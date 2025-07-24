import pandas as pd
import requests
from datetime import datetime, timedelta
import os
import warnings
from pytz import timezone
from urllib3.exceptions import MaxRetryError, ConnectionError
from requests.exceptions import RequestException

# For robust retries
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Suppress SSL warnings when using verify=False (use with caution in production)
warnings.filterwarnings("ignore")

# Define the Malaysia timezone (UTC+8)
malaysia_timezone = timezone('Asia/Kuala_Lumpur')

# API URL for hourly data
url = "https://eqms.doe.gov.my/api3/publicportalapims/apitablehourly"

try:
    # Set headers to mimic a browser request
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Configure requests session with retries for network resilience
    session = requests.Session()
    # Retry configuration: 3 retries on connection errors, exponential backoff, retry on specific HTTP status codes
    retry = Retry(connect=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    session.mount('http://', adapter)

    # Use GET request. verify=False is used due to potential SSL certificate issues on the API side.
    # A timeout is set to prevent indefinite waiting.
    response = session.get(url, headers=headers, verify=False, timeout=10)
    response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)

    # Process JSON response
    payload = response.json()
    
    # Safely normalize the JSON payload.
    # Added specific error handling for KeyError if 'api_table_hourly' is not found.
    try:
        df = pd.json_normalize(payload, record_path=['api_table_hourly'])
    except KeyError:
        print("Error: 'api_table_hourly' key not found in the API response. Check API structure.")
        exit(1) # Exit the script if the expected key is missing

    # Keep only the essential columns for the report
    df = df[['STATION_LOCATION', 'DATETIME', 'API']]

    # Split 'STATION_LOCATION' into 'Location' and 'State' for better organization
    df[['Location', 'State']] = df['STATION_LOCATION'].str.split(', ', expand=True)

    # Convert 'DATETIME' column to datetime objects for time-based operations
    df['DATETIME'] = pd.to_datetime(df['DATETIME'])

    # Extract hour and date in desired formats
    df['hour'] = df['DATETIME'].dt.strftime('%I:00%p') # e.g., "01:00AM", "11:00PM"
    df['date'] = df['DATETIME'].dt.date # Extracts only the date part

    # Get current time in Malaysia timezone for comparison
    current_dt = datetime.now(malaysia_timezone)
    current_date = current_dt.date()
    current_hour = current_dt.hour

    # Fix midnight crossover issue:
    # If the script runs late in the day (e.g., 11 PM) and the API returns data
    # for "tomorrow's" early hours (e.g., 1 AM), adjust the date back by one day.
    df['hour_int'] = df['DATETIME'].dt.hour
    mask = (df['hour_int'] > current_hour) & (df['date'] == current_date)
    df.loc[mask, 'date'] = df.loc[mask, 'date'] - timedelta(days=1)
    df.drop(columns=['hour_int'], inplace=True) # Remove the temporary 'hour_int' column

    # Rename 'API' column to 'index' for clarity based on common usage
    df.rename(columns={'API': 'index'}, inplace=True)

    # Reorder columns to the desired sequence
    df = df[['State', 'Location', 'hour', 'index', 'date']]

    # Create a copy of the processed DataFrame and convert 'date' to string for saving
    data = df.copy()
    data['date'] = data['date'].astype(str)

    # Define the directory where data files will be stored
    data_dir = 'data_apims'
    # Create the directory if it doesn't already exist
    os.makedirs(data_dir, exist_ok=True)

    # Prepare the file path for the current day's data
    file_name = current_dt.strftime('%Y-%m-%d.csv')
    file_path = os.path.join(data_dir, file_name)

    # Check if the file already exists to decide whether to append or create new
    if os.path.exists(file_path):
        # Read existing data, concatenate with new data, remove duplicates, and save
        existing_data = pd.read_csv(file_path, header=0)
        combined_data = pd.concat([existing_data, data], ignore_index=True)
        combined_data = combined_data.drop_duplicates()
        combined_data.to_csv(file_path, index=False)
        print(f'Data has been appended to {file_path}')
    else:
        # If file doesn't exist, save the new data directly
        data.to_csv(file_path, index=False)
        print(f'Data has been saved to {file_path}')

# Catch various request-related exceptions for robust error reporting
except (RequestException, ConnectionError, MaxRetryError) as e:
    print(f"An error occurred while fetching data: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

