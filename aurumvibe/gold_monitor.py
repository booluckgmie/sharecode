import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import requests
import os
from datetime import timedelta, datetime
import numpy as np

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DROP_THRESHOLD = 0.05  # 5% alert
BASE_PRICE_FILE = "last_peak.txt"

def get_data():
    # Fetch Gold (GC=F is Gold Futures, XAUUSD=X is Spot)
    gold = yf.Ticker("GC=F").history(period="120d")
    # Fetch USD/MYR
    currency = yf.Ticker("MYR=X").history(period="120d")
    
    df = pd.DataFrame({
        'USD_Price': gold['Close'],
        'Rate': currency['Close']
    }).dropna()
    
    # Calculate RM per Gram: (Price per Ounce / 31.1035) * Exchange Rate
    df['MYR_Gram'] = (df['USD_Price'] / 31.1035) * df['Rate']
    return df

def generate_projection(df):
    # Naive Projection: Moving average trend for the next 30 days
    last_date = df.index[-1]
    projection_dates = [last_date + timedelta(days=i) for i in range(1, 31)]
    
    # Simple linear trend calculation
    y = df['MYR_Gram'].values[-20:] # Last 20 days
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    
    future_x = np.arange(len(y), len(y) + 30)
    future_y = slope * future_x + intercept
    
    proj_df = pd.DataFrame({'MYR_Gram': future_y}, index=projection_dates)
    return proj_df

def create_chart(df, proj_df):
    plt.figure(figsize=(12, 6))
    
    # Historical
    plt.plot(df.index[-90:], df['MYR_Gram'].iloc[-90:], color='#1f77b4', linewidth=2, label='Historical (3M)')
    
    # Projection
    plt.plot(proj_df.index, proj_df['MYR_Gram'], color='#DAA520', linestyle='--', linewidth=2, label='Projection (1M)')
    
    plt.title(f"Gold Price Trend & Projection (RM/gram) - {datetime.now().strftime('%d %b %Y')}")
    plt.ylabel("Price (MYR/gram)")
    plt.grid(True, alpha=0.3)
    plt.legend()
    
    # Formatting
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.tight_layout()
    
    chart_path = "gold_report.png"
    plt.savefig(chart_path)
    return chart_path

def handle_peak(current_price):
    # 1. Load existing peak
    try:
        with open("last_peak.txt", "r") as f:
            peak = float(f.read().strip())
    except FileNotFoundError:
        peak = current_price # Initialize if file doesn't exist

    # 2. Update if new peak is reached
    if current_price > peak:
        peak = current_price
        with open("last_peak.txt", "w") as f:
            f.write(f"{peak:.2f}")
    
    return peak
    
def send_telegram(chart_path, message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(chart_path, 'rb') as photo:
        payload = {'chat_id': CHAT_ID, 'caption': message, 'parse_mode': 'Markdown'}
        files = {'photo': photo}
        requests.post(url, data=payload, files=files)

# --- New Configuration for Selling ---
RISE_THRESHOLD = 0.15   # 15% gain - Alert to take profit
AVG_COST = 320.0        # Replace with your actual average buy price (RM/g)
DROP_THRESHOLD = 0.05   # 5% drop - Alert to buy more

def main():
    df = get_data()
    proj_df = generate_projection(df)
    chart_path = create_chart(df, proj_df)
    
    current_price = df['MYR_Gram'].iloc[-1]
    peak_price = df['MYR_Gram'].max()
    
    # Logic for Alerts
    drop_pct = (peak_price - current_price) / peak_price
    profit_pct = (current_price - AVG_COST) / AVG_COST
    
    status = "📈 Trending Up" if current_price > df['MYR_Gram'].iloc[-7] else "📉 Consolidating"
    alert_msg = ""
    
    # 🚨 BUY ALERT (Price Drop)
    if drop_pct >= DROP_THRESHOLD:
        alert_msg += f"\n\n🟢 *BUY ALERT*: Price is {drop_pct:.2%} below recent peak! Good time to top up."

    # 🚨 SELL ALERT (Profit Target Reached)
    if profit_pct >= RISE_THRESHOLD:
        alert_msg += f"\n\n🔴 *SELL ALERT*: You are {profit_pct:.2%} in profit! Consider taking partial gains."

    caption = (
        f"📊 *Weekly Gold Report*\n"
        f"Current: *RM {current_price:.2f}/g*\n"
        f"Your Avg Cost: *RM {AVG_COST:.2f}/g*\n"
        f"Current P/L: *{profit_pct:+.2%}*\n"
        f"Status: {status}{alert_msg}"
    )
    
    send_telegram(chart_path, caption)

if __name__ == "__main__":
    main()
