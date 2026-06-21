# Multi-Site Survey Platform — Design Spec

**Date:** 2026-06-21
**Author:** Steven Beltran / Claude
**Status:** Approved

---

## Overview

Extend the existing DFR Site Survey application into a comprehensive multi-site survey platform. A PM uploads photos from one or more buildings during a single survey. The system clusters photos by GPS proximity, enriches each cluster with GIS/FAA data, presents a unified checklist for PM input, and generates a dynamic engineering report that expands per candidate site.

### Constraints

- Zero API cost (except Gemini Flash free tier for building height estimation)
- DOCX output only (no PDF)
- Scoring/ranking deferred to a future phase
- CV pipeline deferred (heuristics + PM checklist fill CV fields for now)
- No native mobile app — Streamlit mobile browser support only

### Deliverables In Scope

1. Streamlit Site Survey App (extend existing)
2. Mobile-friendly photo upload workflow
3. Automated EXIF extraction (exists)
4. GIS enrichment engine (extend existing)
5. FAA airspace analysis engine (exists)
6. Annotated photo generation (exists — rooftop annotator)
7. Installer Quick Reference Page (new)
8. Engineering Report — DOCX (overhaul existing)
9. Structured JSON export (new)
10. CSV export (new)
11. API-ready data model (new)

### Deferred

- Automated AI image analysis (full CV pipeline — costs money at scale)
- Topography analysis engine (elevation profiles, coverage horizon)
- Scoring, ranking, comparison matrix, recommendation page
- PDF report output

---

## Section 1: Structured Data Model (`site_model.py`)

A new module defining typed dataclasses for the entire pipeline. Every stable field ID lives here.

### Data Structure

```
CandidateSite
├── identity: SiteIdentity
│   SITE_NAME, SITE_ID, AGENCY_NAME, SITE_ADDRESS,
│   SITE_LATITUDE, SITE_LONGITUDE, SITE_ELEVATION,
│   SURVEY_DATE, SURVEYOR
├── installation: InstallInfo
│   INSTALL_TYPE (Roof/Pole/Wall/Ground),
│   DOCK_TYPE (Single Dock/Dual Dock),
│   FUTURE_EXPANSION
├── access: AccessInfo
│   ACCESS_TYPE, ROOF_ACCESS, ESCORT_REQUIRED, KEY_REQUIRED,
│   AFTER_HOURS_ACCESS, PARKING_AVAILABLE
├── structure: StructuralInfo
│   BUILDING_HEIGHT, ROOF_TYPE, PARAPET_HEIGHT,
│   ROOF_CONDITION, STRUCTURAL_CONCERNS
├── dock: DockLocation
│   DOCK_LATITUDE, DOCK_LONGITUDE, DOCK_ELEVATION,
│   DISTANCE_TO_EDGE, DISTANCE_TO_POWER,
│   DISTANCE_TO_NETWORK, DISTANCE_TO_ANTENNA
├── electrical: ElectricalInfo
│   POWER_AVAILABLE, VOLTAGE_AVAILABLE, BREAKER_AVAILABLE,
│   DEDICATED_CIRCUIT, PANEL_LOCATION, DISTANCE_TO_POWER
├── network: NetworkInfo
│   ISP_PROVIDER, CONNECTION_TYPE, UPLOAD_SPEED,
│   DOWNLOAD_SPEED, STATIC_IP_AVAILABLE,
│   SWITCH_LOCATION, PATCH_PANEL_LOCATION, DISTANCE_TO_NETWORK
├── rf: RFInfo
│   ANTENNA_LATITUDE, ANTENNA_LONGITUDE, ANTENNA_ELEVATION,
│   LINE_OF_SIGHT_STATUS,
│   OBSTRUCTION_TREES, OBSTRUCTION_BUILDINGS,
│   OBSTRUCTION_WATER_TOWERS, OBSTRUCTION_CELL_TOWERS,
│   COVERAGE_DIRECTION
├── flight: FlightOps
│   PRIMARY_RESPONSE_AREA, LAUNCH_DIRECTION, EMERGENCY_LANDING_ZONE,
│   NEARBY_AIRPORTS, NEARBY_HELIPORTS,
│   AIRSPACE_CLASS, FLIGHT_RESTRICTIONS
├── photos: list[SurveyPhoto]
│   PHOTO_ID, file_path, category (Site/Installation/Infrastructure/RF/Access),
│   PHOTO_DATE, PHOTO_TIME, GPS_LATITUDE, GPS_LONGITUDE,
│   PHOTO_HEADING, PHOTO_ALTITUDE, annotations
├── scores: SiteScores (placeholder — deferred)
│   installation_score, engineering_score, rf_score, safety_score, overall_score
└── checklist_provenance: dict[str, str]
    Maps field ID → source ("auto" | "pm") to track which fields
    were auto-filled by the pipeline vs manually entered by the PM.
    Used by the report to indicate auto-filled vs PM-entered fields.
```

