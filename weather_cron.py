import os
import requests
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from pytz import timezone
from urllib3.exceptions import MaxRetryError  
import time

def fetch_weather_data(city, current_date):
    latitude = city['latitude']
    longitude = city['longitude']
    url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&hourly=temperature_2m,relativehumidity_2m,rain,weathercode,windspeed_10m&current_weather=true&timezone=Asia%2FKuala_Lumpur&start_date={current_date}&end_date={current_date}"
    
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.get(url, timeout=30)  # Set timeout to 30 seconds
            response.raise_for_status()  # Raise an error for bad responses
            return response.json()
        except requests.Timeout:
            print(f"Timeout occurred for {city['city']}. Attempt {attempt + 1} of {retries}.")
            time.sleep(2)  # Wait before retrying
        except requests.RequestException as e:
            print(f"Request error for {city['city']}: {e}")
            break
    return None

try:
    hourly_data_list = []

    cityMY = pd.read_csv('./data_weatherUO/cityMY.csv')
    cities = cityMY.to_dict(orient='records')
    wmo = pd.read_csv('./data_weatherUO/wmo_code.csv', sep=';')

    # Get current time in Malaysia/Kuala_Lumpur timezone
    malaysia_timezone = timezone('Asia/Kuala_Lumpur')
    current_datetime = datetime.now(malaysia_timezone)
    current_date = current_datetime.strftime('%Y-%m-%d')

    # Use tqdm to create a progress bar
    for city in tqdm(cities, desc="Processing Cities", total=len(cities)):
        data = fetch_weather_data(city, current_date)
        if data and "hourly" in data:
            hourly = data["hourly"]

            df = pd.DataFrame(hourly)
            df["state"] = city["state"]
            df["city"] = city["city"]
            df["latitude"] = city["latitude"]
            df["longitude"] = city["longitude"]
            df['time'] = pd.to_datetime(df['time'])

            # Split "datetime" into "date" and "time" columns
            df['date'] = df['time'].dt.date
            df['time'] = df['time'].dt.time
            hourly_data_list.append(df)
        else:
            print(f"Failed to retrieve data for {city['city']}.")

    if hourly_data_list:
        # Combine all the data for each city into one DataFrame
        final_df = pd.concat(hourly_data_list, axis=0)

        # Mapping with wmo code
        wmo.columns = ['weathercode', 'description']
        merged_df = pd.merge(wmo, final_df, on='weathercode', how='inner')

        # Sort the DataFrame by 'time' in descending order
        merged_df.sort_values(by=['time'], ascending=[False], inplace=True)

        # Filter data based on current time
        current_time = current_datetime.time()
        today_df = merged_df[merged_df['time'] <= current_time]
        
        # Remove duplicates based on 'date', 'time', 'state', and 'city'
        today_df = today_df.drop_duplicates(subset=['date', 'time', 'state', 'city'])

        # Save data to CSV using today_df
        data_dir = 'data_weatherUO'
        os.makedirs(data_dir, exist_ok=True)

        file_date = datetime.today()
        file_name = file_date.strftime('%Y-%m-%d.csv')
        file_path = os.path.join(data_dir, file_name)

        if os.path.exists(file_path):
            existing_data = pd.read_csv(file_path, header=0)
            if existing_data.empty:
                combined_data = today_df
            else:
                combined_data = pd.concat([existing_data, today_df], ignore_index=True)
            combined_data = combined_data[['date', 'time', 'state', 'city', 'latitude', 'longitude', 'temperature_2m', 'relativehumidity_2m', 'rain', 'windspeed_10m', 
                                            'weathercode', 'description']]
            combined_data.to_csv(file_path, index=False)
            print(f'Data has been appended to {file_path}')
        else:
            today_df.to_csv(file_path, index=False)
            print(f'Data has been saved to {file_path}')
    else:
        print("No data was collected for any city.")

except (requests.RequestException, requests.ConnectionError, MaxRetryError) as e:
    print(f"An error occurred: {e}")