import pandas as pd
import requests
from datetime import datetime
import os

# Retrieve JSON data from the API
url = "http://apims.doe.gov.my/data/public_v2/CAQM/last24hours.json"
response = requests.get(url)
data = response.json()  # Parse JSON response

# Assuming you want to work with the '24hour_api_apims' key
data = pd.json_normalize(data['24hour_api_apims'])

# Define the directory where you want to save the data
data_dir = 'data'

# Create the data directory if it doesn't exist
os.makedirs(data_dir, exist_ok=True)

# Get the current date and time
current_datetime = datetime.now()

# Format the date and time for naming the CSV file
file_name = current_datetime.strftime('%Y-%m-%d_%H-%M-%S.csv')
file_path = os.path.join(data_dir, file_name)

# Assuming you want to save the data without duplicates
data.to_csv(file_path, index=False)

print(f'Data has been saved to {file_path}')