### Key Behaviors

- **`from_site_dict(data: dict) -> CandidateSite`** — converts existing site dicts from `processor.py` into the new model. Provides backward compatibility with current pipeline output.
- **SITE_ID generation** — auto-generated as `{AGENCY_NAME}_{SURVEY_DATE}_{N}` where N is the candidate site index (1-based). Example: `Chicago_PD_20260621_1`. Stable within a session, regenerated on reprocessing.
- **`to_json() -> dict`** — serializes to JSON using stable field IDs as keys. Used for `session_metadata.json` and JSON export.
- **`from_json(data: dict) -> CandidateSite`** — deserializes from JSON. Loads saved sessions.
- **`to_csv_row() -> dict`** — flattens all fields to a single dict for CSV export. Stable field IDs become column headers.
- **`compute_scores()`** — placeholder, returns None for all scores. Implemented in future phase.
- **`rank_sites(sites: list[CandidateSite]) -> list[CandidateSite]`** — placeholder static method. Returns sites in input order for now.

### Photo Categories

Each `SurveyPhoto` has a `category` field from the spec's required photo list:

| Category | Expected Photos |
|----------|----------------|
| Site | Building Front, Building Rear, Building Overview, Roof Overview, 360 Panorama |
| Installation | Proposed Dock Location, North/South/East/West Views |
| Infrastructure | Electrical Panel, Breaker Panel, Network Closet, Switch, Demarcation Point |
| RF | Antenna Location, Antenna North/South/East/West Views |
| Access | Roof Hatch, Ladder, Stairwell, Elevator, Access Gate |

---

## Section 2: Clustering Upgrades (`processor.py`)

### Current Behavior (Preserved)

- Radius-based transitive-closure clustering with configurable distance (default 90m)
- EXIF GPS extraction using dual-library fallback (exifread → Pillow)
- Reverse geocoding via Nominatim

### New Additions

**DBSCAN clustering option:**
- Add DBSCAN as an alternative clustering method using `scikit-learn`
- Better for irregular building layouts — finds density-based clusters without a fixed radius
- Dashboard gets a clustering method dropdown: `Radius (90m)` | `DBSCAN (auto)`
- Defaults to Radius to preserve current behavior

**Photo categorization:**
- After clustering, categorize each photo by filename heuristics (existing `analyzer.py` logic) into the five categories: Site, Installation, Infrastructure, RF, Access
- Uncategorized photos appear in the checklist UI for PM to assign a category via dropdown

**Output changes:**
- `processor.py` returns `list[CandidateSite]` instead of `list[dict]`
- Each `CandidateSite` gets auto-populated: `identity` (reverse geocode), `photos` (categorized), `flight` (airspace/airfield lookups)
- No changes to the clustering folder structure on disk or Google Drive upload

---

## Section 3: GIS Enrichment (`analyzer.py`)

### Existing (No Changes)

- Reverse geocoding (city, address) via Nominatim
- Airspace classification via FAA ArcGIS
- Nearest airfield via Overpass API

### New — Free Sources Only

| Field | Source | Method |
|-------|--------|--------|
| COUNTY_NAME | Nominatim | Extract from existing reverse geocode response |
| STATE_NAME | Nominatim | Extract from existing reverse geocode response |
| ZIP_CODE | Nominatim | Extract from existing reverse geocode response |
| SITE_ELEVATION | Open-Elevation API | Free, no key. `GET /api/v1/lookup?locations=lat,lng` |
| TERRAIN_TYPE | Open-Elevation + heuristic | Derive from elevation variance in small radius |
| JURISDICTION | Nominatim | City/county from existing response |
| AIRPORT_DISTANCE | Overpass API | Already queried, add distance calculation |
| HELIPORT_DISTANCE | Overpass API | Same query, filter for heliports |
| BUILDING_HEIGHT | Gemini Flash → Overpass → PM | See below |

### Building Height Estimation

Three-tier fallback:

1. **Gemini Flash free tier** — send the building overview photo, prompt: "How many floors does this building have? Estimate the building height in feet. Return JSON: {floors: int, estimated_height_ft: int}". Free tier allows 15 RPM, a survey uses 1-2 calls per site.
2. **Overpass API** — query OSM `building:levels` / `building:height` tags for the GPS coordinates. Good coverage in cities, sparse in rural areas.
3. **PM checklist** — PM enters floor count, system calculates estimate (commercial: floors × 13ft).

