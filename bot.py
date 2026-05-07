import os
import logging
import asyncio
import json
import re
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from openai import OpenAI
from tavily import TavilyClient
from pdf_generator import generate_debate_pdf
import base64

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

nvidia_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)
tavily_client = TavilyClient(api_key=TAVILY_API_KEY)

# Fallback chain — tries each model in order until one works
NVIDIA_MODELS = [
    "moonshotai/kimi-k2-instruct",   # primary — best reasoning
    "google/gemma-4-31b-it",         # fallback 1
    "z-ai/glm-5.1",                  # fallback 2
    "moonshotai/kimi-k2.6",          # fallback 3
]

VISION_MODELS = [
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2.6",
]

def call_nvidia(messages, temperature=0.8, max_tokens=4000):
    last_error = None
    for model in NVIDIA_MODELS:
        try:
            logger.info(f"Trying model: {model}")
            response = nvidia_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            logger.info(f"Success with: {model}")
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"{model} failed: {e}")
            last_error = e
            continue
    raise Exception(f"All models failed. Last error: {last_error}")

def call_nvidia_vision(content, max_tokens=500):
    last_error = None
    for model in VISION_MODELS:
        try:
            logger.info(f"Trying vision model: {model}")
            response = nvidia_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_tokens
            )
            logger.info(f"Vision success with: {model}")
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Vision {model} failed: {e}")
            last_error = e
            continue
    raise Exception(f"All vision models failed. Last error: {last_error}")

SYSTEM_PROMPT = """You are a debate simulation engine controlling 100 distinct expert personas.
Each persona has deep knowledge across ALL domains: trading/finance, sports (football, cricket, UFC),
politics, military history, science, economics, and current events.

The 100 personas are:
1-10: Sports Analysts (football, cricket, UFC, tennis, F1, basketball, rugby, baseball, golf, athletics)
11-20: Financial Experts (trader, economist, hedge fund manager, risk analyst, quant, CFO, central banker, VC, forex specialist, crypto analyst)
21-30: Political Scientists (geopolitics, military strategy, diplomacy, conflict analyst, historian, war strategist, intelligence analyst, sanctions expert, UN analyst, regional specialist)
31-40: Scientists (physicist, biologist, statistician, data scientist, AI researcher, climate scientist, neuroscientist, mathematician, chemist, astronomer)
41-50: Contrarians/Devil Advocates (skeptic, pessimist, contrarian trader, black swan theorist, crash predictor, anti-consensus thinker x5, chaos theorist, randomness expert, uncertainty specialist)
51-60: Optimists/Bulls (optimist, bull analyst, growth theorist, momentum trader, trend follower x5, recovery specialist, upside hunter, opportunity seeker)
61-70: Historians (ancient, medieval, modern, military, economic, sports, political, cultural, technological, scientific historians)
71-80: Psychologists/Behavioralists (crowd psychology, trader psychology, sports psychology, political psychology, behavioral economist x5, decision theorist, bias analyst, emotion specialist)
81-90: Journalists/Investigators (sports journalist, financial journalist, war correspondent, political reporter, investigative journalist x5, data journalist, fact checker, source analyst)
91-100: Wildcards (philosopher, ethicist, futurist, game theorist, conspiracy analyst, insider trader [fictional], locker room informant [fictional], street analyst, gut instinct expert, chaos agent)

IMPORTANT RULES:
- Every argument MUST be backed by specific data, statistics, historical facts, or logical reasoning
- Personas DISAGREE strongly - no quick consensus
- Use the real-time data provided to make arguments current and relevant
- Be specific: name teams, players, dates, prices, events
- Arguments should feel like real expert debate, not generic opinions"""

async def fetch_realtime_data(query: str) -> str:
    try:
        result = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
            include_answer=True
        )
        context = "REAL-TIME DATA (fetched now):\n"
        if result.get("answer"):
            context += f"Summary: {result['answer']}\n\n"
        context += "Sources:\n"
        for r in result.get("results", [])[:5]:
            context += f"- {r.get('title', '')}: {r.get('content', '')[:300]}\n"
        return context
    except Exception as e:
        logger.error(f"Tavily error: {e}")
        return "Real-time data unavailable. Use your training knowledge."

