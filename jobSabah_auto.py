import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm  # Progress bar
from datetime import datetime
import os # Import the os module for path manipulation
import time # Import time for delays

# Define base URLs - refer to number of pages for Oil and Gas Industry
# Ensure the industry code 'NDA%3D' is still valid for Oil & Gas
base_url = "https://jobs.sabah.gov.my"
employer_list_urls = [f"{base_url}/employer/index?industry=NDA%3D&page={i}" for i in range(1, 4)] # Checks pages 1, 2, 3

# Initialize session (better than multiple requests)
session = requests.Session()

# Get current scraping date
scraping_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Define the folder name
output_folder = "data_jobsabah"
# Create the folder if it doesn't exist
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Step 1: Extract employer profile URLs
employer_urls = set()  # Use a set to prevent duplicates
print("Starting to fetch employer profile pages...")
for url in tqdm(employer_list_urls, desc="Fetching employer profile pages"):
    try:
        response = session.get(url, timeout=10) # Added timeout
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Look for links within specific employer listing containers if available
        # This makes the selector more robust than just any 'a' tag
        # Example: if employer cards are within a div with class 'employer-card'
        # For now, keeping original, but this is a common point of failure.
        
        # Original logic for employer links:
        new_employer_links = {
            base_url + link["href"] 
            for link in soup.find_all("a", href=True) 
            if "/employer/company-detail?" in link["href"]
        }
        employer_urls.update(new_employer_links)
        
        # Add a small delay between requests to avoid being blocked
        time.sleep(1) # Sleep for 1 second

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        continue # Continue to the next URL even if one fails

print(f"Step 1 Complete: Found {len(employer_urls)} unique employer URLs.")
if not employer_urls:
    print("Warning: No employer URLs found. Check base_url, industry code, and page range.")


# Step 2: Extract job posting URLs from each employer
job_urls = set()
print("Starting to fetch job postings from employer pages...")
for employer_url in tqdm(employer_urls, desc="Fetching job postings"):
    try:
        response = session.get(employer_url, timeout=10) # Added timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Look for job links within specific job listing containers if available
        # Example: if job listings are within a div with class 'job-listing'
        # For now, keeping original, but this is another common point of failure.
        
        # Original logic for job links:
        new_job_links = {
            base_url + link["href"] 
            for link in soup.find_all("a", href=True) 
            if "/job-posting/job-detail?" in link["href"]
        }
        job_urls.update(new_job_links)

        time.sleep(1) # Sleep for 1 second

    except requests.exceptions.RequestException as e:
        print(f"Error fetching {employer_url}: {e}")
        continue # Continue to the next URL even if one fails

print(f"Step 2 Complete: Found {len(job_urls)} unique job URLs.")
if not job_urls:
    print("Warning: No job URLs found. This could mean no jobs are posted, or the previous step failed.")


# Step 3: Extract job details
job_data = []
print("Starting to extract job details...")
for job_url in tqdm(job_urls, desc="Extracting job details"):
    try:
        response = session.get(job_url, timeout=10) # Added timeout
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract job title - remains simple, often in h2
        job_title = soup.find("h2").get_text(strip=True) if soup.find("h2") else "N/A"

        # Extract company information - assuming post-meta ul remains stable
        company_info = soup.find("ul", class_="post-meta")
        company_name, location = ("N/A", "N/A") # Default values
        if company_info:
            list_items = company_info.find_all("li")
            if len(list_items) > 0:
                company_name = list_items[0].get_text(strip=True) if list_items[0] else "N/A"
            if len(list_items) > 1:
                location = list_items[1].get_text(strip=True) if list_items[1] else "N/A"
        
        # Extract job specifications (Position Level, Jobs Location, Total Vacancy)
        # Assuming 'div.text-holder li' where strong tags hold the values
        job_spec_list = soup.select("div.text-holder li")
        position_level, jobs_location, total_vacancy = ("N/A",) * 3
        
        # More robust extraction for job_spec_list
        spec_texts = [li.get_text(strip=True) for li in job_spec_list]
        
        for text in spec_texts:
            if "Position Level:" in text:
                position_level = text.replace("Position Level:", "").strip()
            elif "Jobs Location:" in text:
                jobs_location = text.replace("Jobs Location:", "").strip()
            elif "Total Vacancy:" in text:
                total_vacancy = text.replace("Total Vacancy:", "").strip()

        # Extract job description
        # More specific way to find the Job Description section
        job_desc_section = soup.find("h3", string="Job Description")
        job_description = "N/A"
        if job_desc_section and job_desc_section.find_next_sibling("div", class_="text-holder"):
            job_description = job_desc_section.find_next_sibling("div", class_="text-holder").get_text(strip=True)
            # Clean up the "Job Description" header if it's still present in the extracted text
            job_description = job_description.replace("Job Description", "").strip()


        # Extract required skills (Experience, Education, Language, Soft Skill, Technical Skill)
        # Using h3 to locate the section and then finding its next sibling 'div.text-holder'
        required_skill_section = None
        skill_heading = soup.find("h3", string="Required Skill")
        if skill_heading:
            required_skill_section = skill_heading.find_next_sibling("div", class_="text-holder")
            
        required_experience, required_education, required_language, required_soft_skill, required_technical_skill = ("N/A",) * 5

        if required_skill_section:
            skill_labels = required_skill_section.find_all("strong") # Find the labels (e.g., "Experience:")
            for label in skill_labels:
                label_text = label.get_text(strip=True)
                # Get the sibling text after the strong tag, or the whole li if no strong
                parent_li_text = label.parent.get_text(strip=True) if label.parent.name == 'li' else label.next_sibling.strip() if label.next_sibling else ''
                
                # Clean up the label from the value
                value = parent_li_text.replace(label_text, "").strip()
                
                if "Experience:" in label_text:
                    required_experience = value
                elif "Education:" in label_text:
                    required_education = value
                elif "Language:" in label_text:
                    required_language = value
                elif "Soft Skill:" in label_text:
                    required_soft_skill = value
                elif "Technical Skill:" in label_text:
                    required_technical_skill = value
        
        # Extract job details from the 'ul.job-info-list li' structure
        job_info_list = soup.select("ul.job-info-list li")
        
        # Initialize all job info fields to "N/A"
        job_type, working_hour_type, working_hour, work_day, off_day, salary_type, salary_range = ("N/A",) * 7

        for item in job_info_list:
            key_span = item.find("span", class_="info-title") # Assuming keys have this class
            value_span = item.find("span", class_="info-value") # Assuming values have this class

            key = key_span.get_text(strip=True).replace(":", "") if key_span else ""
            value = value_span.get_text(strip=True) if value_span else "N/A" # Default to N/A if no value span

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
            # Handle cases where "Salary" might appear without "Type" or "Range"
            elif "Salary" in key and not salary_range and not salary_type:
                 salary_range = value # Or try to parse it

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
        time.sleep(1) # Small delay for each job detail page

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
    df = pd.concat([existing_df, df], ignore_index=True)
    
    # Deduplication: only keep the latest entry for a given job_url
    # If you want to track *all* historical changes, remove or adjust this.
    # Here, we prioritize the latest scrape for each job_url.
    df.drop_duplicates(subset=["job_url"], keep="last", inplace=True) 

except FileNotFoundError:
    print(f"No existing CSV found at {output_file_path}. Creating a new one.")
    pass # No existing file, just save the new DataFrame

# Save to CSV
# Use the full path for writing
df.to_csv(output_file_path, index=False)

print(f"✅ Job scraping complete! Data saved to {output_file_path}")
