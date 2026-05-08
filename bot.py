import os
import logging
import requests
import base64
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# ── Track usage per user (in-memory) ──────────────────────────────────────────
user_stats = {}  # {user_id: {"count": 0, "wins": 0, "history": []}}

# ── Master prompt ──────────────────────────────────────────────────────────────
MASTER_PROMPT = """You are a professional sports match analysis AI. Analyze the image containing two teams and determine the winner probability.

PRIORITY ORDER (strictly follow):
1. Current season form — MOST IMPORTANT
2. Recent 5-match momentum
3. League/table position
4. Attack & defense stats this season
5. Home vs away record this season
6. Injuries & squad availability
7. Tactical consistency
8. Head-to-head history — LOWEST PRIORITY

════════════════════════════════════
OUTPUT FORMAT (use exactly this):
════════════════════════════════════

🏆 MATCH PREDICTION REPORT
📅 {Date} | {Tournament/League}

⚔️ {Team A} vs {Team B}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 1. CURRENT SEASON FORM
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{Team A}:
• League position: #X
• Last 5: W/L/W/W/L
• Form rating: ⭐⭐⭐⭐ (4/5)
• Key stat: (goals/runs/points this season)
• Home/Away record: X wins Y losses

{Team B}:
• League position: #X
• Last 5: W/L/W/W/L
• Form rating: ⭐⭐⭐ (3/5)
• Key stat: (goals/runs/points this season)
• Home/Away record: X wins Y losses

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚔️ 2. TACTICAL ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Attacking strength: {Team A} vs {Team B}
• Defensive record: {Team A} vs {Team B}
• Key player (Team A): Name — impact this season
• Key player (Team B): Name — impact this season
• Tactical edge: Which team and why

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📜 3. HEAD-TO-HEAD (Brief)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• All-time: {Team A} X wins | {Team B} Y wins
• Last meeting: result + date
• Venue factor: home advantage note

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 4. FINAL PREDICTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🥇 PREDICTED WINNER: {Team}

Win Probabilities:
• {Team A}: XX%
• {Team B}: XX%
• Draw/NR: XX%

Confidence: 🟢 HIGH / 🟡 MEDIUM / 🔴 LOW
Reasoning: 2-3 sentences on why

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 5. BETTING INSIGHTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Best bet: (e.g. Match winner / Over 2.5 goals / Both teams score / Total runs over)
💡 Value bet: (specific market with reasoning)
⚠️ Avoid: (risky markets for this match)
📊 Risk level: LOW / MEDIUM / HIGH

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 6. MULTI-MARKET PREDICTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
(Give 3 specific betting markets with prediction + probability for each)
1. Market: prediction (XX% likely)
2. Market: prediction (XX% likely)
3. Market: prediction (XX% likely)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ QUICK SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Back: {Team/market}
❌ Skip: {risky bet}
🔥 Confidence score: XX/100

IMPORTANT RULES:
• If current season data is unavailable, clearly state it
• Never guess — if uncertain, say LOW confidence
• Always specify the sport detected
• Keep betting insights responsible"""

WELCOME_MSG = """🏆 *Sports Prediction Bot*

Send me any match screenshot and I'll give you:

📊 Full season form analysis
⚔️ Tactical breakdown
🎯 Win probability %
💰 Best betting markets
🔍 Multi-market predictions
⚡ Confidence score /100

*Supported Sports:*
🏏 Cricket (IPL, ODI, T20, Test)
⚽ Football (EPL, UCL, La Liga, etc.)
🎾 Tennis (Grand Slams, ATP, WTA)
🏀 Basketball (NBA, FIBA)

Just send a screenshot — I'll handle the rest! 📸

/help — How to use
/stats — Your prediction history
/tips — Betting tips & strategy"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_user(uid):
    if uid not in user_stats:
        user_stats[uid] = {"count": 0, "correct": 0, "history": []}
    return user_stats[uid]


def analyze_with_gemini(image_data: bytes) -> str:
    try:
        img_b64 = base64.b64encode(image_data).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": MASTER_PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}
                ]
            }],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 3000}
        }
        r = requests.post(url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        if "candidates" in data and data["candidates"]:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return "❌ No analysis returned. Try again."
    except requests.exceptions.Timeout:
        return "❌ Timed out. Please try again."
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return f"❌ Error: {str(e)}"


def make_feedback_keyboard(analysis_id: str):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Correct prediction", callback_data=f"correct_{analysis_id}"),
            InlineKeyboardButton("❌ Wrong prediction", callback_data=f"wrong_{analysis_id}"),
        ],
        [
            InlineKeyboardButton("🔄 Re-analyze", callback_data=f"reanalyze_{analysis_id}"),
            InlineKeyboardButton("📤 Share", callback_data=f"share_{analysis_id}"),
        ]
    ])


# ── Handlers ───────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME_MSG, parse_mode="Markdown")


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = """📖 *How to use:*

1️⃣ Screenshot any upcoming match
2️⃣ Send it here
3️⃣ Get full prediction in ~15 seconds

*Best screenshot tips:*
• Team names must be clearly visible
• Include tournament name if possible
• Works with any betting app screenshot
• Works with sports news app screenshots