### Implementation

- New function `enrich_gis(site: CandidateSite)` in `analyzer.py`
- Called automatically after clustering, before the checklist is presented
- Graceful degradation — if any API is down, field stays empty for PM to fill
- No new dependencies; all REST calls via `requests` (already in requirements). Gemini calls via `google-generativeai` (new, lightweight dependency).

---

## Section 4: Unified Checklist (`dashboard.py`)

### Concept

One scrollable checklist per candidate site. Auto-filled where the pipeline has data, PM fills the rest. This is how all data enters the system — heuristics, GIS, FAA, and PM manual input all converge here.

### UI Design

- After processing, each `CandidateSite` is presented as a card in the dashboard
- Single checklist per site with category headers: Access, Structural, Electrical, Network, RF, Flight
- Fields auto-filled by the pipeline show a green indicator; empty fields show yellow
- Field types:
  - Toggles (yes/no): POWER_AVAILABLE, ESCORT_REQUIRED, etc.
  - Dropdowns: ROOF_TYPE (flat/pitched/membrane/metal), INSTALL_TYPE (Roof/Pole/Wall/Ground), etc.
  - Text inputs: ISP_PROVIDER, STRUCTURAL_CONCERNS, etc.
  - Number inputs: DISTANCE_TO_POWER, PARAPET_HEIGHT, etc.
- PM can override any auto-filled value

### Data Flow

```
processor.py clusters photos
    → CandidateSite objects created
        → enrich_gis() auto-fills GIS/FAA fields
            → analyzer.py auto-fills heuristic fields
                → Gemini Flash estimates building height
                    → Checklist UI shows all fields
                        → PM fills remaining, overrides as needed
                            → CandidateSite fully populated
                                → reporter.py generates report
```

### Scoring (Deferred)

The `SiteScores` section of the checklist card is hidden for now. When scoring is implemented, it will display computed scores below the checklist based on the filled fields.

---

## Section 5: Dynamic Report Generation (`reporter.py`)

### Report Structure

The report dynamically expands based on the number of candidate sites discovered.

```
1. Executive Summary
   - Agency name, survey date, surveyor
   - Number of candidate sites found
   - Map overview (Folium map exported as image)

2. Candidate Site {N} (repeated 1–N times)
   2a. Site Overview
       - Name, address, lat/lon/elevation, building height
       - Site map (zoomed Folium map for this cluster)
   2b. Site Photos
       - Organized by category: Site → Installation → Infrastructure → RF → Access
       - Annotated images included where available
   2c. Checklist Summary
       - Table of all filled fields, grouped by category
       - Auto-filled vs PM-entered indicated
   2d. Electrical Assessment
   2e. Network Assessment
   2f. RF Assessment
   2g. Airspace Assessment

3. Installer Quick Reference (1 page per site)
   - Condensed card: address, access method, power location,
     network location, antenna location, key contacts
   - Designed to be printed and carried on-site by install tech

4. Annotated Photo Appendix
   - All annotated engineering layouts, full size
```

### Key Changes From Current Reporter

- Current report iterates sites with a fixed section template — new version uses `CandidateSite` model for richer, category-organized sections
- Photos organized by category instead of flat list
- Installer Quick Reference is new — one-page condensed summary per site
- Annotated Photo Appendix collects all engineering layouts
- Still outputs DOCX via `python-docx`
- Still uploads to Google Drive
- Existing map/airspace/airfield rendering logic reused

### Dynamic Expansion Rule

The report generator never assumes a fixed number of locations:
- 1 cluster → 1 candidate section, 8–12 pages
- 4 clusters → 4 candidate sections, 25–40 pages
- N clusters → N candidate sections

---

## Section 6: Export & Data Portability

Three export formats beyond the DOCX report, all generated from the `CandidateSite` model.

### JSON Export

- `CandidateSite.to_json()` serializes the full model using stable field IDs as keys
- One JSON file per survey containing all candidate sites as an array
- Saved to Google Drive: `04_Metadata/survey_export.json`
- This is the API-ready data model — any future system can consume it

### CSV Export

- `CandidateSite.to_csv_row()` flattens each site to a single row
- One row per candidate site, columns are stable field IDs
- Multi-site survey = multi-row CSV
- Saved to Drive: `04_Metadata/survey_export.csv`

### Session Metadata (Enhanced)

- `session_metadata.json` stores the full `CandidateSite` model instead of raw dicts
- Backward compatible — `from_site_dict()` handles old-format metadata

