import pandas as pd
import requests
from datetime import datetime
import os

r=requests.get("http://apims.doe.gov.my/data/public_v2/CAQM/last24hours.json")

data = pd.json_normalize(payload, record_path=['24hour_api_apims'])

# Assign the first row as the header
header = data.iloc[0]
data = data[1:]  # Exclude the first row from the data
data.columns = header  # Set the column names based on the first row

df1 = data

# Melt the DataFrame to transform it into a tabular format
melted_df1 = pd.melt(df1, id_vars=['State', 'Location'], var_name='hour', value_name='value')
from datetime import datetime

# Get the current date
current_date = datetime.today().date()

# Add the 'date' column with the current date
melted_df1['date'] = current_date

# Remove duplicate rows
melted_df1 = melted_df1.drop_duplicates()

# Define the directory where you want to save the data
data_dir = 'data'

# Create the data directory if it doesn't exist
os.makedirs(data_dir, exist_ok=True)

# Save the data to a CSV file with a unique name based on the date and time
file_name = f"{current_date.strftime('%Y-%m-%d_%H-%M-%S')}.csv"
file_path = os.path.join(data_dir, file_name)

melted_df1.to_csv(file_path, index=False)

print(f'Data has been saved to {file_path}')

# Commit and push the data to the repository
commit_message = f'Update data on {current_date.strftime("%Y-%m-%d %H:%M:%S")}'
git_cmd = f'git add . && git commit -m "{commit_message}" && git push origin master'
os.system(git_cmd)
