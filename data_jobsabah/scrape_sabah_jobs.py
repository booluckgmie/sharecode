import os
import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
from datetime import datetime
from pytz import timezone
from requests.exceptions import RequestException

# -----------------------------
# CONFIGURATION
# -----------------------------
ALL_DATA_FOLDER = 'data_jobsabah/all_jobs'
NEW_JOBS_FOLDER = 'data_jobsabah/new_jobs_only'

os.makedirs(ALL_DATA_FOLDER, exist_ok=True)
os.makedirs(NEW_JOBS_FOLDER, exist_ok=True)

malaysia_timezone = timezone('Asia/Kuala_Lumpur')
current_datetime = datetime.now(malaysia_timezone)
current_date_str = current_datetime.strftime('%Y-%m-%d')
scraping_date = current_datetime.strftime("%Y-%m-%d %H:%M:%S")

all_jobs_file = os.path.join(ALL_DATA_FOLDER, f"sabah_jobs_{current_date_str}.csv")
new_jobs_file = os.path.join(NEW_JOBS_FOLDER, f"new_jobs_only_{current_date_str}.csv")

base_url = "https://jobs.sabah.gov.my"
employer_list_urls = [f"{base_url}/employer/index?industry=NDA%3D&page={i}" for i in range(1, 4)]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; JobScraper/1.0)"
})

# -----------------------------
# SCRAPING LOGIC
# -----------------------------
try:
    # Step 1: Employer profile links
    employer_urls = set()
    for url in tqdm(employer_list_urls, desc="Fetching employer profile pages"):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                employer_urls.update({
                    base_url + link["href"]
                    for link in soup.find_all("a", href=True)
                    if "/employer/company-detail?" in link["href"]
                })
        except RequestException as e:
            print(f"⚠️ Failed to fetch {url}: {e}")

    print(f"📋 Found {len(employer_urls)} employer pages")

    # Step 2: Job links from employer pages
    job_urls = set()
    for employer_url in tqdm(employer_urls, desc="Fetching job postings"):
        try:
            response = session.get(employer_url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                job_urls.update({
                    base_url + link["href"]
                    for link in soup.find_all("a", href=True)
                    if "/job-posting/job-detail?" in link["href"]
                })
        except RequestException as e:
            print(f"⚠️ Failed to fetch {employer_url}: {e}")

    print(f"💼 Found {len(job_urls)} job postings")

    # Step 3: Extract job details
    job_data = []
    for job_url in tqdm(job_urls, desc="Extracting job details"):
        try:
            response = session.get(job_url, timeout=30)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")

            job_title = soup.find("h2").get_text(strip=True) if soup.find("h2") else "N/A"
            company_info = soup.find("ul", class_="post-meta")
            company_name, location = (
                company_info.find_all("li")[i].get_text(strip=True) if company_info and len(company_info.find_all("li")) > i else "N/A"
                for i in range(2)
            )

            job_spec_list = soup.select("div.text-holder li")
            position_level, jobs_location, total_vacancy = (
                job_spec_list[i].strong.get_text(strip=True) if len(job_spec_list) > i and job_spec_list[i].strong else "N/A"
                for i in range(3)
            )

            job_desc_section = next((div for div in soup.find_all("div", class_="text-holder") if "Job Description" in div.get_text()), None)
            job_description = job_desc_section.get_text(strip=True).replace("Job Description", "").strip() if job_desc_section else "N/A"

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
        except Exception as e:
            print(f"⚠️ Error scraping {job_url}: {e}")

    print(f"✅ Scraped {len(job_data)} jobs")

    # -----------------------------
    # SAVE TO all_jobs FOLDER (append + dedup)
    # -----------------------------
    new_df = pd.DataFrame(job_data)

    if os.path.exists(all_jobs_file):
        existing_df = pd.read_csv(all_jobs_file)
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df.drop_duplicates(subset="job_url", keep="last", inplace=True)
        combined_df.to_csv(all_jobs_file, index=False)
        print(f"📁 [all_jobs] Appended to existing file: {all_jobs_file}")
    else:
        new_df.to_csv(all_jobs_file, index=False)
        print(f"📁 [all_jobs] New file created: {all_jobs_file}")

    # -----------------------------
    # COMPARE WITH PREVIOUS all_jobs FILE → SAVE TO new_jobs_only FOLDER
    # -----------------------------
    previous_all_files = sorted(
        [
            f for f in os.listdir(ALL_DATA_FOLDER)
            if f.startswith("sabah_jobs_") and f.endswith(".csv") and f != os.path.basename(all_jobs_file)
        ],
        reverse=True
    )

    latest_df = None
    latest_file_path = None

    for pf in previous_all_files:
        candidate_path = os.path.join(ALL_DATA_FOLDER, pf)
        try:
            tmp_df = pd.read_csv(candidate_path)
            if tmp_df.empty or "job_url" not in tmp_df.columns:
                print(f"⚠️ Skipping empty or invalid file: {candidate_path}")
                continue
            latest_df = tmp_df
            latest_file_path = candidate_path
            break
        except pd.errors.EmptyDataError:
            print(f"⚠️ Skipping empty file: {candidate_path}")
        except Exception as e:
            print(f"⚠️ Could not read {candidate_path}: {e}")

    if latest_df is not None:
        latest_urls = set(latest_df["job_url"])
        new_jobs_df = new_df[~new_df["job_url"].isin(latest_urls)]

        if not new_jobs_df.empty:
            new_jobs_df.to_csv(new_jobs_file, index=False)
            print(f"🆕 {len(new_jobs_df)} new job(s) found vs: {latest_file_path}")
            print(f"📁 [new_jobs_only] Saved to: {new_jobs_file}")
        else:
            print("ℹ️ No new jobs found compared to the previous file.")
    else:
        # First run ever — all jobs are "new"
        new_df.to_csv(new_jobs_file, index=False)
        print(f"📂 No previous file found — all {len(new_df)} jobs saved as new: {new_jobs_file}")

except RequestException as e:
    print(f"❌ Network error occurred: {e}")
    raise
except Exception as e:
    print(f"❌ An error occurred: {e}")
    raise
finally:
    session.close()
    print("🔒 Session closed.")