### Dashboard UI

- Three download buttons after report generation: "Download DOCX" | "Download JSON" | "Download CSV"
- All three also uploaded to the Google Drive folder automatically

---

## Section 7: Mobile-Friendly Upload Workflow

### Approach

Streamlit's existing mobile browser support handles 80% of the work. Targeted improvements for PM field use.

### Improvements

- **Photo upload** — Streamlit's `file_uploader` already triggers camera roll or "Take Photo" on mobile. No custom app needed.
- **Photo category selection** — after upload, dropdown per photo for PM to assign category (Site/Installation/Infrastructure/RF/Access). Unassigned photos auto-categorized by filename heuristic.
- **Responsive layout** — use `st.columns` conditionally, stack vertically on narrow viewports. Streamlit's native mobile rendering handles most of this.
- **Simplified mobile flow** — PM's primary mobile task is upload photos + fill checklist. Map viewing and report generation happen on desktop/tablet.

### Out of Scope

- No native mobile app or PWA
- No custom camera integration
- No offline mode

---

## Module Responsibility Map

| Module | Responsibility | Change Type |
|--------|---------------|-------------|
| `site_model.py` | Typed data model, field IDs, serialization, export | **New** |
| `processor.py` | EXIF extraction, clustering (radius + DBSCAN), photo categorization | Extend |
| `analyzer.py` | Filename heuristics, GIS enrichment, Gemini height estimation | Extend |
| `reporter.py` | Dynamic DOCX report, installer quick reference, photo appendix | Overhaul |
| `dashboard.py` | Unified checklist UI, photo category assignment, export buttons, mobile layout | Extend |
| `google_drive.py` | Drive upload (unchanged) | None |
| `google_oauth.py` | OAuth flow (unchanged) | None |
| `gmail_lookup.py` | Contact extraction (unchanged) | None |

## New Dependencies

| Package | Purpose |
|---------|---------|
| `scikit-learn` | DBSCAN clustering |
| `google-generativeai` | Gemini Flash free tier for building height estimation |

## Stable Field IDs

These IDs are the contract between the data model, checklist UI, report templates, and export formats. They must not change once implemented.

### Site Identity
SITE_NAME, SITE_ID, AGENCY_NAME, SITE_ADDRESS, SITE_LATITUDE, SITE_LONGITUDE, SITE_ELEVATION, SURVEY_DATE, SURVEYOR

### Installation
INSTALL_TYPE, DOCK_TYPE, FUTURE_EXPANSION

### Access
ACCESS_TYPE, ROOF_ACCESS, ESCORT_REQUIRED, KEY_REQUIRED, AFTER_HOURS_ACCESS, PARKING_AVAILABLE

### Structural
BUILDING_HEIGHT, ROOF_TYPE, PARAPET_HEIGHT, ROOF_CONDITION, STRUCTURAL_CONCERNS

### Dock Location
DOCK_LATITUDE, DOCK_LONGITUDE, DOCK_ELEVATION, DISTANCE_TO_EDGE, DISTANCE_TO_POWER, DISTANCE_TO_NETWORK, DISTANCE_TO_ANTENNA

### Electrical
POWER_AVAILABLE, VOLTAGE_AVAILABLE, BREAKER_AVAILABLE, DEDICATED_CIRCUIT, PANEL_LOCATION, DISTANCE_TO_POWER

### Network
ISP_PROVIDER, CONNECTION_TYPE, UPLOAD_SPEED, DOWNLOAD_SPEED, STATIC_IP_AVAILABLE, SWITCH_LOCATION, PATCH_PANEL_LOCATION, DISTANCE_TO_NETWORK

### RF
ANTENNA_LATITUDE, ANTENNA_LONGITUDE, ANTENNA_ELEVATION, LINE_OF_SIGHT_STATUS, OBSTRUCTION_TREES, OBSTRUCTION_BUILDINGS, OBSTRUCTION_WATER_TOWERS, OBSTRUCTION_CELL_TOWERS, COVERAGE_DIRECTION

### Flight Operations
PRIMARY_RESPONSE_AREA, LAUNCH_DIRECTION, EMERGENCY_LANDING_ZONE, NEARBY_AIRPORTS, NEARBY_HELIPORTS, AIRSPACE_CLASS, FLIGHT_RESTRICTIONS

### Photos
PHOTO_ID, PHOTO_DATE, PHOTO_TIME, PHOTO_HEADING, PHOTO_ALTITUDE, ANNOTATED_PHOTO_01, ANNOTATED_PHOTO_02, ANNOTATED_PHOTO_03
