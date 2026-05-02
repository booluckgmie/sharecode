import requests
from bs4 import BeautifulSoup
import re
import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import numpy as np

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RISE_THRESHOLD = 0.15   # 15% gain  → Take profit alert
DROP_THRESHOLD = 0.05   # 5% drop   → Buy more alert
PEAK_FILE = "last_peak.txt"


# ---------------------------------------------------------------------------
# 1. DATA SOURCE: Public Gold (publicgold.me)
# ---------------------------------------------------------------------------

def get_public_gold_data() -> pd.DataFrame:
    url = "https://publicgold.me/yes/gold-price-today"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        res = requests.get(url, headers=headers, timeout=15).text
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to reach publicgold.me: {e}")

    match = re.search(r"data:\s*\[([\d.,\s]+)\]", res)
    if not match:
        raise ValueError("❌ Could not find price data on Public Gold page. "
                         "The site layout may have changed.")

    data_str = "[" + match.group(1) + "]"
    prices = json.loads(data_str)

    if len(prices) < 2:
        raise ValueError("❌ Not enough price data points returned from scrape.")

    n = len(prices)
    dates = [datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=n - 1 - i) for i in range(n)]

    df = pd.DataFrame({"Price": prices}, index=dates)
    print(f"✅ Data fetched: {n} price points "
          f"({dates[0].strftime('%d %b')} → {dates[-1].strftime('%d %b %Y')})")
    return df


# ---------------------------------------------------------------------------
# 2. PEAK PERSISTENCE
# ---------------------------------------------------------------------------

def handle_peak(current_price: float) -> float:
    try:
        with open(PEAK_FILE, "r") as f:
            peak = float(f.read().strip())
    except (FileNotFoundError, ValueError):
        peak = current_price

    if current_price > peak:
        peak = current_price
        with open(PEAK_FILE, "w") as f:
            f.write(f"{peak:.4f}")
        print(f"🆕 New peak recorded: RM {peak:.4f}")

    return peak


# ---------------------------------------------------------------------------
# 3. PROJECTION (linear trend, next 30 days)
# ---------------------------------------------------------------------------

def generate_projection(df: pd.DataFrame) -> pd.DataFrame:
    last_date = df.index[-1]
    window = df["Price"].values[-20:]
    x = np.arange(len(window))
    slope, intercept = np.polyfit(x, window, 1)

    future_x = np.arange(len(window), len(window) + 30)
    future_y = slope * future_x + intercept

    proj_dates = [last_date + timedelta(days=i) for i in range(1, 31)]
    return pd.DataFrame({"Price": future_y}, index=proj_dates)


# ---------------------------------------------------------------------------
# 4. BUY SIGNAL SCORING  (max 6 pts)
# ---------------------------------------------------------------------------

def compute_buy_score(current_price: float, low_30d: float,
                      avg_30d: float, prices: list,
                      peak_price: float) -> tuple[int, list[str]]:
    score = 0
    signals = []

    # Near 30D low (within 1.5%)
    proximity_to_low = (current_price - low_30d) / low_30d * 100
    if proximity_to_low <= 1.5:
        score += 2
        signals.append(f"📉 Near 30D Low (+{proximity_to_low:.1f}%)")

    # Below 30D average by ≥2%
    below_avg = (avg_30d - current_price) / avg_30d * 100
    if below_avg >= 2.0:
        score += 1
        signals.append(f"📊 Below 30D Avg ({below_avg:.1f}%)")

    # At 7-day low
    if len(prices) >= 7 and current_price <= min(prices[-7:]):
        score += 2
        signals.append("🟢 7D Low")

    # Drop from peak ≥5%
    drop_pct = (peak_price - current_price) / peak_price if peak_price else 0
    if drop_pct >= DROP_THRESHOLD:
        score += 1
        signals.append(f"⬇️ {drop_pct:.1%} below peak")

    return score, signals


