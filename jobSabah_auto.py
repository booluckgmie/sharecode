import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from pytz import timezone
from urllib3.exceptions import MaxRetryError, ConnectionError
from requests.exceptions import RequestException

# -----------------------------
# CONFIGURATION
# -----------------------------
output_folder = 'data_jobsabah'
os.makedirs(output_folder, exist_ok=True)

malaysia_timezone = timezone('Asia/Kuala_Lumpur')
current_datetime = datetime.now(malaysia_timezone)
current_date_str = current_datetime.strftime('%Y-%m-%d')

output_file_path = os.path.join(output_folder, f"sabah_jobs_{current_date_str}.csv")

base_url = "https://jobs.sabah.gov.my"
employer_list_urls = [f"{base_url}/employer/index?industry=NDA%3D&page={i}" for i in range(1, 4)]
scraping_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
})

try:
    # Step 1: Get employer profile URLs
    employer_urls = set()
    print("🔍 Fetching employer profile pages...")
    for url in tqdm(employer_list_urls, desc="Employer pages"):
        response = session.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = [link["href"] for link in soup.select("a[href*='employer/company-detail?']")]
            full_links = {base_url + link for link in links}
            employer_urls.update(full_links)
            print(f"  {url} -> Found {len(full_links)} employer profiles")
        else:
            print(f"  Warning: Failed to fetch {url} (status {response.status_code})")

    if not employer_urls:
        print("⚠️ No employer URLs found. Exiting.")
        exit(0)

    # Step 2: Extract job posting URLs
    job_urls = set()
    print("\n🔍 Fetching job postings for each employer...")
    for employer_url in tqdm(employer_urls, desc="Employers"):
        response = session.get(employer_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            links = [link["href"] for link in soup.select("a[href*='job-posting/job-detail?']")]
            full_links = {base_url + link for link in links}
            job_urls.update(full_links)
        else:
            print(f"  Warning: Failed to fetch {employer_url} (status {response.status_code})")

    if not job_urls:
        print("⚠️ No job URLs found. Exiting.")
        exit(0)

    # Step 3: Extract job details
    job_data = []
    print("\n📝 Extracting job details...")
    for job_url in tqdm(job_urls, desc="Jobs"):
        response = session.get(job_url)
        if response.status_code != 200:
            print(f"  Warning: Failed to fetch {job_url} (status {response.status_code})")
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        job_title = soup.find("h2").get_text(strip=True) if soup.find("h2") else "N/A"
        company_info = soup.find("ul", class_="post-meta")
        if company_info and len(company_info.find_all("li")) >= 2:
            company_name = company_info.find_all("li")[0].get_text(strip=True)
            location = company_info.find_all("li")[1].get_text(strip=True)
        else:
            company_name, location = "N/A", "N/A"

        job_spec_list = soup.select("div.text-holder li")
        position_level = job_spec_list[0].strong.get_text(strip=True) if len(job_spec_list) > 0 and job_spec_list[0].strong else "N/A"
        jobs_location = job_spec_list[1].strong.get_text(strip=True) if len(job_spec_list) > 1 and job_spec_list[1].strong else "N/A"
        total_vacancy = job_spec_list[2].strong.get_text(strip=True) if len(job_spec_list) > 2 and job_spec_list[2].strong else "N/A"

        job_desc_section = next((div for div in soup.find_all("div", class_="text-holder") if "Job Description" in div.get_text()), None)
        job_description = job_desc_section.get_text(strip=True).replace("Job Description", "").strip() if job_desc_section else "N/A"

        required_skill_section = next((div for div in soup.find_all("div", class_="text-holder") if "Required Skill" in div.get_text()), None)
        if required_skill_section:
            skill_list = required_skill_section.find_all("li")
            required_experience = skill_list[0].find("strong").get_text(strip=True) if len(skill_list) > 0 and skill_list[0].find("strong") else "N/A"
            required_education = skill_list[1].find("strong").get_text(strip=True) if len(skill_list) > 1 and skill_list[1].find("strong") else "N/A"
            required_language = skill_list[2].find("strong").get_text(strip=True) if len(skill_list) > 2 and skill_list[2].find("strong") else "N/A"
            required_soft_skill = skill_list[3].find("strong").get_text(strip=True) if len(skill_list) > 3 and skill_list[3].find("strong") else "N/A"
            required_technical_skill = skill_list[4].find("strong").get_text(strip=True) if len(skill_list) > 4 and skill_list[4].find("strong") else "N/A"
        else:
            required_experience = required_education = required_language = required_soft_skill = required_technical_skill = "N/A"

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

    if not job_data:
        print("⚠️ No job data scraped. Exiting.")
        exit(0)

    # Append or create CSV file
    new_df = pd.DataFrame(job_data)
    if os.path.exists(output_file_path):
        existing_df = pd.read_csv(output_file_path)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df.drop_duplicates(subset="job_url", keep="last", inplace=True)
        combined_df.to_csv(output_file_path, index=False)
        print(f"✅ Data appended to existing file: {output_file_path}")
    else:
        new_df.to_csv(output_file_path, index=False)
        print(f"✅ New file created: {output_file_path}")

except (RequestException, ConnectionError, MaxRetryError) as e:
    print(f"❌ An error occurred during scraping: {e}")
