import re
import json
import requests
import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.gridspec as gridspec
from datetime import datetime, timedelta
import numpy as np
import yfinance as yf

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Toggle data strategy via env var (set in GitHub Actions or locally).
# "SPOT_YFINANCE"  → GC=F * MYR=X / 31.1035  (reliable, 24/5 data)
# "PUBLIC_GOLD"    → scrape publicgold.me      (local retail price, may be blocked)
DATA_SOURCE = os.getenv("AURUM_DATA_SOURCE", "SPOT_YFINANCE")

RISE_THRESHOLD  = 0.15   # 15% gain  → Take profit alert
DROP_THRESHOLD  = 0.05   # 5% drop   → Buy more alert
PAWNSHOP_SPREAD = 0.03   # fallback ±3% if BNM API unavailable
PEAK_FILE       = "last_peak.txt"
CSV_FILE        = "gold_price_history.csv"


# ---------------------------------------------------------------------------
# 1. DATA FETCHING STRATEGIES
# ---------------------------------------------------------------------------

class SpotYFinanceFetcher:
    """
    Fetches 6 months of gold data via Yahoo Finance.
    Formula: (GC=F USD/oz ÷ 31.1035) × MYR=X  →  RM/gram
    Reliable, continuous 24/5 market data.
    Returns DataFrame with columns: Price, USD_Price, Rate
    """
    def get_data(self) -> pd.DataFrame:
        try:
            gold = yf.Ticker("GC=F").history(period="6mo")
            myr  = yf.Ticker("MYR=X").history(period="6mo")
        except Exception as e:
            raise ConnectionError(f"Failed to fetch from Yahoo Finance: {e}")

        if gold.empty or myr.empty:
            raise ValueError("❌ Empty data returned from Yahoo Finance.")

        df = pd.concat([gold["Close"], myr["Close"]], axis=1)
        df.columns = ["USD_Price", "Rate"]
        df = df.ffill().dropna()

        if df.empty:
            raise ValueError("❌ No overlapping gold/FX data after alignment.")

        df["Price"] = (df["USD_Price"] / 31.1035) * df["Rate"]
        df.index = df.index.tz_localize(None)

        print(f"✅ [SPOT_YFINANCE] {len(df)} points "
              f"({df.index[0].strftime('%d %b')} → {df.index[-1].strftime('%d %b %Y')})")
        return df


class PublicGoldFetcher:
    """
    Scrapes daily local retail price from publicgold.me/yes/gold-price-today.
    Reflects Malaysian retail board price (spreads + duties baked in).
    USD_Price and Rate are unavailable from this source (set to NaN).

    NOTE: This source may return HTTP 403 from GitHub Actions IPs.
    If blocked, set AURUM_DATA_SOURCE=SPOT_YFINANCE in your workflow env.
    """
    URL = "https://publicgold.me/yes/gold-price-today"

    def get_data(self) -> pd.DataFrame:
        headers = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/124.0.0.0 Safari/537.36"),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://publicgold.me/",
        }
        try:
            res = requests.get(self.URL, headers=headers, timeout=15)
            if res.status_code == 403:
                raise ConnectionError(
                    "publicgold.me returned 403 — this host is likely blocked. "
                    "Set AURUM_DATA_SOURCE=SPOT_YFINANCE in your GitHub Actions env."
                )
            res.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"Failed to reach publicgold.me: {e}")

        match = re.search(r"data:\s*\[([\d.,\s]+)\]", res.text)
        if not match:
            raise ValueError(
                "Could not parse price data from publicgold.me — "
                "page layout may have changed."
            )
        prices = json.loads("[" + match.group(1) + "]")
        if len(prices) < 2:
            raise ValueError("Not enough data points from publicgold.me scrape.")

        n = len(prices)
        dates = [
            datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            - timedelta(days=n - 1 - i)
            for i in range(n)
        ]
        df = pd.DataFrame({
            "Price":     prices,
            "USD_Price": float("nan"),
            "Rate":      float("nan"),
        }, index=dates)
        print(f"✅ [PUBLIC_GOLD] {n} points "
              f"({dates[0].strftime('%d %b')} → {dates[-1].strftime('%d %b %Y')})")
        return df


def get_gold_data() -> tuple:
    """Factory: select fetcher from DATA_SOURCE, return (df, source_label)."""
    if DATA_SOURCE == "PUBLIC_GOLD":
        df = PublicGoldFetcher().get_data()
        return df, "Public Gold (retail)"
    elif DATA_SOURCE == "SPOT_YFINANCE":
        df = SpotYFinanceFetcher().get_data()
        return df, "Yahoo Finance (GC=F × MYR=X)"
    else:
        raise ValueError(
            f"Unknown AURUM_DATA_SOURCE='{DATA_SOURCE}'. "
            "Use 'SPOT_YFINANCE' or 'PUBLIC_GOLD'."
        )


