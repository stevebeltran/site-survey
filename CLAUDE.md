# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DFR (Drone as a First Responder) Site Survey & Deployment Automation Suite. A Streamlit application that ingests GPS-tagged site survey photos, clusters them by proximity, performs infrastructure analysis, queries airspace/airfield data, and generates Word reports for drone deployment planning. Integrates with Google Drive, Gmail, and Calendar for team collaboration.

## Commands

```bash
# Run the Streamlit dashboard (primary interface)
streamlit run dashboard.py

# Run CLI pipeline
python main.py --source /path/to/images --output ./processed_sites --radius 90 --report "Report.docx"

# Run all tests
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_pipeline.py -v

# Install dependencies
pip install -r requirements.txt
```

No linter, formatter, or type checker is configured. No CI/CD pipelines exist. Deployment is manual via Streamlit Cloud (push to main auto-triggers).

## Architecture

**Layered module design** - four layers, no build system, all modules importable directly:

| Layer | Modules | Role |
|-------|---------|------|
| UI | `dashboard.py` | Streamlit app with tabs (Ingestion, Sites, Contacts, Reports), OAuth sidebar, Folium maps, session state management |
| Business Logic | `processor.py`, `analyzer.py`, `reporter.py` | Image EXIF extraction, transitive-closure clustering (default 90m radius), heuristic/API-based CV analysis, Word doc generation with embedded maps |
| Integration | `google_oauth.py`, `google_drive.py`, `gmail_lookup.py` | OAuth 2.0 flow (domain-locked to `@brincdrones.com`), Drive file ops via `GoogleDriveManager`, Gmail/Calendar contact extraction |
| CLI | `main.py` | Argparse orchestrator; launches dashboard if no CLI args |

**Processing pipeline flow:** Photos with GPS EXIF -> `processor.py` clusters by proximity -> `analyzer.py` classifies infrastructure -> `reporter.py` generates .docx with airspace/airfield queries -> `google_drive.py` uploads to Drive.

**Key patterns:**
- `GoogleDriveManager` is the central integration hub (most-connected node in the codebase graph). Auth priority: OAuth tokens > service account JSON > None (mock mode).
- Dashboard state lives in `st.session_state` (auth tokens, customer info, processed sites, Drive folder IDs).
- Image formats: JPEG, PNG, TIFF, WEBP, HEIC/HEIF. EXIF extraction uses `ExifRead` (not PIL) for HEIC compatibility.
- Geolocation: `geopy.Nominatim` for reverse geocoding, FAA REST API for airspace, Overpass API for airfields.

**Output structure:**
```
processed_sites/
  Agency_Name_YYYYMMDD_HHMMSS/
    Site_N_Name_Address/
      session_metadata.json
      *.jpg (original photos)
      engineering_layout.png
    Master_DFR_Site_Survey_Report.docx
```

## Secrets & Configuration

Runtime secrets go in `.streamlit/secrets.toml` (git-ignored). See `.streamlit/secrets.toml.template` for required keys: `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI`, `GOOGLE_DRIVE_TEAM_FOLDER_ID`, `TEAM_EMAILS`, and optionally `GOOGLE_DRIVE_CREDENTIALS` (service account JSON fallback).

## Graphify

A knowledge graph exists at `graphify-out/`. After modifying code, run `graphify update .` to keep it current.