*Commands:*
/start — Welcome
/help — This message
/stats — Your prediction history
/tips — Free betting strategy tips
/sports — Supported sports list"""
    await update.message.reply_text(txt, parse_mode="Markdown")


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    acc = round((u["correct"] / u["count"]) * 100) if u["count"] > 0 else 0
    txt = f"""📈 *Your Stats*

🔍 Total predictions: {u['count']}
✅ Marked correct: {u['correct']}
🎯 Accuracy: {acc}%

{'🔥 Great accuracy! Keep tracking!' if acc >= 60 else '📊 Keep tracking to improve!'}

_Tip: Mark predictions as correct/wrong after matches to track accuracy_"""
    await update.message.reply_text(txt, parse_mode="Markdown")


async def tips_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = """💡 *Free Betting Strategy Tips*

*🥇 Best approach — Value betting:*
• Don't just bet the favorite
• Look for odds higher than the real probability
• Example: Team has 65% chance but odds give 55% → value bet

*🥈 Bankroll management:*
• Never bet more than 2-5% per bet
• With $15 → max $0.75 per bet
• Protect your bankroll first

*🥉 Best markets to target:*
• Both Teams to Score (football)
• Over/Under runs (cricket)
• First set winner (tennis)
• These are easier to predict than match winner

*⚠️ Avoid:*
• Accumulators/parlays (high risk)
• Live betting when emotional
• Chasing losses

*📊 Sports with best prediction rate:*
1. Tennis (top 10 players) — ~68% predictable
2. Cricket (IPL home teams) — ~65% predictable
3. Football (top vs bottom) — ~62% predictable"""
    await update.message.reply_text(txt, parse_mode="Markdown")


async def sports_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = """🌍 *Supported Sports*

🏏 *Cricket*
IPL, ODI, T20I, Test, BBL, PSL, CPL

⚽ *Football*
EPL, La Liga, Bundesliga, Serie A
Champions League, Europa League
MLS, Ligue 1, and more

🎾 *Tennis*
ATP, WTA, Grand Slams
Davis Cup, Fed Cup

🏀 *Basketball*
NBA, EuroLeague, FIBA

_More sports coming soon!_"""
    await update.message.reply_text(txt, parse_mode="Markdown")


async def handle_image(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    u = get_user(uid)

    # Animated loading message
    loading = await update.message.reply_text(
        "🔍 *Scanning match data...*", parse_mode="Markdown"
    )

    try:
        photo = update.message.photo[-1]
        file = await ctx.bot.get_file(photo.file_id)
        image_data = bytes(await file.download_as_bytearray())

        await loading.edit_text("⚡ *Analyzing team form & stats...*", parse_mode="Markdown")
        analysis = analyze_with_gemini(image_data)
        await loading.edit_text("📊 *Generating prediction report...*", parse_mode="Markdown")

        # Update user stats
        analysis_id = f"{uid}_{u['count']}"
        u["count"] += 1
        u["history"].append({
            "id": analysis_id,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "analysis": analysis[:200]
        })

        await loading.delete()

        # Send in chunks if too long
        if len(analysis) > 4000:
            chunks = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
            for i, chunk in enumerate(chunks):
                if i == len(chunks) - 1:
                    await update.message.reply_text(
                        chunk,
                        reply_markup=make_feedback_keyboard(analysis_id)
                    )
                else:
                    await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(
                analysis,
                reply_markup=make_feedback_keyboard(analysis_id)
            )

        # Pro tip after every 5 predictions
        if u["count"] % 5 == 0:
            await update.message.reply_text(
                f"🎯 *You've made {u['count']} predictions!*\n\nUse /stats to see your accuracy.",
                parse_mode="Markdown"
            )

    except Exception as e:
        await loading.delete()
        logger.error(f"Image error: {e}")
        await update.message.reply_text("❌ Error processing image. Please try again with a clearer screenshot.")


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = update.effective_user.id
    u = get_user(uid)
    data = q.data

    if data.startswith("correct_"):
        u["correct"] += 1
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text("✅ *Marked as correct!* Great prediction 🎯\n\nUse /stats to see your accuracy.", parse_mode="Markdown")

    elif data.startswith("wrong_"):
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text("❌ *Marked as wrong.* Keep tracking — accuracy improves over time!\n\nUse /stats to see your history.", parse_mode="Markdown")

    elif data.startswith("reanalyze_"):
        await q.message.reply_text("📸 Send the screenshot again and I'll re-analyze it!")

    elif data.startswith("share_"):
        await q.message.reply_text("📤 *To share:* Forward this message to your friends or betting group!")


async def handle_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()
    # Smart keyword responses
    if any(w in txt for w in ["hi", "hello", "hey"]):
        await update.message.reply_text("👋 Hey! Send me a match screenshot and I'll predict the winner! 📸")
    elif any(w in txt for w in ["ipl", "cricket", "football", "tennis", "nba"]):
        await update.message.reply_text("📸 Send me a screenshot of the match you want predicted!")
    else:
        await update.message.reply_text(
            "📸 Send me a *match screenshot* to get a prediction!\n\nUse /help for instructions.",
            parse_mode="Markdown"
        )


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN not set!")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not set!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("tips", tips_cmd))
    app.add_handler(CommandHandler("sports", sports_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🚀 Bot is running!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
