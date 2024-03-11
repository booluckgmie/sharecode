from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import datetime
import os

# Replace with path to ChromeDriver binary if not using a service
chromedriver_path = "/path/to/chromedriver"  # Update with your path (optional)

def scrape_data():
  try:
    # Launch Chrome browser using WebDriver (consider using a service for reusability)
    driver = webdriver.Chrome(executable_path=chromedriver_path)

    # Define the target URL
    url = "https://www.gso.org.my/SystemData/CurrentGen.aspx"

    # Open the URL in the browser
    driver.get(url)

    # Wait for the data table to load (adjust timeout as needed)
    try:
      WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "data-table")))  # Replace with appropriate locator for data table
    except TimeoutException:
      print("Error: Data table not found within the specified timeout.")
      driver.quit()
      return None  # Indicate failure to scrape data

    # Extract data from the table
    data_list = []
    table_element = driver.find_element(By.ID, "data-table")  # Replace with appropriate locator for data table
    table_rows = table_element.find_elements(By.TAG_NAME, "tr")  # Assuming data is in rows

    # Skip the header row (adjust if needed)
    for row in table_rows[1:]:
      data_cells = row.find_elements(By.TAG_NAME, "td")  # Assuming data is in cells
      date_text = data_cells[0].text  # Assuming date is in the first cell (adjust)
      coal_value = data_cells[1].text  # Assuming coal is in the second cell (adjust)
      # ... extract other values for Gas, CoGen etc.

      data_list.append({
          "date": date_text,
          "coal": coal_value,
          # ... add other data points
      })

    # Close the browser window
    driver.quit()

    # Process and return the data as DataFrame
    df = pd.DataFrame(data_list)
    df['datetime'] = pd.to_datetime(df['date'])
    
    return df

  except Exception as e:
    print(f"An error occurred: {e}")
    return None  # Indicate failure to scrape data

if __name__ == "__main__":
  scraped_data = scrape_data()
  if scraped_data is not None:
    # Save data to CSV (consider using environment variables for paths)
    data_dir = 'data_gso'
    os.makedirs(data_dir, exist_ok=True)
    file_date = datetime.today()
    file_name = file_date.strftime('%Y-%m-%d.csv')
    file_path = os.path.join(data_dir, file_name)
    scraped_data.to_csv(file_path, index=False)
    print(f'Data has been saved to {file_path}')
  else:
    print("Failed to scrape data.")
