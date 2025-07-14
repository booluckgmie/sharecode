import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm  # Progress bar
from datetime import datetime
import os # Import the os module for path manipulation
import time # Import time for delays to be polite to the server

# Define base URLs - refer to number of pages for Oil and Gas Industry
base_url = "https://jobs.sabah.gov.my"
employer_list_urls = [f"{base_url}/employer/index?industry=NDA%3D&page={i}" for i in range(1, 4)]

# Get current scraping date
scraping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Initialize session (better than multiple requests)
session = requests.Session()

# Define the folder name
output_folder = "data_jobsabah"
# Create the folder if it doesn't exist
# This is crucial for GitHub Actions or any environment where the folder might not exist
if not os.path.exists(output_folder):
    os.makedirs(output_folder)
    print(f"Created output folder: {output_folder}")

# Step 1: Extract employer profile URLs
employer_urls = set()  # Use a set to prevent duplicates
print("Starting to fetch employer profile pages...")
for url in tqdm(employer_list_urls, desc="Fetching employer profile pages"):
    try:
        response = session.get(url, timeout=10) # Add timeout for robustness
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Ensure the link extraction logic is still valid
        new_employer_links = {
            base_url + link["href"] 
            for link in soup.find_all("a", href=True) 
            if "/employer/company-detail?" in link["href"]
        }
        employer_urls.update(new_employer_links)
        time.sleep(0.5) # Be polite, add a small delay

    except requests.exceptions.RequestException as e:
        print(f"Error fetching employer list page {url}: {e}")
        continue # Continue to the next URL even if one fails

print(f"Step 1 Complete: Found {len(employer_urls)} unique employer URLs.")
if not employer_urls:
    print("Warning: No employer URLs found. Check base_url or site structure.")


# Step 2: Extract job posting URLs from each employer
job_urls = set()
print("Starting to fetch job postings from employer pages...")
for employer_url in tqdm(employer_urls, desc="Fetching job postings"):
    try:
        response = session.get(employer_url, timeout=10) # Add timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Ensure the link extraction logic for jobs is still valid
        new_job_links = {
            base_url + link["href"] 
            for link in soup.find_all("a", href=True) 
            if "/job-posting/job-detail?" in link["href"]
        }
        job_urls.update(new_job_links)
        time.sleep(0.5) # Be polite, add a small delay

    except requests.exceptions.RequestException as e:
        print(f"Error fetching job listings from {employer_url}: {e}")
        continue # Continue to the next employer URL even if one fails

print(f"Step 2 Complete: Found {len(job_urls)} unique job URLs.")
if not job_urls:
    print("Warning: No job URLs found. This might mean no jobs are currently posted for the industry.")


