import pandas as pd
import requests
from datetime import datetime
import os
import json
from pytz import timezone
from urllib3.exceptions import MaxRetryError
from requests.exceptions import RequestException

def fetch_data():
    url = "https://www.gso.org.my/SystemData/CurrentGen.aspx/GetChartDataSource"
    data = {
        "Fromdate": datetime.now(timezone('Asia/Kuala_Lumpur')).strftime('%d/%m/%Y'),
        "Todate": datetime.now(timezone('Asia/Kuala_Lumpur')).strftime('%d/%m/%Y')
    }
    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        chartobjdata = json.loads(response.text)["d"]
        return json.loads(chartobjdata)
    except RequestException as e:
        print(f"Request error: {e}")
    except MaxRetryError as e:
        print(f"Max retry error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")

    return None

def flatten_data(chartobjdata):
    flattened_data = []
    for entry in chartobjdata:
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
    return flattened_data

def save_data(flattened_data):
    df = pd.DataFrame(flattened_data)
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date'] = df['datetime'].dt.date
    df['time'] = df['datetime'].dt.time
    df = df.loc[:, ['date', 'time', 'Coal', 'Gas', 'CoGen', 'Oil', 'Hydro', 'Solar']]

    data_dir = 'data_gso'
    os.makedirs(data_dir, exist_ok=True)
    file_name = datetime.now(timezone('Asia/Kuala_Lumpur')).strftime('%Y-%m-%d.csv')
    file_path = os.path.join(data_dir, file_name)

    if os.path.exists(file_path):
        existing_data = pd.read_csv(file_path, header=0)
        combined_data = pd.concat([existing_data, df], ignore_index=True)
        combined_data.to_csv(file_path, index=False)
        print(f'Data has been appended to {file_path}')
    else:
        df.to_csv(file_path, index=False)
        print(f'Data has been saved to {file_path}')

if __name__ == "__main__":
    chartobjdata = fetch_data()
    if chartobjdata:
        flattened_data = flatten_data(chartobjdata)
        save_data(flattened_data)