# ---------------------------------------------------------------------------
# 5. SELL SIGNAL SCORING  (max 6 pts)
# ---------------------------------------------------------------------------

def compute_sell_score(current_price: float, high_30d: float,
                       avg_30d: float,
                       prices: list) -> tuple[int, list[str]]:
    score = 0
    signals = []

    # Near 30D high (within 1.5%)
    proximity_to_high = (high_30d - current_price) / high_30d * 100
    if proximity_to_high <= 1.5:
        score += 2
        signals.append(f"🏔 Near 30D High ({proximity_to_high:.1f}% away)")

    # Above 30D average by ≥3%
    above_avg = (current_price - avg_30d) / avg_30d * 100
    if above_avg >= 3.0:
        score += 1
        signals.append(f"📈 Above 30D Avg (+{above_avg:.1f}%)")

    # Peak reversal: price fell after 2 consecutive up-days
    if len(prices) >= 3:
        last3 = prices[-3:]
        if last3[-1] < last3[-2] > last3[-3]:   # ▲▲▼ pattern
            score += 2
            signals.append("⛰️ Peak Reversal Detected")

    # At 7-day high
    if len(prices) >= 7 and current_price >= max(prices[-7:]):
        score += 1
        signals.append("🔴 7D High")

    return score, signals


# ---------------------------------------------------------------------------
# 6. CHART
# ---------------------------------------------------------------------------

