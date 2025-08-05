import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import os

def scrape_today(year):
    url = f"https://bepi.mpob.gov.my/admin2/price_local_daily_view_cpo_msia.php?more=Y&jenis=1Y&tahun={year}"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    table = soup.find("tbody")
    rows = table.find_all("tr")

    months = []
    for row in rows:
        if row.find_all("td") and "Date" in row.get_text():
            months = [td.get_text(strip=True) for td in row.find_all("td")[1:]]
            break

    data = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) == 13 and cols[0].get_text(strip=True).isdigit():
            day = cols[0].get_text(strip=True).zfill(2)
            for i, value_td in enumerate(cols[1:], start=0):
                value = value_td.get_text(strip=True).replace(",", "")
                if value not in ['-', '']:
                    record = {
                        "year": year,
                        "month": months[i],
                        "day": day,
                        "price": value
                    }
                    data.append(record)

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["day"] + " " + df["month"] + " " + df["year"].astype(str), errors='coerce', dayfirst=True)
    df = df.dropna(subset=["date"])
    df["price"] = df["price"].apply(lambda x: x if x in ["PH", "NT"] else float(x))
    return df[["date", "price"]]

def prices_are_equal(price1, price2):
    """Compare two prices, handling different data types properly"""
    # Convert both to string for comparison to handle mixed types
    return str(price1) == str(price2)

def update_csv():
    if datetime.now().hour < 10:
        return  # Run only after 10 AM

    year = datetime.now().year
    df_scraped = scrape_today(year)
    csv_file = "cpo_daily_prices.csv"

    if os.path.exists(csv_file):
        df_existing = pd.read_csv(csv_file, parse_dates=["date"])
    else:
        df_existing = pd.DataFrame(columns=["date", "price"])

    df_existing.set_index("date", inplace=True)
    df_scraped.set_index("date", inplace=True)

    changes = []

    # Detect updates (date exists and price changed)
    common_dates = df_scraped.index.intersection(df_existing.index)
    for date in common_dates:
        new_price = df_scraped.loc[date, "price"]
        old_price = df_existing.loc[date, "price"]
        # Only add to changes if prices are actually different
        if not prices_are_equal(old_price, new_price):
            df_existing.loc[date, "price"] = new_price
            changes.append((date.date(), old_price, new_price))

    # Detect new additions
    new_dates = df_scraped.index.difference(df_existing.index)
    for date in new_dates:
        new_price = df_scraped.loc[date, "price"]
        df_existing.loc[date] = new_price
        changes.append((date.date(), None, new_price))

    # Save updated file
    df_existing.sort_index().reset_index().to_csv(csv_file, index=False)

    # Print only actual changes
    for date, old, new in changes:
        print(f"{date} updated: {old} → {new}")

# Run it
update_csv()