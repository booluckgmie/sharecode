import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm  # Progress bar

# Define base URLs - refer to number of pages for Oil and Gas Industry
base_url = "https://jobs.sabah.gov.my"
employer_list_urls = [f"{base_url}/employer/index?industry=NDA%3D&page={i}" for i in range(1, 4)]

# Initialize session (better than multiple requests)
session = requests.Session()

# Step 1: Extract employer profile URLs
employer_urls = set()  # Use a set to prevent duplicates
for url in tqdm(employer_list_urls, desc="Fetching employer profile pages"):
    response = session.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        employer_urls.update(
            {base_url + link["href"] for link in soup.find_all("a", href=True) if "/employer/company-detail?" in link["href"]}
        )

# Step 2: Extract job posting URLs from each employer
job_urls = set()
for employer_url in tqdm(employer_urls, desc="Fetching job postings"):
    response = session.get(employer_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        job_urls.update(
            {base_url + link["href"] for link in soup.find_all("a", href=True) if "/job-posting/job-detail?" in link["href"]}
        )

# Step 3: Extract job details
job_data = []
for job_url in tqdm(job_urls, desc="Extracting job details"):
    response = session.get(job_url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract job title
        job_title = soup.find("h2").get_text(strip=True) if soup.find("h2") else "N/A"

        # Extract company information
        company_info = soup.find("ul", class_="post-meta")
        company_name, location = (company_info.find_all("li")[i].get_text(strip=True) if company_info and len(company_info.find_all("li")) > i else "N/A" for i in range(2))

        # Extract job specifications
        job_spec_list = soup.select("div.text-holder li")
        position_level, jobs_location, total_vacancy = (job_spec_list[i].strong.get_text(strip=True) if len(job_spec_list) > i and job_spec_list[i].strong else "N/A" for i in range(3))

        # Extract job specifications
        job_spec_list = soup.select("div.text-holder li")
        position_level, jobs_location, total_vacancy = (
            job_spec_list[i].strong.get_text(strip=True) if len(job_spec_list) > i else "N/A"
            for i in range(3)
        )

        # Extract job description
        job_desc_section = next(
            (div for div in soup.find_all("div", class_="text-holder") if "Job Description" in div.get_text()), 
            None
        )
        job_description = job_desc_section.get_text(strip=True).replace("Job Description", "").strip() if job_desc_section else "N/A"


        # Extract required skills
        required_skill_section = next(
            (div for div in soup.find_all("div", class_="text-holder") if "Required Skill" in div.get_text()), 
            None
        )
        if required_skill_section:
            skill_list = required_skill_section.find_all("li")
            required_experience, required_education, required_language, required_soft_skill, required_technical_skill = (
                skill_list[i].find("strong").get_text(strip=True) if len(skill_list) > i else "N/A"
                for i in range(5)
            )
        else:
            required_experience, required_education, required_language, required_soft_skill, required_technical_skill = ("N/A",) * 5


        # Extract job details from the corrected HTML structure
        job_info_list = soup.select("ul.job-info-list li")
        job_info = []
        for item in job_info_list:
            spans = item.find_all("span")
            if len(spans) == 2:  # Standard key-value pair
                job_info.append(spans[1].get_text(strip=True))
            elif len(spans) == 1:  # Missing colon cases (like Salary Type, Salary Range)
                job_info.append(spans[0].get_text(strip=True))
            else:
                job_info.append("N/A")

        # Ensure all job fields exist (handling missing fields)
        while len(job_info) < 7:
            job_info.append("N/A")

        job_type, working_hour_type, working_hour, work_day, off_day, salary_type, salary_range = job_info[:7]

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
            "job_url": job_url
        })

# Convert to DataFrame
df = pd.DataFrame(job_data)

# Save to CSV
df.to_csv("sabah_jobs_extended.csv", index=False)

print("✅ Job scraping complete! Data saved to sabah_jobs_extended.csv")
