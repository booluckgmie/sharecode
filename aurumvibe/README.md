# 🏅 AurumVibe — Daily Gold Price Monitor

Automated daily gold price tracker powered by **Public Gold (publicgold.me)**, with buy/sell signals, 30-day trend projection, and Telegram alerts.

---

## 📋 Features

| Feature | Details |
|---|---|
| 📡 Data Source | publicgold.me (scraped daily) |
| 📊 Chart | Historical price + 30-day linear projection |
| 🧠 Signals | BUY / SELL / Neutral based on 30d range & peak |
| 💬 Delivery | Telegram bot (photo + caption) |
| 🗃️ Persistence | Peak price tracked via `last_peak.txt` in repo |
| ⏰ Schedule | Daily at **08:00 AM Malaysia Time** (00:00 UTC) |

---

## ⚙️ GitHub Secrets Required

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from [@BotFather](https://t.me/BotFather) |
| `TELEGRAM_CHAT_ID` | Your Telegram chat/channel ID |
| `AVG_COST` | *(Optional)* Your actual average buy price in RM/g. If not set, defaults to the 30-day midpoint. |

---

## 🧠 Signal Logic

| Signal | Condition |
|---|---|
| 🔴 Take Profit | Current P/L ≥ +15% above `AVG_COST` |
| 🟢 BUY Zone | Price ≥ 5% below tracked peak |
| 🟢 Strong BUY | Price at 7-day low |
| ⚠️ Near Resistance | Price at or above 30D high |
| ⚖️ Neutral | None of the above |

---

## 📁 Project Structure

```
aurumvibe/
├── gold_monitor.py       # Main script
├── requirements.txt      # Python dependencies
├── last_peak.txt         # Auto-generated, committed by workflow
└── gold_report.png       # Chart output (not committed)
```

---

## 🚀 Setup

1. Fork or clone this repo
2. Add the required GitHub Secrets above
3. Push to `master` — the workflow runs automatically every day at 08:00 AM MYT
4. To test immediately: **Actions → Daily Gold Monitor → Run workflow**

---

## 📦 Requirements

```
requests
beautifulsoup4
pandas
matplotlib
numpy
```

---

## 🔧 Workflow Behaviour

- Runs daily via cron (`0 0 * * *` UTC = 08:00 MYT)
- Can be triggered manually via `workflow_dispatch`
- Only commits `last_peak.txt` back to repo (chart PNG is excluded)
- Uses `--rebase` + stash strategy to avoid push conflicts on concurrent runs