# Step 3: Extract job details
job_data = []
print("Starting to extract job details...")
for job_url in tqdm(job_urls, desc="Extracting job details"):
    try:
        response = session.get(job_url, timeout=10) # Add timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract job title
        job_title = soup.find("h2").get_text(strip=True) if soup.find("h2") else "N/A"

        # Extract company information
        company_info = soup.find("ul", class_="post-meta")
        company_name, location = ("N/A", "N/A") # Initialize with N/A
        if company_info:
            list_items = company_info.find_all("li")
            if len(list_items) > 0:
                company_name = list_items[0].get_text(strip=True) if list_items[0] else "N/A"
            if len(list_items) > 1:
                location = list_items[1].get_text(strip=True) if list_items[1] else "N/A"

        # Extract job specifications (Position Level, Jobs Location, Total Vacancy)
        job_spec_list = soup.select("div.text-holder li")
        position_level, jobs_location, total_vacancy = ("N/A",) * 3
        
        # Iterating through all <li> elements under div.text-holder to find specific specs
        for li in job_spec_list:
            text = li.get_text(strip=True)
            if "Position Level:" in text:
                position_level = text.replace("Position Level:", "").strip()
            elif "Jobs Location:" in text:
                jobs_location = text.replace("Jobs Location:", "").strip()
            elif "Total Vacancy:" in text:
                total_vacancy = text.replace("Total Vacancy:", "").strip()

        # Extract job description
        # Attempt to find the specific heading and then its content
        job_desc_heading = soup.find("h3", string="Job Description")
        job_description = "N/A"
        if job_desc_heading:
            # Look for the next 'div' with class 'text-holder' after the heading
            desc_div = job_desc_heading.find_next_sibling("div", class_="text-holder")
            if desc_div:
                job_description = desc_div.get_text(strip=True)
                # Remove the "Job Description" header text if it's still part of the extracted content
                if job_description.startswith("Job Description"):
                    job_description = job_description.replace("Job Description", "", 1).strip()


        # Extract required skills
        required_skill_heading = soup.find("h3", string="Required Skill")
        required_experience, required_education, required_language, required_soft_skill, required_technical_skill = ("N/A",) * 5

        if required_skill_heading:
            skill_div = required_skill_heading.find_next_sibling("div", class_="text-holder")
            if skill_div:
                skill_list_items = skill_div.find_all("li")
                for li in skill_list_items:
                    li_text = li.get_text(strip=True)
                    if "Experience:" in li_text:
                        required_experience = li_text.replace("Experience:", "").strip()
                    elif "Education:" in li_text:
                        required_education = li_text.replace("Education:", "").strip()
                    elif "Language:" in li_text:
                        required_language = li_text.replace("Language:", "").strip()
                    elif "Soft Skill:" in li_text:
                        required_soft_skill = li_text.replace("Soft Skill:", "").strip()
                    elif "Technical Skill:" in li_text:
                        required_technical_skill = li_text.replace("Technical Skill:", "").strip()


        # Extract job details from 'ul.job-info-list li'
        job_info_list = soup.select("ul.job-info-list li")
        
        # Initialize with N/A
        job_type, working_hour_type, working_hour, work_day, off_day, salary_type, salary_range = ("N/A",) * 7

        for item in job_info_list:
            key_span = item.find("span", class_="info-title") # Assuming standard class for key
            value_span = item.find("span", class_="info-value") # Assuming standard class for value

            key = key_span.get_text(strip=True).replace(":", "").strip() if key_span else ""
            value = value_span.get_text(strip=True) if value_span else "N/A"

            if "Job Type" in key:
                job_type = value
            elif "Working Hour Type" in key:
                working_hour_type = value
            elif "Working Hour" in key:
                working_hour = value
            elif "Work Day" in key:
                work_day = value
            elif "Off Day" in key:
                off_day = value
            elif "Salary Type" in key:
                salary_type = value
            elif "Salary Range" in key:
                salary_range = value
            # Handle potential cases where "Salary" might be present but no specific type/range span
            elif "Salary" in key and not salary_range and not salary_type:
                 salary_range = value # Default to salary_range if no specific type/range

        # Append data
        job_data.append({
            "job_title": job_title,
            "company_name": company_name,
            "location": location,
            "position_level": position_level,
            "jobs_location": jobs_location,
            "total_vacancy": total_vacancy,
            "job_description": job_description,
            "required_experience": required_experience,
            "required_education": required_education,
            "required_language": required_language,
            "required_soft_skill": required_soft_skill,
            "required_technical_skill": required_technical_skill,
            "job_type": job_type,
            "working_hour_type": working_hour_type,
            "working_hour": working_hour,
            "work_day": work_day,
            "off_day": off_day,
            "salary_type": salary_type,
            "salary_range": salary_range,
            "job_url": job_url,
            "scraping_date": scraping_date # Add the scraping date
        })
        time.sleep(0.5) # Be polite, add a small delay for each job detail page

    except requests.exceptions.RequestException as e:
        print(f"Error fetching job details for {job_url}: {e}")
        continue # Continue to the next job URL
    except Exception as e:
        print(f"An unexpected error occurred while processing {job_url}: {e}")
        continue # Continue to the next job URL if parsing fails

# Convert to DataFrame
df = pd.DataFrame(job_data)

# Define the full path to the CSV file
output_file_path = os.path.join(output_folder, "sabah_jobs_extended.csv")

# Load existing data if available and append, otherwise create new
try:
    # Use the full path for reading
    existing_df = pd.read_csv(output_file_path)
    print(f"Found existing data with {len(existing_df)} rows. Appending new data.")
    df = pd.concat([existing_df, df], ignore_index=True)
    
    # Deduplication: keep the latest entry for each job_url
    # If the website provides an "updated date" for jobs, you might use that for keep="last"
    # Otherwise, "scraping_date" is a good proxy for freshness if you want the *most recent scrape*
    df.drop_duplicates(subset=["job_url"], keep="last", inplace=True) 
    print(f"After deduplication, DataFrame has {len(df)} rows.")

except FileNotFoundError:
    print(f"No existing CSV found at {output_file_path}. Creating a new one.")
    pass # No existing file, just save the new DataFrame

# Save to CSV
# Use the full path for writing
df.to_csv(output_file_path, index=False)

print(f"✅ Job scraping complete! Data saved to {output_file_path}")
