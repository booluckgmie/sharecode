# 📌 Project Summary: MSD Alliance Data Integration

## 👤 Key Stakeholders
- **Sally** – Project Director, MSD Alliance  
- **Tech Partners** – MCMC, NADI (Smart Services)

---

## 🔍 Project Scope Summary

**Client Needs:**
- Consolidate data from **multiple sources**
- ~1–2 million data points, under 50 attributes
- Deliver **end-to-end solution**:
  - Data ingestion pipeline
  - Cleaning + standardization
  - Dashboards + analytics
- No existing infrastructure/tools
- Output: **Decision-making dashboard for MCMC**
- Small ops team → needs **automation + efficient delivery**
- **Proposal due in ~1 week**
- **Service Charge Estimate: RM10k/month (excludes infra)**

---

## 🔗 Data Flow & Integration Overview

Data consolidated from:
- **DUSP**
- **MCMC**
- **Tech Partner FTP (AWS)**

---

### 🔐 Data Security Approach

- PII **encrypted before entering** internal environment  
- Pipeline:
  1. Data Provider → encrypts PII + maps to internal ID  
  2. Data transferred encrypted  
  3. Avoid raw PII matching across data sources  

---

## 📶 Connectivity Monitoring

Track pipeline/API availability using indicators:
- ✅ Operational
- ⚠️ Degraded Performance
- 🟠 Partial Outage
- 🔴 Major Outage
- 🛠️ Maintenance

Also show:
- 100% uptime over last 90 days  
- Incident history  
- Scheduled maintenance  

---

## 📊 Dashboard Requirements

### Unified Dashboard: Single Source of Truth
- Real-time visibility across platforms  
- Clean naming conventions  
- KPI snapshots for MCMC  
- Agile, modular, scalable design  

---

### 🗺️ Advanced Visualizations

- Geospatial insights (heatmaps, clustering, overlays)  
- Ready for future **predictive/temporal** use cases  

---

### 📈 Two-Tier Dashboard Views

| Type            | Audience        | Purpose                                 |
|-----------------|------------------|------------------------------------------|
| **Operational** | Internal Team    | Live metrics, pipeline status            |
| **Reporting**   | Stakeholders     | KPIs, summaries, geospatial insights     |

---

## 📨 Automated Reports

- Scheduled delivery (weekly/monthly)  
- Formats: **PDF + image**  
- Contents:
  - Dashboard snapshots  
  - KPI summaries  
  - System anomalies & health  

---

## 🔄 Future-Ready Architecture

- Scalable to:
  - Add new data sources
  - API integrations
  - Expand cloud & BI stack  
- Modular and **cloud-compatible**  
- Ready for **PADU, DOSM, or State dashboards**  

---

## ⚠️ Key Data Management Challenges

### 1. Lack of Standardization
- Each partner uses different format/system  
- No shared data schema or structure  

### 2. Incomplete & Inconsistent Data
- Missing fields (e.g., race, location)  
- Inputs vary across partners  

### 3. Access & Encryption Issues
- Inconsistent encryption methods  
- Not all systems are owned/controlled internally  

### 4. Legal/Compliance Constraints
- Historical data may **not be PDPA compliant**  
- Engaging with DOSM/PADU needs justification  

---

## 💰 Budget Planning: Estimated Service Breakdown

### 🧑‍💻 Monthly Service Allocation

| Component                                             | Effort       | Suggested (RM)       |
|-------------------------------------------------------|--------------|----------------------|
| Data Ingestion + Pipeline                             | Medium-High  | RM4,000 – RM5,000    |
| Standardization / Validation                          | Medium       | RM1,500 – RM2,000    |
| Custom Dashboard + Analytics                          | Medium       | RM2,000 – RM2,500    |
| Project Management + QA                               | Low          | RM500 – RM1,000      |
| **Total (Service Only)**                              |              | RM8,000 – RM10,500 ✅ |

---

## 🏗️ Infrastructure Cost (Optional Add-On)

| Item                        | Est. Monthly Cost    | Notes                          |
|-----------------------------|----------------------|--------------------------------|
| Cloud Infra (AWS/GCP/Azure) | RM1,000 – RM3,000     | Hosting, compute, pipelines    |
| Managed DB (e.g., RDS)      | RM500 – RM1,500       | Based on data/query loads      |
| BI Tool Licenses            | RM500 – RM1,000       | Power BI Pro ~RM50/user        |
| Security (VPC, encryption)  | RM500 – RM1,000       | Required if handling PII       |

🟡 **Recommendation:** Keep infra **as optional cost**, not bundled with RM10k/month service fee.

---

## 🧠 Charge Justification (RM10k/month)

| Factor                   | Value Provided                                         |
|--------------------------|--------------------------------------------------------|
| **Lean Setup**           | You provide Data Eng, Analyst, PM coverage             |
| **Large Volume**         | ~1–2M records, scalable pipeline needed                |
| **No Infra in Place**    | Ground-up deployment + config                          |
| **Secure PII Handling**  | Design needs to meet compliance standards              |
| **Custom Dashboards**    | Built from scratch, tailored to MCMC needs             |
| **Automation Focus**     | Low team overhead → cost-effective solution            |

✅ **RM10k/month is competitive** given delivery scope and constraints.

---

## 🧾 Proposal Packaging Tips

### Suggested Proposal Title:
**"Data Consolidation & Decision Support Platform for MCMC"**

### Recommended Sections:
1. **Problem Statement** – Fragmented, inconsistent data environment  
2. **Objectives** – Unified dashboards, encrypted pipelines, insights  
3. **Scope of Work** – Ingest → Clean → Visualize → Report  
4. **Timeline** –  
   - Month 1: Data onboarding  
   - Month 2: MVP dashboard  
   - Month 3+: Optimizations + scaling  
5. **Pricing** – RM10k/month (service only); infra optional  
6. **Value Proposition** – Fast, lean, PDPA-aligned, ready to grow  

---

## 🧩 Final Notes

- ✅ RM10k/month reflects effort, efficiency, and expertise  
- 🔁 Offer infrastructure as **modular add-on**, not bundled  
- 🧠 Emphasize automation + lean delivery = high ROI  
- 📡 Pitch scalable roadmap (e.g., PADU/DOSM integration)

---

## 🧭 Architecture & Operational Flow

### 🔧 Initial Architecture Flow:
*data source → encrypted pipeline → analytics engine → dashboard output)*
### [Architecture Flow]
![Architecture Flow](https://fast.image.delivery/sksebmj.png)

### 🔄 Operational Flow:
*(Optional: add swimlane diagram or timeline showing data intake, QA, and reporting loops)*
### [Operational Flow]
![Operational Flow](https://fast.image.delivery/chklpre.png)
