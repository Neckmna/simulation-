import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from debate_engine import DebateEngine

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

engine = DebateEngine(GEMINI_API_KEY)

INTRO = """
⚔️ *ARENA — 100 AI Minds Debate Your Question*

Send me any question or topic and watch 100 AI personas tear it apart with data, logic, and raw debate firepower.

*Topics I eat for breakfast:*
🏆 Football, Cricket, UFC
📈 Trading, Markets, Crypto
🌍 Politics, War, History
💡 Science, Tech, Philosophy
🎯 Literally anything

Just send your question. No fluff. Let the arena decide.
"""

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(INTRO, parse_mode="Markdown")

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = update.message.text.strip()
    if not question:
        return

    user = update.message.from_user.first_name or "Challenger"
    
    # Send loading message
    loading_msg = await update.message.reply_text(
        f"🧠 *Arena activated, {user}.*\n\n"
        "⚡ Round 1 — 100 minds forming positions...\n"
        "_(This takes ~20–30 seconds. Real debate takes time.)_",
        parse_mode="Markdown"
    )

    try:
        # Run debate
        result = await engine.run_debate(question)

        # Update to round 2
        await loading_msg.edit_text(
            f"🧠 *Arena activated, {user}.*\n\n"
            "✅ Round 1 — 100 positions captured\n"
            "⚔️ Round 2 — Top 5 gladiators clashing...",
            parse_mode="Markdown"
        )

        # Send final result
        await asyncio.sleep(1)
        await loading_msg.edit_text(
            f"🧠 *Arena activated, {user}.*\n\n"
            "✅ Round 1 — 100 positions captured\n"
            "✅ Round 2 — Champions have clashed\n"
            "🏆 Verdict incoming...",
            parse_mode="Markdown"
        )

        await asyncio.sleep(1)

        # Split result if too long for Telegram (4096 char limit)
        chunks = split_message(result)
        for i, chunk in enumerate(chunks):
            if i == 0:
                await update.message.reply_text(chunk, parse_mode="Markdown")
            else:
                await update.message.reply_text(chunk, parse_mode="Markdown")

        await loading_msg.delete()

    except Exception as e:
        logger.error(f"Debate failed: {e}")
        await loading_msg.edit_text(
            "❌ The arena crashed. Even 100 AI minds have limits.\n"
            f"Error: `{str(e)[:200]}`",
            parse_mode="Markdown"
        )

def split_message(text: str, limit: int = 4000) -> list[str]:
    """Split long messages into chunks for Telegram."""
    if len(text) <= limit:
        return [text]
    
    chunks = []
    while len(text) > limit:
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip('\n')
    
    if text:
        chunks.append(text)
    
    return chunks

def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN environment variable not set")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

    logger.info("Arena bot is live.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