# ---------------------------------------------------------------------------
# 2. PAWNSHOP RATES  (BNM Kijang Emas → fallback ±3% spread)
# ---------------------------------------------------------------------------

def get_pawnshop_rates(spot_rm_per_g):
    """
    Returns (sell_to_shop, buy_from_shop, source) in RM/gram.
    sell_to_shop  = what you RECEIVE when selling gold (lower)
    buy_from_shop = what you PAY when buying gold   (higher)
    Primary: BNM Kijang Emas (official MY benchmark, free, no auth)
    Fallback: ±PAWNSHOP_SPREAD on spot
    """
    try:
        r = requests.get(
            "https://api.bnm.gov.my/public/kijang-emas",
            headers={"Accept": "application/vnd.BNM.API.v1+json"},
            timeout=10,
        )
        if r.status_code == 200:
            data     = r.json()["data"]
            oz       = data.get("one_oz", {})
            buy_oz   = oz.get("buying")
            sell_oz  = oz.get("selling")
            eff_date = data.get("effective_date", "today")
            if buy_oz and sell_oz:
                sell_to_shop  = float(buy_oz)  / 31.1035
                buy_from_shop = float(sell_oz) / 31.1035
                source = f"BNM Kijang Emas ({eff_date})"
                print(f"✅ {source}: Sell RM {sell_to_shop:.2f} | Buy RM {buy_from_shop:.2f}/g")
                return sell_to_shop, buy_from_shop, source
    except Exception as e:
        print(f"⚠️  BNM Kijang Emas API unavailable: {e}")

    sell_to_shop  = spot_rm_per_g * (1 - PAWNSHOP_SPREAD)
    buy_from_shop = spot_rm_per_g * (1 + PAWNSHOP_SPREAD)
    source = f"Estimated (±{PAWNSHOP_SPREAD:.0%} spread)"
    print(f"⚠️  Fallback: Sell RM {sell_to_shop:.2f} | Buy RM {buy_from_shop:.2f}/g")
    return sell_to_shop, buy_from_shop, source


# ---------------------------------------------------------------------------
# 3. PEAK PERSISTENCE
# ---------------------------------------------------------------------------

def handle_peak(current_price):
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
# 4. CSV HISTORY EXPORT
# ---------------------------------------------------------------------------

def save_price_csv(df, sell_to_shop, buy_from_shop, rate_source):
    p = df["Price"]
    spot_today  = p.iloc[-1]
    sell_spread = (spot_today - sell_to_shop) / spot_today
    buy_spread  = (buy_from_shop - spot_today) / spot_today
    total_spread_pct = (sell_spread + buy_spread) * 100

    out = pd.DataFrame({
        "date":                   df.index.strftime("%Y-%m-%d"),
        "price_rm_per_g":         p.round(4),
        "price_usd_per_oz":       df["USD_Price"].round(4),
        "usd_myr_rate":           df["Rate"].round(4),
        "pawnshop_sell_rm_per_g": (p * (1 - sell_spread)).round(4),
        "pawnshop_buy_rm_per_g":  (p * (1 + buy_spread)).round(4),
        "pawnshop_spread_pct":    round(total_spread_pct, 4),
        "pawnshop_rate_source":   rate_source,
        "daily_change_rm":        p.diff().round(4),
        "daily_change_pct":       (p.pct_change() * 100).round(4),
        "ma_7d":                  p.rolling(7,  min_periods=1).mean().round(4),
        "ma_30d":                 p.rolling(30, min_periods=1).mean().round(4),
        "high_30d":               p.rolling(30, min_periods=1).max().round(4),
        "low_30d":                p.rolling(30, min_periods=1).min().round(4),
        "pct_from_30d_high":      ((p - p.rolling(30, min_periods=1).max())
                                   / p.rolling(30, min_periods=1).max() * 100).round(4),
    })
    out.to_csv(CSV_FILE, index=False)
    print(f"✅ CSV saved: {CSV_FILE} ({len(out)} rows, spread {total_spread_pct:.2f}%)")
    return CSV_FILE


# ---------------------------------------------------------------------------
# 5. PROJECTION (linear trend, next 30 days)
# ---------------------------------------------------------------------------

def generate_projection(df):
    last_date = df.index[-1]
    window = df["Price"].values[-20:]
    x = np.arange(len(window))
    slope, intercept = np.polyfit(x, window, 1)
    future_x = np.arange(len(window), len(window) + 30)
    future_y = slope * future_x + intercept
    proj_dates = [last_date + timedelta(days=i) for i in range(1, 31)]
    return pd.DataFrame({"Price": future_y}, index=proj_dates)


# ---------------------------------------------------------------------------
# 6. BUY SIGNAL SCORING  (max 6 pts)
# ---------------------------------------------------------------------------

