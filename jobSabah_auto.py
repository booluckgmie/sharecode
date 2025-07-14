import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import os
import time
from requests.exceptions import RequestException
from urllib3.exceptions import MaxRetryError, NewConnectionError
from pytz import timezone

# Malaysian timezone
malaysia_tz = timezone('Asia/Kuala_Lumpur')
scraping_date = datetime.now(malaysia_tz).strftime("%Y-%m-%d %H:%M:%S")

# Folder setup
output_folder = "data_jobsabah"
os.makedirs(output_folder, exist_ok=True)
output_file_path = os.path.join(output_folder, "sabah_jobs_extended.csv")

# Base URLs
base_url = "https://jobs.sabah.gov.my"
employer_list_urls = [f"{base_url}/employer/index?industry=NDA%3D&page={i}" for i in range(1, 4)]

session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})

# Retry-safe request
def safe_get(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            return response
        except (RequestException, MaxRetryError, NewConnectionError) as e:
            print(f"❌ Error fetching {url}: {e}")
            time.sleep(delay)
    return None

# Step 1: Get employer profile URLs
employer_urls = set()
for url in tqdm(employer_list_urls, desc="Fetching employer profile pages"):
    response = safe_get(url)
    if response:
        soup = BeautifulSoup(response.text, "html.parser")
        employer_urls.update(
            {base_url + link["href"] for link in soup.find_all("a", href=True) if "/employer/company-detail?" in link["href"]}
        )

# Step 2: Get job posting URLs
job_urls = set()
for employer_url in tqdm(employer_urls, desc="Fetching job postings"):
    response = safe_get(employer_url)
    if response:
        soup = BeautifulSoup(response.text, "html.parser")
        job_urls.update(
            {base_url + link["href"] for link in soup.find_all("a", href=True) if "/job-posting/job-detail?" in link["href"]}
        )

# Step 3: Extract job details
job_data = []
for job_url in tqdm(job_urls, desc="Extracting job details"):
    response = safe_get(job_url)
    if not response:
        continue
    soup = BeautifulSoup(response.text, "html.parser")

    job_title = soup.find("h2").get_text(strip=True) if soup.find("h2") else "N/A"
    company_info = soup.find("ul", class_="post-meta")
    company_name, location = (company_info.find_all("li")[i].get_text(strip=True) if company_info and len(company_info.find_all("li")) > i else "N/A" for i in range(2))

    job_spec_list = soup.select("div.text-holder li")
    position_level, jobs_location, total_vacancy = (job_spec_list[i].strong.get_text(strip=True) if len(job_spec_list) > i and job_spec_list[i].strong else "N/A" for i in range(3))

    # Job description
    job_desc_section = next((div for div in soup.find_all("div", class_="text-holder") if "Job Description" in div.get_text()), None)
    job_description = job_desc_section.get_text(strip=True).replace("Job Description", "").strip() if job_desc_section else "N/A"

    # Required skills
    required_skill_section = next((div for div in soup.find_all("div", class_="text-holder") if "Required Skill" in div.get_text()), None)
    if required_skill_section:
        skill_list = required_skill_section.find_all("li")
        required_experience, required_education, required_language, required_soft_skill, required_technical_skill = (
            skill_list[i].find("strong").get_text(strip=True) if len(skill_list) > i and skill_list[i].find("strong") else "N/A"
            for i in range(5)
        )
    else:
        required_experience, required_education, required_language, required_soft_skill, required_technical_skill = ("N/A",) * 5

    job_info_list = soup.select("ul.job-info-list li")
    job_info = []
    for item in job_info_list:
        spans = item.find_all("span")
        if len(spans) == 2:
            job_info.append(spans[1].get_text(strip=True))
        elif len(spans) == 1:
            job_info.append(spans[0].get_text(strip=True))
        else:
            job_info.append("N/A")

    while len(job_info) < 7:
        job_info.append("N/A")

    job_type, working_hour_type, working_hour, work_day, off_day, salary_type, salary_range = job_info[:7]

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
        "scraping_date": scraping_date
    })

# Step 4: Save or append to CSV
df = pd.DataFrame(job_data)

# Check if existing CSV has data
if os.path.exists(output_file_path) and os.path.getsize(output_file_path) > 0:
    try:
        existing_df = pd.read_csv(output_file_path)
        df = pd.concat([existing_df, df], ignore_index=True)
        df.drop_duplicates(subset=["job_url", "scraping_date"], inplace=True)
    except pd.errors.EmptyDataError:
        print("⚠️ Existing CSV file is empty. Creating fresh data.")
else:
    print("📄 No existing data or file is empty, creating a new file.")

# Save
df.to_csv(output_file_path, index=False)
print(f"✅ Job scraping complete! Data saved to {output_file_path}")