def run_debate_round(question: str, realtime_data: str, round_num: int, prev_arguments: str = "") -> dict:
    if round_num == 1:
        prompt = f"""QUESTION: {question}

{realtime_data}

TASK - ROUND 1: Simulate 100 expert personas each giving their position with data-backed reasoning.

Format your response as JSON:
{{
  "round": 1,
  "positions": [
    {{
      "id": 1,
      "persona": "Sports Analyst #1 (Football)",
      "position": "Brief stance in 5 words",
      "argument": "2-3 sentences with specific data/stats/facts",
      "confidence": 85,
      "key_data_point": "The most important fact supporting this view"
    }}
  ]
}}

Generate all 100 personas. Make them DISAGREE. Use specific numbers, names, dates. No vague opinions."""

    else:
        prompt = f"""QUESTION: {question}

{realtime_data}

ROUND 1 ARGUMENTS SUMMARY:
{prev_arguments}

TASK - ROUND 2: The top 10 strongest personas now challenge each other aggressively.
They attack weak arguments, defend their position with NEW data points, and try to win.

Format your response as JSON:
{{
  "round": 2,
  "top_debaters": [
    {{
      "id": 1,
      "persona": "Sports Analyst #1",
      "original_position": "Their round 1 stance",
      "counter_attack": "Attack on the strongest opposing argument with data",
      "defense": "Why their position still holds with new evidence",
      "updated_confidence": 90,
      "strength_score": 8.5,
      "key_evidence": "Strongest data point after round 2"
    }}
  ],
  "eliminated": ["list of persona types whose arguments collapsed"],
  "emerging_consensus": "Brief note on which side is winning or if still split"
}}"""

    raw = call_nvidia(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=4000
    )
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass
    return {"raw": raw}

def pick_winner(question: str, realtime_data: str, round1: dict, round2: dict) -> dict:
    r1_summary = json.dumps(round1, indent=2)[:2000]
    r2_summary = json.dumps(round2, indent=2)[:2000]

    prompt = f"""QUESTION: {question}

{realtime_data}

ROUND 1 DATA: {r1_summary}
ROUND 2 DATA: {r2_summary}

TASK: Analyze both rounds and declare the winning argument. Be a strict judge.

Format as JSON:
{{
  "winner": {{
    "persona": "Winning persona type",
    "final_verdict": "The definitive answer to the question in 2-3 sentences",
    "overall_rating": 9.2,
    "why_won": "Why this argument was stronger than others",
    "key_data_points": ["data point 1", "data point 2", "data point 3", "data point 4", "data point 5"],
    "confidence_level": "HIGH/MEDIUM/LOW",
    "caveats": "What could change this verdict"
  }},
  "top_5": [
    {{
      "rank": 1,
      "persona": "Persona name",
      "position": "Their stance",
      "score": 9.2,
      "strongest_argument": "Their best point",
      "weakness": "Where they fell short"
    }}
  ],
  "bottom_line": "One sentence final answer",
  "dissenting_view": "Strongest opposing argument that didn't win"
}}"""

    raw = call_nvidia(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        max_tokens=2000
    )
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass
    return {"raw": raw}

