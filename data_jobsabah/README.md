# Sabah Job Portal Scraper

Automated daily scraper for [jobs.sabah.gov.my](https://jobs.sabah.gov.my), running via **GitHub Actions** every day at **10:00 AM Malaysia Time**.

---

## 📁 Folder Structure

```
data_jobsabah/
├── all_jobs/
│   ├── sabah_jobs_2026-04-08.csv   ← full daily snapshot (appended + deduped)
│   ├── sabah_jobs_2026-04-09.csv
│   └── ...
└── new_jobs_only/
    ├── new_jobs_only_2026-04-08.csv   ← jobs NOT seen in previous day's file
    ├── new_jobs_only_2026-04-09.csv
    └── ...
```

| Folder | Description |
|---|---|
| `all_jobs/` | One CSV per day — complete snapshot. If re-run on the same day, data is appended and deduplicated by `job_url`. |
| `new_jobs_only/` | Only jobs that did not appear in the **previous day's** `all_jobs` file. Useful for alerts or daily diff emails. |

---

## ⚙️ GitHub Actions Setup

The workflow file is at `.github/workflows/scrape_sabah_jobs.yml`.

### Schedule
Runs automatically at **02:00 UTC = 10:00 AM MYT** every day.

You can also trigger it manually: **Actions → Scrape Sabah Job Portal → Run workflow**.

### Required Repository Permission
The workflow needs write access to commit the CSVs back to the repo.

Go to: **Settings → Actions → General → Workflow permissions**  
→ Select **"Read and write permissions"** ✅

---

## 🖥️ Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python scrape_sabah_jobs.py
```

Output will be written to `data_jobsabah/all_jobs/` and `data_jobsabah/new_jobs_only/`.

---

## 📊 CSV Columns

| Column | Description |
|---|---|
| `job_title` | Job title |
| `company_name` | Employer name |
| `location` | City/State |
| `position_level` | Seniority level |
| `jobs_location` | Location of the job |
| `total_vacancy` | Number of openings |
| `job_description` | Full job description |
| `required_experience` | Minimum years of experience |
| `required_education` | Minimum education level |
| `required_language` | Language requirements |
| `required_soft_skill` | Soft skills listed |
| `required_technical_skill` | Technical skills listed |
| `job_type` | Full Time / Contract / Temporary etc. |
| `working_hour_type` | Office Hour / Flexible etc. |
| `working_hour` | Start–end time |
| `work_day` | Working days |
| `off_day` | Off days |
| `salary_type` | Monthly / Daily / Project Based |
| `salary_range` | Salary range (RM) |
| `job_url` | Direct link to job posting |
| `scraping_date` | Timestamp of when data was scraped (MYT) |