def create_chart(df: pd.DataFrame, proj_df: pd.DataFrame,
                 current_price: float, avg_cost: float) -> str:
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.patch.set_facecolor("#0f0f0f")
    ax.set_facecolor("#1a1a2e")

    ax.plot(df.index, df["Price"],
            color="#DAA520", linewidth=2.5, label="Public Gold Price")
    ax.fill_between(df.index, df["Price"], color="#DAA520", alpha=0.08)

    ax.plot(proj_df.index, proj_df["Price"],
            color="#FFD700", linestyle="--", linewidth=1.8,
            alpha=0.75, label="Projection (30d)")

    ax.axhline(avg_cost, color="#00FF88", linestyle=":",
               linewidth=1.5, alpha=0.7, label=f"Avg Cost RM {avg_cost:.2f}")

    ax.scatter([df.index[-1]], [current_price],
               color="#FFD700", s=80, zorder=5)

    ax.set_title(f"Public Gold Price Trend & Projection (RM/g) — "
                 f"{datetime.now().strftime('%d %b %Y')}",
                 color="white", fontsize=13, pad=14)
    ax.set_ylabel("Price (RM/gram)", color="#cccccc")
    ax.tick_params(colors="#aaaaaa")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.grid(True, alpha=0.15, color="#444444")
    ax.legend(facecolor="#222222", labelcolor="white", fontsize=9)
    fig.autofmt_xdate()
    plt.tight_layout()

    chart_path = "gold_report.png"
    plt.savefig(chart_path, dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    return chart_path


# ---------------------------------------------------------------------------
# 7. TELEGRAM
# ---------------------------------------------------------------------------

def send_telegram(chart_path: str, caption: str) -> None:
    if not TOKEN or not CHAT_ID:
        print("⚠️  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping send.")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(chart_path, "rb") as photo:
            payload = {"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"}
            response = requests.post(url, data=payload,
                                     files={"photo": photo}, timeout=20)
        if response.status_code != 200:
            print(f"❌ Telegram Error {response.status_code}: {response.text}")
        else:
            print("✅ Telegram message sent successfully!")
    except Exception as e:
        print(f"❌ Telegram connection error: {e}")


# ---------------------------------------------------------------------------
# 8. MAIN
# ---------------------------------------------------------------------------

def main():
    try:
        # --- Data ---
        df = get_public_gold_data()
        prices = df["Price"].tolist()

        current_price = prices[-1]
        prev_price    = prices[-2] if len(prices) > 1 else current_price
        change        = current_price - prev_price

        window_30      = prices[-30:] if len(prices) >= 30 else prices
        high_30d       = max(window_30)
        low_30d        = min(window_30)
        avg_30d        = sum(window_30) / len(window_30)
        median_30d     = (high_30d + low_30d) / 2   # midpoint of 30d range

        effective_avg_cost = median_30d

        # --- Peak tracking ---
        peak_price = handle_peak(current_price)

        # --- Projection & Chart ---
        proj_df    = generate_projection(df)
        chart_path = create_chart(df, proj_df, current_price, effective_avg_cost)

        # --- P/L ---
        profit_pct = (current_price - effective_avg_cost) / effective_avg_cost
        drop_pct   = (peak_price - current_price) / peak_price if peak_price else 0

        # --- Trend ---
        if len(prices) >= 7:
            trend = "📈 Trending Up" if current_price > prices[-7] else "📉 Consolidating"
        else:
            trend = "📊 Calculating Trend..."

        # --- Buy & Sell scores ---
        buy_score,  buy_signals  = compute_buy_score(
            current_price, low_30d, avg_30d, prices, peak_price)
        sell_score, sell_signals = compute_sell_score(
            current_price, high_30d, avg_30d, prices)

        buy_badge  = "🟢" if buy_score  >= 4 else "🟡" if buy_score  >= 2 else "⚪"
        sell_badge = "🔴" if sell_score >= 4 else "🟠" if sell_score >= 2 else "⚪"

        buy_detail  = ", ".join(buy_signals)  or "No strong buy signal"
        sell_detail = ", ".join(sell_signals) or "No strong sell signal"

        # --- Primary signal (priority order) ---
        if profit_pct >= RISE_THRESHOLD:
            primary_signal = f"🔴 *Take Profit Zone* — {profit_pct:+.2%} gain reached!"
        elif sell_score >= 4:
            primary_signal = f"🔴 *SELL Zone* — Score {sell_score}/6 ({sell_detail})"
        elif drop_pct >= DROP_THRESHOLD:
            primary_signal = (f"🟢 *BUY Zone* — {drop_pct:.2%} below peak "
                              f"(RM {peak_price:.2f})")
        elif current_price <= min(prices[-7:]):
            primary_signal = "🟢 *Strong BUY zone* — 7-day low"
        elif sell_score >= 2:
            primary_signal = f"🟠 *Watch to Sell* — Score {sell_score}/6 ({sell_detail})"
        elif current_price >= high_30d:
            primary_signal = "⚠️ *Near Resistance* — watch for reversal"
        else:
            primary_signal = "⚖️ Neutral — Hold"

        # --- Change string ---
        change_str = (f"+RM {change:.2f}" if change >= 0
                      else f"-RM {abs(change):.2f}")

        caption = (
            f"📊 *Public Gold Weekly Report*\n\n"
            f"💰 Price:        *RM {current_price:.2f}/g*\n"
            f"🔄 Change:       {change_str}\n"
            f"🏔 30D High:     RM {high_30d:.2f}/g\n"
            f"📉 30D Low:      RM {low_30d:.2f}/g\n"
            f"📊 30D Avg:      RM {avg_30d:.2f}/g\n"
            f"🎯 Avg Cost:     RM {effective_avg_cost:.2f}/g\n"
            f"💹 P/L:          *{profit_pct:+.2%}*\n"
            f"📈 Status:       {trend}\n\n"
            f"─────────────────────\n"
            f"🧠 *Signal*: {primary_signal}\n\n"
            f"{buy_badge} *Buy Score*:   {buy_score}/6\n"
            f"   ↳ {buy_detail}\n\n"
            f"{sell_badge} *Sell Score*:  {sell_score}/6\n"
            f"   ↳ {sell_detail}"
        )

        send_telegram(chart_path, caption)
        print("🚀 Report dispatched!")
        print(caption)

    except Exception as e:
        print(f"❌ Script failed: {e}")


if __name__ == "__main__":
    main()