def format_telegram_message(question: str, result: dict) -> str:
    top5 = result.get("top_5", [])
    winner = result.get("winner", {})
    bottom_line = result.get("bottom_line", "")
    dissent = result.get("dissenting_view", "")

    def get_bar(score):
        try:
            s = int(float(score))
        except:
            s = 0
        if s >= 9: return "🟢🟢🟢🟢🟢"
        if s >= 8: return "🟢🟢🟢🟢⚪"
        if s >= 7: return "🟢🟢🟢⚪⚪"
        if s >= 6: return "🟢🟢⚪⚪⚪"
        return "🟢⚪⚪⚪⚪"

    msg = "🧠 *100 BRAIN DEBATE COMPLETE*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"❓ *Question:* {question}\n\n"
    msg += f"🏆 *WINNER: {winner.get('persona', 'Unknown')}*\n"
    msg += f"📊 Rating: `{winner.get('overall_rating', 0)}/10` {get_bar(winner.get('overall_rating', 0))}\n"
    msg += f"🎯 Confidence: `{winner.get('confidence_level', 'N/A')}`\n\n"
    msg += f"✅ *VERDICT:*\n_{winner.get('final_verdict', '')}_\n\n"
    msg += "📌 *KEY DATA POINTS:*\n"
    for i, dp in enumerate(winner.get('key_data_points', [])[:5], 1):
        msg += f"  {i}. {dp}\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
    msg += "🔥 *TOP 5 DEBATERS:*\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, debater in enumerate(top5[:5]):
        score = debater.get('score', 0)
        msg += f"{medals[i]} *{debater.get('persona', '')}*\n"
        msg += f"   Score: `{score}/10` {get_bar(score)}\n"
        msg += f"   📍 _{debater.get('position', '')}_\n"
        msg += f"   💪 {debater.get('strongest_argument', '')}\n"
        msg += f"   ⚠️ Weakness: {debater.get('weakness', '')}\n\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"💬 *BOTTOM LINE:*\n_{bottom_line}_\n\n"
    msg += f"🔴 *DISSENTING VIEW:*\n_{dissent}_\n\n"
    msg += "📄 _Full debate report attached as PDF_"
    return msg

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    question = None
    image_data = None

    if message.photo:
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        file_bytes = await file.download_as_bytearray()
        image_data = base64.b64encode(file_bytes).decode("utf-8")
        question = message.caption or "Analyze this image and debate what it shows"
    elif message.document and message.document.mime_type.startswith("image/"):
        file = await context.bot.get_file(message.document.file_id)
        file_bytes = await file.download_as_bytearray()
        image_data = base64.b64encode(file_bytes).decode("utf-8")
        question = message.caption or "Analyze this image and debate what it shows"
    elif message.text:
        question = message.text
    else:
        await message.reply_text("Send me a question or an image!")
        return

    status_msg = await message.reply_text(
        "🧠 *Debate starting...*\n\n🔍 Fetching real-time data...",
        parse_mode=ParseMode.MARKDOWN
    )

    try:
        realtime_data = await fetch_realtime_data(question)

        await status_msg.edit_text(
            "🧠 *Debate in progress...*\n\n"
            "✅ Real-time data fetched\n"
            "⚔️ Round 1: 100 brains forming positions...",
            parse_mode=ParseMode.MARKDOWN
        )

        if image_data:
            image_analysis = await asyncio.get_event_loop().run_in_executor(
                None, call_nvidia_vision,
                [
                    {"type": "text", "text": f"Analyze this image in detail for debate context about: {question}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
                ]
            )
            realtime_data = f"IMAGE ANALYSIS:\n{image_analysis}\n\n{realtime_data}"

        round1 = await asyncio.get_event_loop().run_in_executor(
            None, run_debate_round, question, realtime_data, 1, ""
        )

        r1_summary = ""
        positions = round1.get("positions", [])
        if positions:
            for p in positions[:20]:
                r1_summary += f"- {p.get('persona', '')}: {p.get('position', '')} (confidence: {p.get('confidence', 0)}%)\n"

        await status_msg.edit_text(
            "🧠 *Debate in progress...*\n\n"
            "✅ Real-time data fetched\n"
            "✅ Round 1 complete — 100 positions formed\n"
            "🔥 Round 2: Top debaters clashing...",
            parse_mode=ParseMode.MARKDOWN
        )

        round2 = await asyncio.get_event_loop().run_in_executor(
            None, run_debate_round, question, realtime_data, 2, r1_summary
        )

        await status_msg.edit_text(
            "🧠 *Debate in progress...*\n\n"
            "✅ Real-time data fetched\n"
            "✅ Round 1 complete\n"
            "✅ Round 2 complete\n"
            "⚖️ Picking winner...",
            parse_mode=ParseMode.MARKDOWN
        )

        final_result = await asyncio.get_event_loop().run_in_executor(
            None, pick_winner, question, realtime_data, round1, round2
        )

        await status_msg.edit_text(
            "🧠 *Debate in progress...*\n\n"
            "✅ Real-time data fetched\n"
            "✅ Round 1 complete\n"
            "✅ Round 2 complete\n"
            "✅ Winner selected\n"
            "📄 Generating PDF report...",
            parse_mode=ParseMode.MARKDOWN
        )

        telegram_msg = format_telegram_message(question, final_result)

        pdf_path = await asyncio.get_event_loop().run_in_executor(
            None, generate_debate_pdf, question, realtime_data, round1, round2, final_result
        )

        await status_msg.delete()
        await message.reply_text(telegram_msg, parse_mode=ParseMode.MARKDOWN)

        with open(pdf_path, "rb") as pdf_file:
            await message.reply_document(
                document=pdf_file,
                filename=f"debate_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                caption="📄 Full debate analysis report"
            )

        os.unlink(pdf_path)

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Error: {str(e)}\n\nTry again.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *100 BRAIN DEBATE BOT*\n\n"
        "Send me any question and 100 AI personas will debate it using real-time data.\n\n"
        "📌 *Topics I handle:*\n"
        "⚽ Football, 🏏 Cricket, 🥊 UFC\n"
        "📈 Trading & Markets\n"
        "🏛️ Politics & War\n"
        "🌍 Anything else\n\n"
        "📸 You can also send an *image* for visual debate analysis!\n\n"
        "Just send your question to start!",
        parse_mode=ParseMode.MARKDOWN
    )

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.IMAGE, handle_message))
    logger.info("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
