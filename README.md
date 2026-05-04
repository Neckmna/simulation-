# ⚔️ ARENA BOT — 100 AI Minds Debate Your Questions

A Telegram bot where 100 distinct AI personas debate any question using Gemini 2.0 Flash. The strongest data-backed argument wins.

## How It Works

1. You send a question
2. **Round 1** — All 100 personas give their position with data/logic in one Gemini call
3. **Round 2** — Top 5 strongest voices clash directly, attacking each other's weak points
4. **Final Verdict** — Winner declared based on best argument, sent back to you

## Setup

### 1. Get Your Credentials

**Telegram Bot Token:**
- Open Telegram → search `@BotFather`
- Send `/newbot`
- Follow prompts → copy the token

**Gemini API Key:**
- Go to https://aistudio.google.com/
- Click "Get API Key" → Create → copy it

### 2. Local Testing

```bash
# Clone and enter directory
cd arena-bot

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env and paste your keys

# Run locally
python bot.py
```

For local `.env` loading, install python-dotenv:
```bash
pip install python-dotenv
```

And add to top of `bot.py`:
```python
from dotenv import load_dotenv
load_dotenv()
```

### 3. Deploy to Railway

**Option A — GitHub (Recommended):**
```bash
git init
git add .
git commit -m "Arena bot initial commit"
# Push to GitHub repo
# Then: Railway dashboard → New Project → Deploy from GitHub repo
```

**Option B — Railway CLI:**
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

**Set Environment Variables in Railway:**
- Go to your project → Variables tab
- Add: `TELEGRAM_TOKEN` = your token
- Add: `GEMINI_API_KEY` = your key
- Deploy → Done

## The 100 Personas

The bot includes 100 carefully designed personas across 10 archetypes:
- 📊 Analysts & Strategists (data, game theory, risk)
- 🎯 Domain Experts (sports, finance, medicine, geopolitics)
- 🧠 Philosophers (Stoic, Utilitarian, Kantian, Nietzschean)
- 🌍 Cultural & Political Voices (all major ideologies)
- 🗺️ Regional Specialists (South Asia, East Asia, Africa, etc.)
- 🏢 Industry Insiders (VC, banking, energy, pharma)
- 🔬 Scientists (physics, biology, neuroscience, AI)
- 💡 Unconventional Thinkers (futurists, devil's advocates)
- ⚙️ Practitioners (doctors, diplomats, journalists)
- 🃏 Wildcards (12-year-old, 100-year-old, poet, detective)

## Topics It Handles

- 🏆 Football, Cricket, UFC — tactical, historical, statistical
- 📈 Trading, Markets, Crypto — macro, micro, quant angles
- 🌍 Politics, War, History — all ideologies represented
- 🔬 Science, Tech, Philosophy — first principles to speculation
- 💬 Literally anything

## Architecture

```
bot.py              — Telegram handler, message routing
debate_engine.py    — Gemini API calls, debate logic, 100 personas
requirements.txt    — Dependencies
railway.toml        — Deployment config
Procfile            — Process definition
```

## Cost

- Gemini 2.0 Flash free tier: 15 requests/minute, 1M tokens/day
- Each debate uses ~2 API calls (Round 1 + Round 2)
- Round 1 prompt is large (~3000 tokens input, ~8000 output)
- Free tier handles ~60 debates/day comfortably

## Customization

**Add more personas** — edit the `PERSONAS` list in `debate_engine.py`

**Change the model** — swap `gemini-2.0-flash` for `gemini-1.5-pro` for deeper reasoning (slower, costs more)

**Add /history command** — store debates in a SQLite database

**Add voting** — let users upvote/downvote verdicts with inline keyboard buttons
