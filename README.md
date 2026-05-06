# 100 Brain Debate Bot

Send any question to Telegram → 100 AI personas debate it → winner declared with PDF report.

## Features
- 100 unique expert personas argue your question
- 2 rounds of debate with real data
- Real-time data via Tavily web search
- Vision support — send images/charts
- Top 5 debaters shown in Telegram message
- Full PDF debate report with ratings

## Deploy to Railway

1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Add these environment variables:

```
NVIDIA_API_KEY=your_nvidia_api_key
TELEGRAM_TOKEN=your_telegram_bot_token
TAVILY_API_KEY=your_tavily_api_key
```

4. Deploy — bot starts automatically

## How to use

- Send any text question → debate starts
- Send an image/chart with optional caption → vision analysis + debate
- /start → intro message

## Stack
- Kimi K2.6 via NVIDIA API
- Tavily real-time web search
- python-telegram-bot
- ReportLab PDF generation
- Railway deployment
