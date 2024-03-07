import pandas as pd
import requests
from datetime import datetime
import os
import json
from pytz import timezone
from urllib3.exceptions import MaxRetryError, ConnectionError
from requests.exceptions import RequestException

try:
    url = "https://www.gso.org.my/SystemData/CurrentGen.aspx/GetChartDataSource"

    data = {
        "Fromdate": datetime.now().strftime('%d/%m/%Y'),
        "Todate": datetime.now().strftime('%d/%m/%Y')
    }

    headers = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}


    response = requests.post(url, json=data, headers=headers)


    if response.status_code == 200:
        chartobjdata = json.loads(response.text)["d"]

        # Convert the data to a list of dictionaries
        chartobjdata_list = json.loads(chartobjdata)

        # Manually flatten the JSON data
        flattened_data = []
        for entry in chartobjdata_list:
            flattened_entry = {
                "datetime": entry["DT"],
                "Coal": entry["Coal"],
                "Gas": entry["Gas"],
                "CoGen": entry["CoGen"],
                "Oil": entry["Oil"],
                "Hydro": entry["Hydro"],
                "Solar": entry["Solar"]
            }
            flattened_data.append(flattened_entry)

        # Convert flattened data to DataFrame
        df = pd.DataFrame(flattened_data)
        df['datetime'] = pd.to_datetime(df['datetime'])

        # Split "datetime" into "date" and "time" columns
        df['date'] = df['datetime'].dt.date
        df['time'] = df['datetime'].dt.time

        # Select specific columns
        df = df.loc[:, ['date', 'time', 'Coal', 'Gas', 'CoGen', 'Oil', 'Hydro', 'Solar']]

        # print(df)  # Add a print statement to display the resulting DataFrame

        # Save data to CSV using flattened_data
        data_dir = 'data_gso'
        os.makedirs(data_dir, exist_ok=True)

        # current_datetime = datetime.now(malaysia_timezone)
        # data['date'] = current_datetime.strftime('%Y-%m-%d')

        file_date = datetime.today()  # Corrected function name
        file_name = file_date.strftime('%Y-%m-%d.csv')
        file_path = os.path.join(data_dir, file_name)

        if os.path.exists(file_path):
            existing_data = pd.read_csv(file_path, header=0)
            combined_data = pd.concat([existing_data, df], ignore_index=True)
            combined_data.to_csv(file_path, index=False)
            print(f'Data has been appended to {file_path}')
        else:
            df.to_csv(file_path, index=False)
            print(f'Data has been saved to {file_path}')

    else:
        print("Error: Unable to retrieve chart data. Status Code:", response.status_code)

except (RequestException, ConnectionError, MaxRetryError) as e:
    print(f"An error occurred: {e}")
    # You can add further error handling or logging here.
