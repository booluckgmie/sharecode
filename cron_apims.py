import pandas as pd
import requests
from datetime import datetime, timedelta
import os
import warnings
from pytz import timezone
from urllib3.exceptions import MaxRetryError, ConnectionError
from requests.exceptions import RequestException

# Suppress SSL warnings when using verify=False
warnings.filterwarnings("ignore")

# Define the Malaysia timezone (UTC+8)
malaysia_timezone = timezone('Asia/Kuala_Lumpur')

# API URL
url = "https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly"

try:
    # Set headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Use GET request with verify=False due to SSL issues
    response = requests.get(url, headers=headers, verify=False)
    response.raise_for_status()

    # Process JSON response
    payload = response.json()
    df = pd.json_normalize(payload, record_path=['api_table_hourly'])

    # Keep only required columns
    df = df[['STATION_LOCATION', 'DATETIME', 'API']]

    # Split STATION_LOCATION into Location and State
    df[['Location', 'State']] = df['STATION_LOCATION'].str.split(', ', expand=True)

    # Convert DATETIME column to datetime type
    df['DATETIME'] = pd.to_datetime(df['DATETIME'])

    # Extract hour in 12-hour format with AM/PM
    df['hour'] = df['DATETIME'].dt.strftime('%I:00%p')

    # Extract date
    df['date'] = df['DATETIME'].dt.date

    # Adjust date for hours past midnight but ahead of current time
    current_hour_str = datetime.now(malaysia_timezone).strftime('%I:00%p')
    df['hour_dt'] = pd.to_datetime(df['hour'], format='%I:%M%p').dt.time
    current_hour_dt = pd.to_datetime(current_hour_str, format='%I:%M%p').time()
    df.loc[(df['hour_dt'] > current_hour_dt), 'date'] = df['date'] - timedelta(days=1)
    df.drop(columns=['hour_dt'], inplace=True)

    # Rename API to index
    df.rename(columns={'API': 'index'}, inplace=True)

    # Reorder columns
    df = df[['State', 'Location', 'hour', 'index', 'date']]

    # Create data copy
    data = df.copy()

    # Prepare data directory
    data_dir = 'data_apims'
    os.makedirs(data_dir, exist_ok=True)

    # Current datetime in Malaysia timezone
    current_datetime = datetime.now(malaysia_timezone)
    data['date'] = data['date'].astype(str)

    # Prepare file path
    file_name = current_datetime.strftime('%Y-%m-%d.csv')
    file_path = os.path.join(data_dir, file_name)

    # Save or append data
    if os.path.exists(file_path):
        existing_data = pd.read_csv(file_path, header=0)
        combined_data = pd.concat([existing_data, data], ignore_index=True)
        combined_data = combined_data.drop_duplicates()
        combined_data.to_csv(file_path, index=False)
        print(f'Data has been appended to {file_path}')
    else:
        data.to_csv(file_path, index=False)
        print(f'Data has been saved to {file_path}')

except (RequestException, ConnectionError, MaxRetryError) as e:
    print(f"An error occurred: {e}")