def compute_buy_score(current_price, low_30d, avg_30d, prices, peak_price):
    score, signals = 0, []

    proximity_to_low = (current_price - low_30d) / low_30d * 100
    if proximity_to_low <= 1.5:
        score += 2
        signals.append(f"📉 Near 30D Low (+{proximity_to_low:.1f}%)")

    below_avg = (avg_30d - current_price) / avg_30d * 100
    if below_avg >= 2.0:
        score += 1
        signals.append(f"📊 Below 30D Avg ({below_avg:.1f}%)")

    if len(prices) >= 7 and current_price <= min(prices[-7:]):
        score += 2
        signals.append("🟢 7D Low")

    drop_pct = (peak_price - current_price) / peak_price if peak_price else 0
    if drop_pct >= DROP_THRESHOLD:
        score += 1
        signals.append(f"⬇️ {drop_pct:.1%} below peak")

    return score, signals


# ---------------------------------------------------------------------------
# 7. SELL SIGNAL SCORING  (max 6 pts)
# ---------------------------------------------------------------------------

def compute_sell_score(current_price, high_30d, avg_30d, prices):
    score, signals = 0, []

    proximity_to_high = (high_30d - current_price) / high_30d * 100
    if proximity_to_high <= 1.5:
        score += 2
        signals.append(f"🏔 Near 30D High ({proximity_to_high:.1f}% away)")

    above_avg = (current_price - avg_30d) / avg_30d * 100
    if above_avg >= 3.0:
        score += 1
        signals.append(f"📈 Above 30D Avg (+{above_avg:.1f}%)")

    if len(prices) >= 3:
        last3 = prices[-3:]
        if last3[-1] < last3[-2] > last3[-3]:
            score += 2
            signals.append("⛰️ Peak Reversal Detected")

    if len(prices) >= 7 and current_price >= max(prices[-7:]):
        score += 1
        signals.append("🔴 7D High")

    return score, signals


# ---------------------------------------------------------------------------
# 8. CHART  (2-panel: price + daily % change bars)
# ---------------------------------------------------------------------------

