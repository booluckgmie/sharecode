import requests
from bs4 import BeautifulSoup
import re
import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

# --- Configuration ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
try:
    AVG_COST = float(os.getenv("AVG_COST", "320.0"))
except:
    AVG_COST = 320.0

def get_public_gold_data():
    url = "https://publicgold.me/yes/gold-price-today"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers).text
    
    # 1. Extract the JS Chart Data (Price Series)
    # This regex looks for the 'data: [ ... ]' pattern in the script tags
    match = re.search(r'data:\s*\[(.*?)\]', res)
    
    if match:
        data_str = "[" + match.group(1) + "]"
        prices = json.loads(data_str)
        
        # Create a basic dataframe for the last 30 entries
        # Note: Scraped data usually doesn't have dates in the array, 
        # so we generate them backwards from today.
        df = pd.DataFrame({'Price': prices})
        df.index = [datetime.now() - timedelta(days=len(prices)-1-i) for i in range(len(prices))]
        return df
    else:
        raise ValueError("Could not find price data on Public Gold page")

def create_chart(df):
    plt.figure(figsize=(10, 5))
    plt.plot(df.index, df['Price'], color='#DAA520', linewidth=2, label='Public Gold Price')
    plt.fill_between(df.index, df['Price'], color='#DAA520', alpha=0.1)
    
    plt.title(f"Public Gold Price Trend (RM/g) - {datetime.now().strftime('%d %b %Y')}")
    plt.ylabel("RM per gram")
    plt.grid(True, alpha=0.2)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    
    chart_path = "gold_report.png"
    plt.savefig(chart_path)
    plt.close()
    return chart_path

def send_telegram(chart_path, caption):
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    with open(chart_path, 'rb') as photo:
        payload = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'Markdown'}
        files = {'photo': photo}
        requests.post(url, data=payload, files=files)

def main():
    try:
        df = get_public_gold_data()
        prices = df['Price'].tolist()
        
        current_price = prices[-1]
        prev_price = prices[-2] if len(prices) > 1 else current_price
        change = current_price - prev_price
        
        high_30d = max(prices)
        low_30d = min(prices)
        
        # --- Logic & Signals ---
        profit_pct = (current_price - AVG_COST) / AVG_COST
        
        signal = "⚖️ Neutral - Hold"
        # 🟢 BUY Alert (Current price is lowest in last 7 days)
        if current_price <= min(prices[-7:]):
            signal = "🟢 Strong BUY zone (7-day low)"
        # 🔴 SELL Alert (Based on your 15% profit target)
        elif profit_pct >= 0.15:
            signal = "🔴 Take Profit Zone (+15% gain reached)"
        elif current_price >= high_30d:
            signal = "⚠️ Near Resistance - Watch for reversal"

        change_str = f"+RM{change}" if change >= 0 else f"-RM{abs(change)}"
        
        caption = (
            f"📊 *Public Gold Update*\n\n"
            f"💰 Price: *RM {current_price}/g*\n"
            f"📉 Change: {change_str}\n"
            f"📈 30D High: RM {high_30d}\n"
            f"📉 30D Low: RM {low_30d}\n"
            f"💰 Avg Cost: RM {AVG_COST}\n"
            f"📈 P/L: {profit_pct:+.2%}\n\n"
            f"🧠 *Signal*:\n- {signal}"
        )

        chart_path = create_chart(df)
        send_telegram(chart_path, caption)
        print("✅ Public Gold Report Sent!")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
