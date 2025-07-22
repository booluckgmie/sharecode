import pandas as pd
import requests
from datetime import datetime, timedelta
import os
from pytz import timezone
from urllib3.exceptions import MaxRetryError, ConnectionError
from requests.exceptions import RequestException

# Define the Malaysia timezone (UTC+8)
malaysia_timezone = timezone('Asia/Kuala_Lumpur')

try:
    # Retrieve JSON data from the API
    r = requests.get("https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly")
    r.raise_for_status()  # Check for HTTP errors
    payload = r.json()
    df = pd.json_normalize(payload, record_path=['api_table_hourly'])

    df = df[['STATION_LOCATION', 'DATETIME', 'API']]
    
    # Split STATION_LOCATION into Location and State
    df[['Location', 'State']] = df['STATION_LOCATION'].str.split(', ', expand=True)
    
    # Convert DATETIME column to datetime type
    df['DATETIME'] = pd.to_datetime(df['DATETIME'])
    
    # Extract hour in 12-hour format with AM/PM
    df['hour'] = df['DATETIME'].dt.strftime('%I:00%p')
    
    # Extract date
    df['date'] = df['DATETIME'].dt.date
    
    # Rename API to index
    df.rename(columns={'API': 'index'}, inplace=True)
    
    # Reorder columns
    df = df[['State', 'Location', 'hour', 'index', 'date']]

    data = df.copy()

    data_dir = 'data_apims'
    os.makedirs(data_dir, exist_ok=True)

    current_datetime = datetime.now(malaysia_timezone)
    data['date'] = current_datetime.strftime('%Y-%m-%d')

    file_date = current_datetime
    file_name = file_date.strftime('%Y-%m-%d.csv')
    file_path = os.path.join(data_dir, file_name)

    if os.path.exists(file_path):
        existing_data = pd.read_csv(file_path, header=0)
        combined_data = pd.concat([existing_data, data], ignore_index=True)
        combined_data.to_csv(file_path, index=False)
        print(f'Data has been appended to {file_path}')
    else:
        data.to_csv(file_path, index=False)
        print(f'Data has been saved to {file_path}')

except (RequestException, ConnectionError, MaxRetryError) as e:
    print(f"An error occurred: {e}")
    # You can add further error handling or logging here.