def create_chart(df, proj_df, current_price, avg_cost,
                 sell_to_shop, buy_from_shop,
                 peak_price, usd_price,
                 usd_myr_rate, source_label):

    fig = plt.figure(figsize=(13, 8))
    fig.patch.set_facecolor("#0f0f0f")
    gs = gridspec.GridSpec(2, 1, figure=fig, height_ratios=[7, 3], hspace=0.06)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    # ── Panel 1: Price ──────────────────────────────────────────────────────────────────────────
    ax1.set_facecolor("#1a1a2e")

    # Pawnshop band + lines
    ax1.axhspan(sell_to_shop, buy_from_shop, alpha=0.07, color="#AAAAAA", zorder=1)
    ax1.axhline(sell_to_shop,  color="#00CC44", linestyle="--", linewidth=1.0,
                alpha=0.85, zorder=2, label=f"Sell RM {sell_to_shop:.2f}")
    ax1.axhline(buy_from_shop, color="#FF4455", linestyle="--", linewidth=1.0,
                alpha=0.85, zorder=2, label=f"Buy  RM {buy_from_shop:.2f}")

    # Moving averages
    ma7  = df["Price"].rolling(7,  min_periods=1).mean()
    ma30 = df["Price"].rolling(30, min_periods=1).mean()
    ax1.plot(df.index, ma7,  color="#00BFFF", linewidth=1.1, alpha=0.75,
             zorder=3, label="MA 7d")
    ax1.plot(df.index, ma30, color="#FF8C00", linewidth=1.1, alpha=0.75,
             zorder=3, label="MA 30d")

    # Gold price + fill
    ax1.plot(df.index, df["Price"], color="#DAA520", linewidth=2.5,
             zorder=4, label="Gold Spot (RM/g)")
    ax1.fill_between(df.index, df["Price"], color="#DAA520", alpha=0.08, zorder=1)

    # Projection
    ax1.plot(proj_df.index, proj_df["Price"], color="#FFD700", linestyle="--",
             linewidth=1.5, alpha=0.65, zorder=3, label="Projection 30d")

    # Avg cost + peak
    ax1.axhline(avg_cost, color="#00FF88", linestyle=":", linewidth=1.3,
                alpha=0.7, zorder=2, label=f"Avg Cost RM {avg_cost:.2f}")
    ax1.axhline(peak_price, color="#FF6600", linestyle=":", linewidth=1.0,
                alpha=0.55, zorder=2, label=f"Peak RM {peak_price:.2f}")

    # Current price dot + right-side label
    ax1.scatter([df.index[-1]], [current_price], color="#FFD700", s=90, zorder=6)
    ax1.annotate(
        f"  RM {current_price:.2f}",
        xy=(df.index[-1], current_price),
        xytext=(6, 0), textcoords="offset points",
        color="#FFD700", fontsize=9, fontweight="bold", va="center", zorder=7,
    )

    # Info box — top-left
    usd_str  = f"${usd_price:,.2f}/oz" if not np.isnan(usd_price) else "n/a"
    rate_str = f"{usd_myr_rate:.4f}" if not np.isnan(usd_myr_rate) else "n/a"
    info = (f"Source : {source_label}\n"
            f"Gold   : {usd_str}\n"
            f"USD/MYR: {rate_str}\n"
            f"Time   : {datetime.now().strftime('%d %b %Y %H:%M')}")
    ax1.text(
        0.012, 0.975, info, transform=ax1.transAxes,
        fontsize=7.5, va="top", color="#cccccc", family="monospace",
        bbox=dict(boxstyle="round,pad=0.45", facecolor="#0d0d1a",
                  edgecolor="#444466", alpha=0.88),
    )

    ax1.set_title("AurumVibe — Gold Price Monitor (RM/g)",
                  color="white", fontsize=12, pad=10)
    ax1.set_ylabel("Price (RM/gram)", color="#cccccc", fontsize=9)
    ax1.tick_params(colors="#888888", labelsize=8)
    ax1.grid(True, alpha=0.12, color="#444444")
    ax1.legend(facecolor="#151525", labelcolor="white", fontsize=7.5,
               loc="lower left", ncol=4, framealpha=0.85)
    plt.setp(ax1.get_xticklabels(), visible=False)

    # ── Panel 2: Daily % change bars ───────────────────────────────────────────────────────────────────────
    ax2.set_facecolor("#111122")
    daily_pct = df["Price"].pct_change() * 100
    bar_colors = ["#00CC44" if v >= 0 else "#FF4455" for v in daily_pct.fillna(0)]
    ax2.bar(df.index, daily_pct.fillna(0), color=bar_colors, alpha=0.75, width=0.9)
    ax2.axhline(0, color="#555566", linewidth=0.8)
    ax2.set_ylabel("Day %", color="#aaaaaa", fontsize=8)
    ax2.tick_params(colors="#888888", labelsize=7)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax2.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    ax2.grid(True, alpha=0.10, color="#333333", axis="y")

    fig.autofmt_xdate(rotation=28, ha="right")

    chart_path = "gold_report.png"
    plt.savefig(chart_path, dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    return chart_path


# ---------------------------------------------------------------------------
# 9. TELEGRAM
# ---------------------------------------------------------------------------

def send_telegram(chart_path, caption):
    if not TOKEN or not CHAT_ID:
        print("⚠️  TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set — skipping.")
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    try:
        with open(chart_path, "rb") as photo:
            resp = requests.post(
                url,
                data={"chat_id": CHAT_ID, "caption": caption, "parse_mode": "Markdown"},
                files={"photo": photo},
                timeout=20,
            )
        if resp.status_code != 200:
            print(f"❌ Telegram Error {resp.status_code}: {resp.text}")
        else:
            print("✅ Telegram message sent successfully!")
    except Exception as e:
        print(f"❌ Telegram connection error: {e}")


def send_telegram_text(text):
    if not TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": text,
                                 "parse_mode": "Markdown"}, timeout=15)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 10. MAIN
# ---------------------------------------------------------------------------

def main():
    try:
        # --- Data ---
        df, source_label = get_gold_data()
        prices       = df["Price"].tolist()
        current_price = prices[-1]
        prev_price    = prices[-2] if len(prices) > 1 else current_price
        change        = current_price - prev_price
        usd_price     = df["USD_Price"].iloc[-1]
        usd_myr_rate  = df["Rate"].iloc[-1]

        # --- Pawnshop rates ---
        sell_to_shop, buy_from_shop, rate_source = get_pawnshop_rates(current_price)

        # --- CSV ---
        save_price_csv(df, sell_to_shop, buy_from_shop, rate_source)

        # --- 30D stats ---
        window_30 = prices[-30:] if len(prices) >= 30 else prices
        high_30d  = max(window_30)
        low_30d   = min(window_30)
        avg_30d   = sum(window_30) / len(window_30)
        effective_avg_cost = (high_30d + low_30d) / 2

        # --- Peak ---
        peak_price = handle_peak(current_price)

        # --- Projection & Chart ---
        proj_df    = generate_projection(df)
        chart_path = create_chart(
            df, proj_df, current_price, effective_avg_cost,
            sell_to_shop, buy_from_shop, peak_price,
            usd_price, usd_myr_rate, source_label,
        )

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

        # --- Primary signal ---
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
        send_telegram_text(f"⚠️ *AurumVibe Error*\nGold monitor failed:\n`{e}`")


if __name__ == "__main__":
    main()
