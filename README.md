# Real Estate KYC Verification Agent 📋

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![OpenAI GPT-4o](https://img.shields.io/badge/OpenAI-GPT--4o-orange.svg)](https://openai.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-red.svg)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-blue.svg)](https://www.postgresql.org/)

An AI-powered agentic system that automates the verification of client details in **Agreement for Sale (AFS)** documents against official KYC documents (**Aadhaar** and **PAN** cards). The system cross-verifies multiple fields (Full Name, Father's Name, DOB, PAN, Aadhaar, and Addresses), audits numeric data against Google Sheets, logs verification history, generates premium PDF reports, and alerts the CRM team with rich HTML emails featuring interactive comparison tables.

---

## 🌟 Key Features

- **Unified Verification Flow**: Single endpoint that performs both KYC verification AND Google Sheet audit in one run
- **Document Parsing**: Automatic text and structured markdown extraction from AFS PDFs using Microsoft `MarkItDown` and `PyMuPDF`
- **AI-Powered Cross-Verification**: Leverages GPT-4o with vision capabilities for character-perfect identity verification supporting joint owners and co-applicants
- **Google Sheets Integration**: Automatically extracts and audits numeric data (amounts, percentages) against configured Google Sheets
- **Strict Logic Matching**: Zero-tolerance checks on Names, Date of Birth, PAN, Aadhaar, and Address components (handling abbreviations and masked card formats)
- **Interactive CRM Alerts**: Beautifully styled HTML emails with color-coded badges and interactive comparison tables
- **Premium PDF Reports**: Professional branded documents with client metadata, verification badges, and detailed comparison tables
- **Multi-Backend Persistence**: SQLite for local development, PostgreSQL (Neon) for cloud deployment
- **Complete History**: Full audit trail with timestamps, metadata, and ability to re-download any past report

---

## 🏗️ System Architecture

### Component Diagram
```
┌─────────────────────────────────────────────────────────────────────────┐
│                         STREAMLIT UI LAYER (app.py)                     │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  4-Tab Dashboard:                                                │   │
│  │  • Full Verification (KYC + Sheet Audit)                        │   │
│  │  • KYC Only (Identity Verification)                            │   │
│  │  • Sheet Audit Only (Numeric Data Validation)                  │   │
│  │  • History (Past Records & Report Download)                    │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
        ┌──────────────────┐  ┌─────────────┐  ┌──────────────┐
        │  agent.py        │  │ sheets.py   │  │ comparator.py│
        │ (GPT-4o Verify)  │  │(Google API) │  │  (Logic)     │
        └──────────────────┘  └─────────────┘  └──────────────┘
                    │                ▼                ▼
                    └────────────────┼────────────────┘
                                     ▼
                    ┌────────────────────────────────┐
                    │   Verification Engine          │
                    │  (GPT-4o Vision + Text)        │
                    │  + Matching Logic              │
                    └────────────────────────────────┘
                                     │
        ┌────────────────┬───────────┼───────────┬──────────────┐
        ▼                ▼           ▼           ▼              ▼
   ┌─────────┐  ┌───────────────┐  ┌────────┐  ┌──────────┐  ┌──────┐
   │database │  │pdf_report.py  │  │notifier│  │  ui.py   │  │tests │
   │  (ORM)  │  │ (PDF Gen)     │  │(SMTP)  │  │(Styling) │  │(e2e) │
   └─────────┘  └───────────────┘  └────────┘  └──────────┘  └──────┘
        │
        ▼
   ┌────────────────────────────────┐
   │  Data Persistence Layer        │
   │  ┌──────────────┐              │
   │  │   SQLite     │ (dev)        │
   │  │  Postgres    │ (production) │
   │  └──────────────┘              │
   └────────────────────────────────┘
```

---

## 🔄 End-to-End Data Flow

```
User Upload (AFS + KYC Cards)
        │
        ▼
    ┌───────────────────────────────────┐
    │  Document Extraction Layer        │
    │  ├─ AFS PDF → MarkItDown → Text   │
    │  ├─ Aadhaar/PAN → Base64 Images   │
    │  └─ Google Sheet → Gspread API    │
    └───────────────────────────────────┘
        │
        ▼
    ┌───────────────────────────────────┐
    │  AI Verification Agent (GPT-4o)   │
    │  ├─ Vision: Read KYC Cards        │
    │  ├─ Text: Parse AFS Content       │
    │  └─ Logic: Cross-match fields     │
    └───────────────────────────────────┘
        │
        ▼
    ┌───────────────────────────────────┐
    │  Comparison Engine                │
    │  ├─ Field Matching (Name, DOB)    │
    │  ├─ Address Normalization         │
    │  ├─ Sheet Data Validation         │
    │  └─ Anomaly Detection             │
    └───────────────────────────────────┘
        │
        ├──────────────────┬──────────────────┬──────────────────┐
        ▼                  ▼                  ▼                  ▼
    ┌─────────┐        ┌────────┐      ┌──────────┐        ┌──────┐
    │ Database│        │ PDF    │      │ HTML     │        │ UI   │
    │ Record  │        │ Report │      │ Email    │        │ View │
    │(SQLite/ │        │(fpdf2) │      │(Styled)  │        │      │
    │Postgres)│        │        │      │(SMTP)    │        │      │
    └─────────┘        └────────┘      └──────────┘        └──────┘
        │                  │                  │                  │
        └──────────────────┴──────────────────┴──────────────────┘
                           │
                           ▼
                    Re-downloadable
                    Audit Trail
```

---

## 📁 Repository Structure

```
├── app.py                      # Streamlit multi-tab dashboard
├── agent.py                    # Document extraction + GPT-4o verification orchestration
├── comparator.py               # Field comparison logic + validation rules
├── sheets.py                   # Google Sheets API integration (service account)
├── database.py                 # SQLAlchemy ORM (SQLite/PostgreSQL abstraction)
├── pdf_report.py               # PDF generation engine (branded reports with badges)
├── notifier.py                 # HTML email construction + SMTP sender
├── ui.py                       # Streamlit component library (CSS injection, layouts)
│
├── system_prompt.md            # GPT-4o system instructions for verification logic
├── afs_sheet_system_prompt.md  # GPT-4o system instructions for sheet data extraction
│
├── tests/
│   ├── test_comparator.py      # Unit tests for matching logic
│   ├── test_e2e_sheet.py       # End-to-end sheet audit tests
│   └── fixtures/
│       └── afs_313_extraction.json  # Sample AFS extraction data
│
├── requirements.txt            # Core dependencies
├── requirements-dev.txt        # Dev + test dependencies
├── runtime.txt                 # Python version (deployment)
├── .streamlit/
│   ├── config.toml             # Streamlit theme & UI config
│   └── secrets.toml.example    # Secrets template (cloud deployment)
│
├── DEPLOYMENT.md               # Step-by-step cloud deployment guide
├── .env.example                # Local environment variables template
└── .gitignore                  # Excludes .env, credentials, caches
```

---

## 🔗 Module Dependencies

```
app.py (Streamlit UI)
 ├── agent.py
 │   ├── comparator.py
 │   └── system_prompt.md
 ├── sheets.py
 │   └── comparator.py
 ├── database.py
 ├── pdf_report.py
 │   └── database.py
 ├── notifier.py
 │   └── database.py
 └── ui.py

database.py (ORM Layer)
 └── SQLAlchemy + SQLite/PostgreSQL

tests/
 ├── comparator.py (unit tests)
 └── agent.py + sheets.py (integration tests)
```

---

## 🚀 Quick Start

### 📋 Prerequisites

- **Python 3.10+** on your machine
- **OpenAI API Key** (GPT-4o access) — [Get it here](https://platform.openai.com/api-keys)
- **Google Service Account Key** (for Google Sheets API) — [Setup guide](DEPLOYMENT.md#step-1)
- **Gmail App Password** (for SMTP notifications) — [Generate here](https://myaccount.google.com/apppasswords)

### 💻 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/afs-verification-agent.git
   cd afs-verification-agent
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   ```bash
   cp .env.example .env
   ```
   
   Fill in your `.env` file:
   ```env
   # OpenAI API
   OPENAI_API_KEY=your_openai_api_key_here
   
   # SMTP Email (Gmail)
   SMTP_EMAIL=your_gmail_address_here
   SMTP_PASSWORD=your_gmail_app_password_here
   
   # Google Sheets (local development)
   GOOGLE_SHEETS_CREDENTIALS_PATH=./AFS_Verification_GS.json
   
   # Optional: Default Google Sheet ID for pre-filling
   DEFAULT_SHEET_ID=your_sheet_id_here
   ```

   > [!IMPORTANT]
   > **Gmail Setup**: The `SMTP_PASSWORD` must be a 16-character **App Password** (not your Gmail password). Enable 2-Step Verification in your Google Account settings, then generate an app-specific password.

4. **Prepare Google Service Account:**
   - Create a service account in [Google Cloud Console](https://console.cloud.google.com/)
   - Download the JSON key and save it as `AFS_Verification_GS.json` in the project root
   - Share your Google Sheet with the service account's `client_email`

5. **Run the Application:**
   ```bash
   streamlit run app.py
   ```
   The app will open at `http://localhost:8501`

### 🧪 Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests include:
- **Unit Tests** (`test_comparator.py`): Field matching logic, normalization, anomaly detection
- **Integration Tests** (`test_e2e_sheet.py`): Full verification flow with sample AFS + sheets data

### ☁️ Cloud Deployment

For production on **Streamlit Cloud** with **PostgreSQL (Neon)**:

See complete guide → [`DEPLOYMENT.md`](DEPLOYMENT.md)

Quick summary:
1. Rotate secrets (git-committed keys must be replaced)
2. Create Neon PostgreSQL database
3. Push code to GitHub (private repo)
4. Deploy on Streamlit Cloud with secrets configured

---

## 📊 Usage Scenarios

### Scenario 1: KYC Identity Verification Only
**Use case**: Verify that Aadhaar/PAN details match the AFS document

1. Go to **🪪 KYC Only** tab
2. Upload AFS PDF + Aadhaar + PAN images
3. Click "Verify KYC"
4. View match/mismatch report with color-coded badges
5. Optional: Send email to CRM officer

### Scenario 2: Google Sheet Audit Only
**Use case**: Verify that numeric data (amounts, percentages) in AFS match your project sheet

1. Go to **🔢 Sheet Audit Only** tab
2. Upload AFS PDF + provide Google Sheet ID
3. Click "Verify Against Sheet"
4. Review extracted vs. sheet values
5. Download PDF or email report

### Scenario 3: Full Verification (Unified Flow)
**Use case**: Do everything at once — KYC check + sheet audit in a single run

1. Go to **🛡️ Full Verification** tab
2. Upload AFS PDF + Aadhaar + PAN + provide Sheet ID
3. Click "Run Full Verification"
4. Get one comprehensive report with both checks
5. Email goes to CRM with badges for both KYC + Sheet status

### Scenario 4: Browse History
**Use case**: Re-download old reports, review past verifications

1. Go to **📚 History** tab
2. Browse all past verification records (searchable by buyer name, date)
3. Click any row to view/download the original PDF report

---

## 🔒 Security & Compliance

### Data Privacy
- **No KYC Persistence**: Aadhaar/PAN images are processed transiently via OpenAI API and **never stored** in cloud databases
- **Session-Only Processing**: Card images are converted to base64, sent to GPT-4o, and discarded after response
- **Secure Credentials**: API keys and email passwords stored in `.env` (local) or Streamlit Secrets (cloud), never in version control

### Compliance
- **Audit Trail**: Every verification is logged with timestamp, user email, and outcome in the database
- **Report History**: All generated PDFs can be re-downloaded from the History tab for compliance review
- **Field-Level Transparency**: Reports show exactly which fields matched and which had discrepancies

### Deployment Security
Before going live, follow **STEP 0** in [`DEPLOYMENT.md`](DEPLOYMENT.md):
- Rotate all leaked secrets (Google service account key, OpenAI key, Gmail app password)
- Remove committed `.env` files from git history
- Use Streamlit Secrets for cloud deployment (not `.env` files)

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Streamlit + Custom CSS | Multi-tab dashboard, document upload, results display |
| **AI/LLM** | OpenAI GPT-4o (Vision + Text) | Document understanding, field extraction, matching |
| **Document Processing** | MarkItDown, PyMuPDF (fitz) | PDF text extraction, image rasterization |
| **External APIs** | Google Sheets API, Gmail SMTP | Sheet data fetch, email notifications |
| **Data Layer** | SQLAlchemy ORM | Database abstraction (SQLite/PostgreSQL) |
| **Local DB** | SQLite | Development & lightweight deployments |
| **Cloud DB** | PostgreSQL (Neon) | Production deployments |
| **Report Generation** | fpdf2 | Professional branded PDF reports |
| **Testing** | pytest | Unit + integration tests |
| **Deployment** | Streamlit Cloud | Serverless hosting |

---

## 📈 Performance & Limits

- **Max File Size**: 15 MB per document (AFS PDF + images)
- **Max AFS Text**: 80,000 characters (~20k tokens) to leave room for system prompt + vision data
- **Processing Time**: ~30-45 seconds per verification (GPT-4o latency + sheet API calls)
- **Concurrent Users**: SQLite (local) = single user; PostgreSQL (cloud) = unlimited
- **Cost**: OpenAI API (~$0.10 per verification), Gmail (free), Neon (free tier or pay-as-you-go)

---

## 🐛 Troubleshooting

### "No module named 'openai'"
→ `pip install -r requirements.txt`

### "Google Sheets API error"
→ Check that service account JSON exists at `GOOGLE_SHEETS_CREDENTIALS_PATH`
→ Verify the Google Sheet is shared with the service account's `client_email`

### "SMTP authentication failed"
→ Ensure `SMTP_PASSWORD` is a 16-character **App Password**, not your Gmail password
→ Check that 2-Step Verification is enabled on your Google Account

### "Database locked" (SQLite only)
→ This is normal in Streamlit (multi-threaded). Use PostgreSQL for production.

### "GPT-4o image quality issues"
→ Upload clearer, well-lit photos of Aadhaar/PAN cards
→ The system upscales images 2x before sending to GPT-4o for better OCR

---

## 📝 License

This project is provided as-is for educational and commercial use in real estate KYC workflows.
