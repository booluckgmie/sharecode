# AurumVibe — Daily Gold Price Monitor

Automated daily gold price tracker with buy/sell signals, 2-panel interactive chart, 30-day trend projection, and Telegram alerts.

---

## Features

| Feature | Details |
|---|---|
| Data Source | Yahoo Finance (`GC=F x MYR=X`) by default; or scrape publicgold.me |
| Chart | 2-panel: price history + daily % change bars, MA7, MA30, pawnshop band |
| Signals | BUY/SELL scoring (6 pts each) based on 30D range, peak drop, 7D extremes |
| Delivery | Telegram bot (photo + caption with scores) |
| Persistence | Peak tracked in `last_peak.txt`; full history in `gold_price_history.csv` |
| Schedule | Daily at **09:10 AM Malaysia Time** (01:10 UTC) |

---

## Data Source Architecture

Gold price in RM/gram can be sourced two ways. The `AURUM_DATA_SOURCE` env var toggles the strategy at runtime without code changes.

| Strategy | Source | Formula | Reliability |
|---|---|---|---|
| `SPOT_YFINANCE` *(default)* | Yahoo Finance futures | `(GC=F USD/oz / 31.1035) x MYR=X` | 24/5, no scraping |
| `PUBLIC_GOLD` | publicgold.me retail board | HTML scrape, RM/g direct | may 403 from GitHub IPs |

### Why `SPOT_YFINANCE` is the default

`publicgold.me` began blocking GitHub Actions IP ranges in early May 2025, returning HTTP 403 silently. The yfinance route is unblocked, provides 6 months of history, and includes USD/MYR exchange rate data for the info panel.

**FX Noise caveat**: Because spot price = (gold in USD) x (USD/MYR rate), a falling USD can push the MYR price up even when gold itself is flat — and vice versa. The chart info box shows both components so you can distinguish the two effects.

### Modular Design

The fetcher is selected by factory function at startup:

```python
DATA_SOURCE = os.getenv("AURUM_DATA_SOURCE", "SPOT_YFINANCE")

class SpotYFinanceFetcher:
    def get_data(self) -> pd.DataFrame:
        # Returns df with: Price (RM/g), USD_Price, Rate columns

class PublicGoldFetcher:
    URL = "https://publicgold.me/yes/gold-price-today"
    def get_data(self) -> pd.DataFrame:
        # Returns df with: Price (RM/g); USD_Price=NaN, Rate=NaN

def get_gold_data() -> tuple:
    if DATA_SOURCE == "PUBLIC_GOLD":
        return PublicGoldFetcher().get_data(), "Public Gold (retail)"
    return SpotYFinanceFetcher().get_data(), "Yahoo Finance (GC=F x MYR=X)"
```

To switch strategies, add `AURUM_DATA_SOURCE=PUBLIC_GOLD` to your GitHub Actions environment variables (Settings -> Environments or directly in the workflow file).

---

## Chart

The generated `gold_report.png` has two panels:

**Panel 1 — Price (full height)**
- Gold spot price in RM/gram (gold line)
- MA 7-day (cyan) and MA 30-day (orange) overlays
- 30-day linear projection (dashed yellow)
- Pawnshop buy/sell band (grey fill) with dashed lines for spread limits
- Your average cost (green dotted) and all-time tracked peak (orange dotted)
- Current price dot annotation
- Info box (top-left): data source, USD/oz, USD/MYR rate, timestamp

**Panel 2 — Daily % change bars**
- Green bars for positive days, red for negative
- Gives a quick feel for momentum and volatility

---

## Pawnshop Spread

Gold has two spread layers when trading via pawnshops:

| Type | Typical Spread |
|---|---|
| Digital gold (wakalah/murabahah) | 2-4% total |
| Physical bullion (1g-100g) | 6-15% total |

The script fetches today's **BNM Kijang Emas** official benchmark (free, no auth required) and converts from troy oz to per gram:

```python
sell_to_shop  = bnm_buying_price_oz  / 31.1035   # what you receive
buy_from_shop = bnm_selling_price_oz / 31.1035   # what you pay
```

If the BNM API is unavailable, it falls back to +/-3% spread on the current spot price.

---

## Signal Logic

### Buy Score (max 6 pts)

| Signal | Points |
|---|---|
| Within 1.5% of 30D Low | +2 |
| More than 2% below 30D Average | +1 |
| At 7-day low | +2 |
| >=5% below tracked all-time peak | +1 |

### Sell Score (max 6 pts)

| Signal | Points |
|---|---|
| Within 1.5% of 30D High | +2 |
| More than 3% above 30D Average | +1 |
| Peak reversal pattern (3-day) | +2 |
| At 7-day high | +1 |

### Primary Signal

| Condition | Signal |
|---|---|
| P/L >= +15% above avg cost | Take Profit Zone |
| Sell Score >= 4 | SELL Zone |
| Price >= 5% below peak | BUY Zone |
| Price at 7-day low | Strong BUY Zone |
| Sell Score >= 2 | Watch to Sell |
| Price at 30D high | Near Resistance |
| Otherwise | Neutral — Hold |

---

## GitHub Secrets Required

Go to **Settings -> Secrets and variables -> Actions** and add:

| Secret | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your Telegram chat/channel ID |
| `AVG_COST` | *(Optional)* Your actual average buy price in RM/g |

---

## File Structure

```
aurumvibe/
├── gold_monitor.py          # Main script (modular, strategy-based)
├── gold_monitorV1.py        # Original version (archived)
├── requirements.txt         # Python dependencies
├── last_peak.txt            # Auto-generated: all-time peak price
├── gold_price_history.csv   # Auto-generated: 6-month history with analytics
└── gold_report.png          # Chart output (not committed)
```

### CSV Columns

| Column | Description |
|---|---|
| `date` | Trading date (YYYY-MM-DD) |
| `price_rm_per_g` | Spot gold price in RM/gram |
| `price_usd_per_oz` | Gold price in USD/oz (NaN for PUBLIC_GOLD source) |
| `usd_myr_rate` | USD/MYR exchange rate (NaN for PUBLIC_GOLD source) |
| `pawnshop_sell_rm_per_g` | Estimated sell-to-pawnshop price |
| `pawnshop_buy_rm_per_g` | Estimated buy-from-pawnshop price |
| `pawnshop_spread_pct` | Total spread % for that day |
| `pawnshop_rate_source` | BNM Kijang Emas or estimated |
| `daily_change_rm` | Day-over-day change in RM/g |
| `daily_change_pct` | Day-over-day percentage change |
| `ma_7d` | 7-day moving average |
| `ma_30d` | 30-day moving average |
| `high_30d` | Rolling 30D high |
| `low_30d` | Rolling 30D low |
| `pct_from_30d_high` | % distance from 30D high (negative = below high) |

---

## Setup

1. Fork or clone this repo
2. Add the required GitHub Secrets above
3. Push to `master` — the workflow runs automatically every day at 09:10 AM MYT
4. To test immediately: **Actions -> Daily Gold Monitor -> Run workflow**

---

## Requirements

```
yfinance
pandas
matplotlib
requests
numpy
beautifulsoup4
```

---

## Workflow Behaviour

- Runs daily via cron (`10 1 * * *` UTC = 09:10 MYT)
- Triggered manually via `workflow_dispatch`
- Commits `last_peak.txt` and `gold_price_history.csv` back to repo after each run
- Uses `--rebase` + stash strategy to avoid push conflicts on concurrent runs
- On any script failure, sends an error notification to Telegram (no silent failures)
