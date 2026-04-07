This `README.md` is designed for a professional production environment, tailored for a data-driven workflow. It covers the architecture, setup, and logic of your **AurumVibe** monitor.

---

# 📈 AurumVibe: Automated Gold Monitor & Telegram Alerter

**AurumVibe** is a lightweight, serverless data pipeline designed to monitor global gold spot prices, convert them to Malaysian Ringgit (MYR), and provide actionable Buy/Sell signals via Telegram. 

It leverages "vibe architecture"—prioritizing rapid iteration and AI-assisted deployment—running entirely on **GitHub Actions** to eliminate infrastructure overhead.

---

## 🚀 Key Features

* **Dual-Stream Data Integration:** Fetches real-time Gold Futures (`GC=F`) and USD/MYR exchange rates (`MYR=X`) via the Yahoo Finance API.
* **Asymmetric Alerting Logic:**
    * 🟢 **Buy Alert:** Triggered on a **5% drop** from recent local peaks (Capital Preservation).
    * 🔴 **Sell Alert:** Triggered on a **15% gain** above your personal average cost (Profit Harvesting).
* **Weekly Visual Analytics:** Every Monday, the system generates a 90-day historical chart combined with a 30-day trend projection.
* **Serverless Execution:** Fully automated via GitHub Actions (CRON-scheduled).

---

## 🛠 Tech Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.9+ |
| **Data Source** | `yfinance` |
| **Data Processing** | `pandas`, `numpy` |
| **Visualization** | `matplotlib` |
| **Automation** | GitHub Actions |
| **Communication** | Telegram Bot API |

---

## 📂 Project Structure

```text
.
├── .github/
│   └── workflows/
│       └── gold_weekly.yml    # GitHub Actions Schedule (Mon 8AM MYT)
├── gold_monitor.py            # Main execution script & alert logic
├── requirements.txt           # Python dependencies
└── last_peak.txt              # (Auto-generated) Tracks historical highs
```

---

## ⚙️ Setup & Deployment

### 1. Telegram Configuration
1.  Create a bot via [@BotFather](https://t.me/botfather) and save the **API Token**.
2.  Retrieve your **Chat ID** via [@userinfobot](https://t.me/userinfobot).

### 2. GitHub Secrets
To maintain security and privacy (especially regarding your average cost), navigate to **Settings > Secrets and variables > Actions** in your repository and add the following:

| Secret Name | Description |
| :--- | :--- |
| `TELEGRAM_BOT_TOKEN` | Your Bot's API Key |
| `TELEGRAM_CHAT_ID` | Your Personal Telegram ID |
| `AVG_COST` | Your current average buy price (e.g., 320.00) |

### 3. Local Customization
In `gold_monitor.py`, you can tune the "Vibe" of your alerts by adjusting these constants:
* `DROP_THRESHOLD = 0.05` (5% for Buy signals)
* `RISE_THRESHOLD = 0.15` (15% for Sell signals)

---

## 📊 Alert Logic Breakdown

The app calculates the local price using the following formula:

$$Price_{MYR/g} = \left( \frac{Spot_{USD/oz}}{31.1035} \right) \times Rate_{USD/MYR}$$

> **Note on the 15% Sell Threshold:** > Considering the typical **5%–8% spread** in Malaysian physical gold markets (Public Gold, Maybank GIA), a 15% alert ensures a net profit of approximately **7%–10%** after transaction costs.

---

## 🛠 Maintenance
* **Manual Trigger:** You can trigger an instant report by going to the **Actions** tab in GitHub and selecting **Run workflow**.
* **Updating Cost:** If you make a new purchase, remember to update the `AVG_COST` secret in GitHub to keep the Sell alerts accurate.

---

**Disclaimer:** *This tool is for informational and automation purposes only. Financial decisions should be based on your own research and risk appetite.*
