# S*EntryTrace

**Android Digital Forensics Workstation**

S*EntryTrace is a desktop forensic examination tool that performs automated security assessments of Android devices using the Mobile Verification Toolkit (MVT). It provides a professional web-based interface for conducting examinations, analyzing findings, managing evidence, and generating forensic audit reports.

**Author:** Kanishk Karam

---

## Features

### Examination
- Automated forensic examination pipeline with 9 stages
- Live examination activity terminal with color-coded log levels
- Real-time pipeline progress visualization
- Examination cancellation support
- Multiple independent examinations with full history

### Device Management
- Automatic device detection via ADB
- Device metadata collection (model, manufacturer, Android version, security patch, build fingerprint)
- USB debugging verification
- Device authorization state tracking

### Evidence & Integrity
- Structured evidence storage with per-examination isolation
- SHA-256 integrity hashing for all evidence files
- Evidence manifest generation with complete file inventory
- Evidence inventory browsable in the UI

### Findings
- MVT-powered forensic analysis of Android bugreport data
- Findings parsed from MVT output with severity classification
- Category-based organization (Suspicious, Informational, etc.)
- Human-readable explanations and interpretations

### Reports
- Professional A4 PDF forensic audit reports
- In-app PDF viewer
- Report regeneration support
- Report download
- 11-section report structure including:
  - Executive Summary
  - Device Information
  - Examination Timeline
  - Activity Log
  - Findings
  - Threat Intelligence Coverage
  - Evidence Inventory
  - Evidence Integrity
  - Warnings and Limitations
  - Technical Details
  - Collection Disclaimer

### History
- Persistent examination history across server restarts
- Browse and review any past examination
- Per-examination evidence, findings, and reports

---

## Architecture

```
S*EntryTrace
├── backend/          Python FastAPI backend
│   ├── app/
│   │   ├── api/      REST API routes (devices, scans, findings, reports)
│   │   ├── models/   Pydantic data models
│   │   ├── services/ Core services (scan, evidence, report, device, finding)
│   │   └── utils/    Utilities (hashing, subprocess, ADB client)
│   └── tests/        pytest test suite
├── frontend/         React + TypeScript + Vite frontend
│   └── src/
│       ├── api/      API client
│       └── components/ UI components
├── evidence/         Evidence storage (per-examination directories)
├── platform-tools/   Android SDK platform-tools (ADB)
└── mvt-main/         MVT source (upstream, unmodified)
```

---

## Requirements

- **Python** 3.11+
- **Node.js** 18+
- **Android SDK Platform-Tools** (ADB)
- **MVT** 2.0.0 (installed in the Python virtual environment)
- **Android device** with USB debugging enabled

### Python Dependencies
- FastAPI
- uvicorn
- fpdf2
- python-dateutil
- pydantic

### Frontend Dependencies
- React 19
- TypeScript
- Vite
- Lucide React (icons)

---

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd S_EntryTrace
```

### 2. Set Up Python Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
# or: source .venv/bin/activate  # Linux/Mac

pip install -r backend/requirements.txt
```

### 3. Install MVT
```bash
pip install mvt
```

### 4. Install Frontend Dependencies
```bash
cd frontend
npm install
cd ..
```

### 5. Verify ADB
Ensure `platform-tools/` contains `adb.exe` (Windows) or `adb` (Linux/Mac).

---

## How to Start

### Start Backend
```bash
# From project root
.venv\Scripts\activate
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start Frontend
```bash
# In a separate terminal
cd frontend
npm run dev
```

The application will be available at **http://localhost:5173/**

---

## How to Connect an Android Device

### Enable USB Debugging
1. Open **Settings** on the Android device
2. Navigate to **About Phone**
3. Tap **Build Number** 7 times to enable Developer Options
4. Go to **Settings > Developer Options**
5. Enable **USB Debugging**

### Connect via USB
1. Connect the device via USB cable
2. On the device, tap **Allow** when the USB debugging authorization prompt appears
3. S*EntryTrace will automatically detect the device

---

## How to Run an Examination

1. Connect an Android device via USB
2. Open S*EntryTrace in your browser (http://localhost:5173/)
3. Navigate to the **Examination** tab
4. Click **Start Examination**
5. Monitor the live examination pipeline and activity log
6. Once complete, navigate to:
   - **Findings** — View analysis results
   - **Evidence** — View collected evidence files and integrity hashes
   - **Reports** — Generate, view, or download the forensic audit report

---

## How to View Findings

1. Navigate to the **Findings** tab
2. View the summary: total observations, severity breakdown
3. Expand individual findings for explanations and interpretations
4. Review module analysis details

---

## How to View Evidence

1. Navigate to the **Evidence** tab
2. View the evidence manifest: file count, total size
3. Browse individual evidence files with SHA-256 hashes
4. Verify evidence integrity

---

## How to Generate/Download Reports

1. Navigate to the **Reports** tab
2. Click **Generate Report** (or the report is auto-generated after examination)
3. Click **View Report** to open the PDF in the in-app viewer
4. Click **Download Report** to save the PDF locally
5. Click **Regenerate Report** to create a fresh report from the examination data

---

## Known Limitations

- **Evidence Collection:** Only ADB read-only commands are used. This is NOT a full forensic device image.
- **MVT Coverage:** Analysis is limited to MVT-supported artifacts and indicators.
- **Not Legally Admissible:** This tool does not produce a legally admissible forensic acquisition. For legal proceedings, use a certified forensic examiner.
- **Root Detection:** Root status detection is best-effort and may not detect all rooting methods.
- **IOC Matching:** Requires a configured STIX2 indicator dataset. Without it, threat indicator matching is not performed.
- **Single Device:** Only one device can be connected at a time for examination.

---

## Security/Forensic Limitations

> **Important:** S*EntryTrace is a triage tool, not a comprehensive forensic platform.

- Evidence is collected via ADB, not via physical or logical acquisition
- The device owner could potentially tamper with ADB-accessible data
- Not all Android artifacts are accessible without root access
- Absence of findings does NOT confirm absence of threats
- Results should be interpreted by a qualified analyst

---

## Third-Party Attribution

### Mobile Verification Toolkit (MVT)
S*EntryTrace uses the **Mobile Verification Toolkit (MVT)** as its forensic analysis engine.

- **MVT** is developed by Amnesty International's Security Lab
- MVT is licensed under its own open-source license
- The MVT source code included in this project is unmodified
- For more information: https://github.com/mvt-project/mvt

### Other Dependencies
- **FastAPI** — MIT License
- **fpdf2** — LGPL License
- **React** — MIT License
- **Lucide Icons** — ISC License

---

## Running Tests

```bash
# Backend tests
.venv\Scripts\activate
python -m pytest backend/tests/ -v

# Frontend type checking
cd frontend
npx tsc --noEmit

# Frontend build
npm run build
```

---

**Author:** Kanishk Karam  
**Project:** S*EntryTrace — Android Digital Forensics Workstation
