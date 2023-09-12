import pandas as pd
import requests
from datetime import datetime, timedelta
import os

# Retrieve JSON data from the API
r = requests.get("http://apims.doe.gov.my/data/public_v2/CAQM/last24hours.json")
payload = r.json()  # Parse `response.text` into JSON

data = pd.json_normalize(payload, record_path=['24hour_api_apims'])
# Set the first row as the header
data.columns = data.iloc[0]

# Drop the first row (if needed)
data = data[1:]

# # Melt the data to keep only specific columns
data = data.melt(id_vars=['State', 'Location'], var_name='hour', value_name='index')
# Remove specific characters from the "value" column using regex
data["index"] = data["index"].str.replace(r'[&*c]', '', regex=True)

# Define the directory where you want to save the data
data_dir = 'data_apims'

# Create the data directory if it doesn't exist
os.makedirs(data_dir, exist_ok=True)

# Get the current date and time
current_datetime = datetime.now()

# Calculate the date for naming the CSV file
file_date = current_datetime
file_name = file_date.strftime('%Y-%m-%d.csv')
file_path = os.path.join(data_dir, file_name)

# Check if the CSV file already exists
if os.path.exists(file_path):
    # Load the existing data from the CSV file and set the first row as the header
    existing_data = pd.read_csv(file_path, header=0)

    # Append the new data to the existing data
    combined_data = pd.concat([existing_data, data], ignore_index=True)

    # Save the combined data to the CSV file
    combined_data.to_csv(file_path, index=False)
    print(f'Data has been appended to {file_path}')
else:
    # Save the data to the CSV file (create a new file if it doesn't exist)
    data.to_csv(file_path, index=False)
    print(f'Data has been saved to {file_path}')
