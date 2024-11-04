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
    r = requests.get("http://apims.doe.gov.my/data/public_v2/CAQM/last24hours.json")
    r.raise_for_status()  # Check for HTTP errors

    payload = r.json()

    data = pd.json_normalize(payload, record_path=['24hour_api_apims'])
    data.columns = data.iloc[0]

    data = data[1:]
    data = data.iloc[:, [0, 1, -1]]
    data = data.melt(id_vars=['State', 'Location'], var_name='hour', value_name='index')

    data["index"] = data["index"].str.replace(r'[&*c]', '', regex=True)

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
