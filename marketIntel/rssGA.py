import pandas as pd
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os

def fetch_and_process_google_alerts(url: str) -> pd.DataFrame:
    """
    Fetches the content of a Google Alerts RSS feed, parses the XML,
    and returns a pandas DataFrame.

    Args:
        url (str): The URL of the Google Alerts RSS feed.

    Returns:
        pd.DataFrame: A DataFrame containing the parsed data with columns
                      'id', 'title', 'published', and 'url'.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()

        root = ET.fromstring(response.content)

        data = []
        for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
            entry_id = entry.find('{http://www.w3.org/2005/Atom}id').text
            title = entry.find('{http://www.w3.org/2005/Atom}title').text
            published = entry.find('{http://www.w3.org/2005/Atom}published').text

            link_elem = entry.find('{http://www.w3.org/2005/Atom}link')
            link_href = link_elem.get('href')

            url_start_marker = "url="
            url_end_marker = "&ct"
            try:
                start_index = link_href.find(url_start_marker) + len(url_start_marker)
                end_index = link_href.find(url_end_marker)
                extracted_url = link_href[start_index:end_index]
            except (ValueError, IndexError):
                extracted_url = None

            data.append({
                'id': entry_id,
                'title': title,
                'published': datetime.fromisoformat(published.replace('Z', '+00:00')),
                'url': extracted_url
            })

        df = pd.DataFrame(data)
        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching the feed: {e}")
        return pd.DataFrame()
    except ET.ParseError as e:
        print(f"Error parsing the XML feed: {e}")
        return pd.DataFrame()

# Main script to fetch, process, and save data to a CSV
feed_url = "https://www.google.com.my/alerts/feeds/00888648782241832453/695303575284904172"
csv_file = "petronasGAlerts2025.csv"

# Fetch the new data
new_df = fetch_and_process_google_alerts(feed_url)

if not new_df.empty:
    if os.path.exists(csv_file):
        # File exists, append new data
        try:
            existing_df = pd.read_csv(csv_file)
            # Append new data to existing DataFrame
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            # Save the combined DataFrame back to the CSV
            combined_df.to_csv(csv_file, index=False)
            print(f"New data has been successfully appended to {csv_file}")

        except pd.errors.EmptyDataError:
            print("Existing CSV file is empty, saving new data.")
            new_df.to_csv(csv_file, index=False)
            print(f"Data saved to {csv_file}")
            print("\nDataFrame head:")
            print(new_df.head())
        except Exception as e:
            print(f"An error occurred while appending data: {e}")

    else:
        # File does not exist, create a new one
        new_df.to_csv(csv_file, index=False)
        print(f"New file '{csv_file}' created and data saved.")
        print("\nDataFrame head:")
        print(new_df.head())
else:
    print("No new data to save.")