# 📌 Project Summary: MSD Alliance Data Integration

## 👤 Key Stakeholders
- **Sally** – Project Director, MSD Alliance
- **Tech Partners** – MCMC, NADI (Smart Services)

---

## 🔗 Data Flow & Integration Overview
- Data comes from multiple platforms and tech partners
- Merged through:
  - **DUSP**  
  - **MCMC**  
  - **Tech Partner FTP (AWS)**

### 🔐 Data Security Approach
- Prefer **PII data encrypted before entering our environment**
- Data pipeline:
  1. Data Provider → PII encrypted with mapped ID (on their end)
  2. Transferred to our environment in **encrypted** form
  3. Avoid cross-source matching of raw PII

---

## 📶 Data Source Connectivity Indicators
- Track **API or other connections** with availability metrics:
  - **100% uptime over the last 90 days**
  - Include status:
    - Operational
    - Degraded Performance
    - Partial Outage
    - Major Outage
    - Maintenance
- Show:
  - **Incident History**
  - **Upcoming Maintenance**

---

## 📊 Dashboard Requirements
- **Centralized dashboard** as single source of truth
- Features:
  - Data visibility across platforms
  - Naming convention consistency
  - Analytics for actionable insights
  - Agile and cost-efficient architecture

---

## ⚠️ Key Data Management Challenges

### 1. Lack of Standardization
- Each TP has its **own system** (or none)
- No standard data formats or structures
- Smart Services creates **reports in their own format**

### 2. Incomplete & Inconsistent Data
- Some data only includes name & IC (missing race, etc.)
- Data gaps due to non-uniform input across TPs

### 3. Data Encryption & Access Issues
- PII is encrypted differently by partners
- Not all parties **own or control the systems** involved

### 4. Compliance & Legal Constraints
- **Historical data may not comply with PDPA**
- Engaging external agencies (e.g., MCMC, DOSM/PADU) requires strong **justification** and oversight

---


Initial data flow:
### [Architecture Flow]
![Architecture Flow](https://fast.image.delivery/sksebmj.png)


### [Operational Flow]
![Operational Flow](https://fast.image.delivery/chklpre.png)
