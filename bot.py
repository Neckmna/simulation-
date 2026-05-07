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

NVIDIA_MODELS = [
    "moonshotai/kimi-k2-instruct",
    "google/gemma-4-31b-it",
    "z-ai/glm-5.1",
    "moonshotai/kimi-k2.6",
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
            response = nvidia_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": content}],
                max_tokens=max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Vision {model} failed: {e}")
            last_error = e
            continue
    raise Exception(f"All vision models failed. Last error: {last_error}")

SYSTEM_PROMPT = """You are a debate engine. Two expert personas are chosen based on the question topic.
They have deep knowledge across ALL domains: trading/finance, sports (football, cricket, UFC),
politics, military history, science, economics, and current events.

IMPORTANT RULES:
- Every argument MUST be backed by specific data, statistics, historical facts, or logical reasoning
- The two personas MUST strongly disagree with each other
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

def run_debate(question: str, realtime_data: str) -> dict:
    prompt = f"""QUESTION: {question}

{realtime_data}

TASK: Pick the 2 best expert personas suited for this question topic. Have them debate with strong opposing views backed by real data.

Format your response as JSON:
{{
  "persona_a": {{
    "name": "e.g. Football Analyst",
    "position": "Their stance in 5-8 words",
    "argument": "3-4 sentences with specific data, stats, names, dates",
    "confidence": 85,
    "key_data_point": "Single strongest fact supporting their view"
  }},
  "persona_b": {{
    "name": "e.g. Sports Statistician",
    "position": "Their opposing stance in 5-8 words",
    "argument": "3-4 sentences with specific data, stats, names, dates that contradicts Persona A",
    "confidence": 78,
    "key_data_point": "Single strongest fact supporting their view"
  }},
  "winner": {{
    "persona": "Persona A or Persona B name",
    "final_verdict": "The definitive answer in 2-3 sentences",
    "overall_rating": 8.5,
    "why_won": "Why this argument was stronger with specific reasoning",
    "key_data_points": ["fact 1", "fact 2", "fact 3", "fact 4", "fact 5"],
    "confidence_level": "HIGH/MEDIUM/LOW",
    "caveats": "What could change this verdict"
  }},
  "bottom_line": "One sentence final answer",
  "dissenting_view": "Strongest point from the losing side"
}}"""

    raw = call_nvidia(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=0.8,
        max_tokens=3000
    )
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        try:
            return json.loads(json_match.group())
        except:
            pass
    return {"raw": raw}

def format_telegram_message(question: str, result: dict) -> str:
    pa = result.get("persona_a", {})
    pb = result.get("persona_b", {})
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

    msg = "🧠 *2 BRAIN DEBATE COMPLETE*\n"
    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"❓ *Question:* {question}\n\n"

    msg += f"🔵 *{pa.get('name', 'Persona A')}*\n"
    msg += f"   📍 _{pa.get('position', '')}_\n"
    msg += f"   💬 {pa.get('argument', '')}\n"
    msg += f"   🔑 {pa.get('key_data_point', '')}\n"
    msg += f"   Confidence: `{pa.get('confidence', 0)}%`\n\n"

    msg += f"🔴 *{pb.get('name', 'Persona B')}*\n"
    msg += f"   📍 _{pb.get('position', '')}_\n"
    msg += f"   💬 {pb.get('argument', '')}\n"
    msg += f"   🔑 {pb.get('key_data_point', '')}\n"
    msg += f"   Confidence: `{pb.get('confidence', 0)}%`\n\n"

    msg += "━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏆 *WINNER: {winner.get('persona', 'Unknown')}*\n"
    msg += f"📊 Rating: `{winner.get('overall_rating', 0)}/10` {get_bar(winner.get('overall_rating', 0))}\n"
    msg += f"🎯 Confidence: `{winner.get('confidence_level', 'N/A')}`\n\n"
    msg += f"✅ *VERDICT:*\n_{winner.get('final_verdict', '')}_\n\n"
    msg += "📌 *KEY DATA POINTS:*\n"
    for i, dp in enumerate(winner.get('key_data_points', [])[:5], 1):
        msg += f"  {i}. {dp}\n"
    msg += "\n━━━━━━━━━━━━━━━━━━━━\n"
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
            "⚔️ 2 experts debating...",
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

        result = await asyncio.get_event_loop().run_in_executor(
            None, run_debate, question, realtime_data
        )

        await status_msg.edit_text(
            "🧠 *Debate in progress...*\n\n"
            "✅ Real-time data fetched\n"
            "✅ Debate complete\n"
            "📄 Generating PDF report...",
            parse_mode=ParseMode.MARKDOWN
        )

        telegram_msg = format_telegram_message(question, result)

        # Build dummy round1/round2 for PDF compatibility
        round1 = {"positions": [
            {"id": 1, "persona": result.get("persona_a", {}).get("name", "Persona A"),
             "position": result.get("persona_a", {}).get("position", ""),
             "argument": result.get("persona_a", {}).get("argument", ""),
             "confidence": result.get("persona_a", {}).get("confidence", 0),
             "key_data_point": result.get("persona_a", {}).get("key_data_point", "")},
            {"id": 2, "persona": result.get("persona_b", {}).get("name", "Persona B"),
             "position": result.get("persona_b", {}).get("position", ""),
             "argument": result.get("persona_b", {}).get("argument", ""),
             "confidence": result.get("persona_b", {}).get("confidence", 0),
             "key_data_point": result.get("persona_b", {}).get("key_data_point", "")}
        ]}
        round2 = {"top_debaters": [], "eliminated": [], "emerging_consensus": "Single round debate"}

        # Build top_5 from the 2 debaters for PDF
        winner_name = result.get("winner", {}).get("persona", "")
        pa_name = result.get("persona_a", {}).get("name", "Persona A")
        pb_name = result.get("persona_b", {}).get("name", "Persona B")
        final_result = {
            "winner": result.get("winner", {}),
            "top_5": [
                {"rank": 1, "persona": pa_name,
                 "position": result.get("persona_a", {}).get("position", ""),
                 "score": result.get("winner", {}).get("overall_rating", 0) if winner_name == pa_name else round(result.get("winner", {}).get("overall_rating", 0) * 0.85, 1),
                 "strongest_argument": result.get("persona_a", {}).get("key_data_point", ""),
                 "weakness": "Lost the debate" if winner_name != pa_name else "Minor caveats only"},
                {"rank": 2, "persona": pb_name,
                 "position": result.get("persona_b", {}).get("position", ""),
                 "score": result.get("winner", {}).get("overall_rating", 0) if winner_name == pb_name else round(result.get("winner", {}).get("overall_rating", 0) * 0.85, 1),
                 "strongest_argument": result.get("persona_b", {}).get("key_data_point", ""),
                 "weakness": "Lost the debate" if winner_name != pb_name else "Minor caveats only"},
            ],
            "bottom_line": result.get("bottom_line", ""),
            "dissenting_view": result.get("dissenting_view", "")
        }

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
        "🧠 *2 BRAIN DEBATE BOT*\n\n"
        "Send me any question and 2 AI experts will debate it using real-time data.\n\n"
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
