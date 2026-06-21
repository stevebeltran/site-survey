# Multi-Site Survey Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the DFR Site Survey app with a typed data model, DBSCAN clustering, GIS enrichment, unified PM checklist, dynamic multi-site DOCX report, and JSON/CSV export.

**Architecture:** Introduce `site_model.py` as a new typed data model layer with dataclasses for all stable field IDs. Extend `processor.py` (DBSCAN), `analyzer.py` (GIS enrichment + Gemini height), `reporter.py` (dynamic report overhaul), and `dashboard.py` (checklist UI + exports). Google Drive remains the persistence layer.

**Tech Stack:** Python 3.10+, Streamlit, python-docx, scikit-learn (DBSCAN), google-generativeai (Gemini Flash free tier), geopy, requests, folium, dataclasses (stdlib).

**Spec:** `docs/superpowers/specs/2026-06-21-multi-site-survey-platform-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `site_model.py` | **Create** | Typed dataclasses for CandidateSite and all sub-models, serialization, export |
| `processor.py` | Modify | Add DBSCAN clustering, return `list[CandidateSite]` |
| `analyzer.py` | Modify | Add `enrich_gis()`, Gemini height estimation, photo categorization |
| `reporter.py` | Modify | Dynamic report with per-category photos, installer quick ref, appendix |
| `dashboard.py` | Modify | Unified checklist UI, photo category assignment, export buttons |
| `requirements.txt` | Modify | Add `scikit-learn`, `google-generativeai` |
| `tests/test_site_model.py` | **Create** | Tests for data model, serialization, export |
| `tests/test_clustering.py` | **Create** | Tests for DBSCAN clustering |
| `tests/test_gis_enrichment.py` | **Create** | Tests for GIS enrichment |
| `tests/test_report_dynamic.py` | **Create** | Tests for dynamic report generation |

---

## Task 1: Data Model — SurveyPhoto and Sub-Models

**Files:**
- Create: `site_model.py`
- Create: `tests/test_site_model.py`

- [ ] **Step 1: Write failing tests for SurveyPhoto and sub-model dataclasses**

```python
# tests/test_site_model.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from site_model import (
    SurveyPhoto, SiteIdentity, InstallInfo, AccessInfo,
    StructuralInfo, DockLocation, ElectricalInfo, NetworkInfo,
    RFInfo, FlightOps, SiteScores,
)


class TestSurveyPhoto:
    def test_create_with_required_fields(self):
        photo = SurveyPhoto(
            photo_id="IMG_001",
            file_path="/path/to/img.jpg",
            category="Site",
        )
        assert photo.photo_id == "IMG_001"
        assert photo.category == "Site"
        assert photo.gps_latitude is None
        assert photo.annotations == []

    def test_to_json_roundtrip(self):
        photo = SurveyPhoto(
            photo_id="IMG_002",
            file_path="/path/to/img.jpg",
            category="Infrastructure",
            gps_latitude=41.862,
            gps_longitude=-87.661,
            photo_date="2026-06-21",
            photo_time="14:30:00",
            photo_heading=270.0,
            photo_altitude=15.0,
        )
        data = photo.to_json()
        restored = SurveyPhoto.from_json(data)
        assert restored.photo_id == "IMG_002"
        assert restored.gps_latitude == 41.862
        assert restored.photo_heading == 270.0

    def test_valid_categories(self):
        for cat in ["Site", "Installation", "Infrastructure", "RF", "Access"]:
            photo = SurveyPhoto(photo_id="X", file_path="x.jpg", category=cat)
            assert photo.category == cat


class TestSiteIdentity:
    def test_create_identity(self):
        identity = SiteIdentity(
            site_name="Police HQ",
            site_id="Chicago_PD_20260621_1",
            agency_name="Chicago Police Department",
            site_address="1412 S Blue Island Ave, Chicago, IL",
            site_latitude=41.862644,
            site_longitude=-87.661244,
        )
        assert identity.site_name == "Police HQ"
        assert identity.site_elevation is None
        assert identity.survey_date is None

    def test_identity_to_json(self):
        identity = SiteIdentity(
            site_name="HQ",
            site_id="CPD_20260621_1",
            agency_name="CPD",
            site_address="123 Main St",
            site_latitude=41.0,
            site_longitude=-87.0,
            site_elevation=200.0,
            survey_date="2026-06-21",
            surveyor="Steven Beltran",
        )
        data = identity.to_json()
        assert data["SITE_NAME"] == "HQ"
        assert data["SITE_ELEVATION"] == 200.0
        assert data["SURVEYOR"] == "Steven Beltran"
        restored = SiteIdentity.from_json(data)
        assert restored.site_name == "HQ"
        assert restored.surveyor == "Steven Beltran"


class TestElectricalInfo:
    def test_defaults_all_none(self):
        info = ElectricalInfo()
        assert info.power_available is None
        assert info.voltage_available is None
        assert info.distance_to_power is None

    def test_to_json_uses_stable_field_ids(self):
        info = ElectricalInfo(power_available=True, voltage_available="120V")
        data = info.to_json()
        assert data["POWER_AVAILABLE"] is True
        assert data["VOLTAGE_AVAILABLE"] == "120V"
        assert data["DEDICATED_CIRCUIT"] is None


class TestNetworkInfo:
    def test_to_json_roundtrip(self):
        info = NetworkInfo(
            isp_provider="Comcast",
            upload_speed="50 Mbps",
            download_speed="200 Mbps",
        )
        data = info.to_json()
        restored = NetworkInfo.from_json(data)
        assert restored.isp_provider == "Comcast"
        assert restored.upload_speed == "50 Mbps"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "G:/My Drive/PRIVATE NO ACCESS/Python/app/Monster/ant"
python -m pytest tests/test_site_model.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'site_model'`

- [ ] **Step 3: Implement SurveyPhoto and all sub-model dataclasses**

```python
# site_model.py
"""Typed data model for DFR Site Survey candidate sites.

All stable field IDs are defined here as dataclass fields.
Serialization uses the uppercase FIELD_ID format for JSON/CSV export.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ── Photo ──────────────────────────────────────────────────────────

VALID_PHOTO_CATEGORIES = ["Site", "Installation", "Infrastructure", "RF", "Access"]


@dataclass
class SurveyPhoto:
    photo_id: str
    file_path: str
    category: str  # One of VALID_PHOTO_CATEGORIES
    photo_date: Optional[str] = None
    photo_time: Optional[str] = None
    gps_latitude: Optional[float] = None
    gps_longitude: Optional[float] = None
    photo_heading: Optional[float] = None
    photo_altitude: Optional[float] = None
    annotations: list = field(default_factory=list)
    selected_for_report: bool = True

    def to_json(self) -> dict:
        return {
            "PHOTO_ID": self.photo_id,
            "file_path": self.file_path,
            "category": self.category,
            "PHOTO_DATE": self.photo_date,
            "PHOTO_TIME": self.photo_time,
            "GPS_LATITUDE": self.gps_latitude,
            "GPS_LONGITUDE": self.gps_longitude,
            "PHOTO_HEADING": self.photo_heading,
            "PHOTO_ALTITUDE": self.photo_altitude,
            "annotations": self.annotations,
            "selected_for_report": self.selected_for_report,
        }

    @classmethod
    def from_json(cls, data: dict) -> SurveyPhoto:
        return cls(
            photo_id=data.get("PHOTO_ID", data.get("photo_id", "")),
            file_path=data.get("file_path", ""),
            category=data.get("category", "Site"),
            photo_date=data.get("PHOTO_DATE"),
            photo_time=data.get("PHOTO_TIME"),
            gps_latitude=data.get("GPS_LATITUDE"),
            gps_longitude=data.get("GPS_LONGITUDE"),
            photo_heading=data.get("PHOTO_HEADING"),
            photo_altitude=data.get("PHOTO_ALTITUDE"),
            annotations=data.get("annotations", []),
            selected_for_report=data.get("selected_for_report", True),
        )


# ── Sub-models ─────────────────────────────────────────────────────

@dataclass
class SiteIdentity:
    site_name: str
    site_id: str
    agency_name: str
    site_address: str
    site_latitude: float
    site_longitude: float
    site_elevation: Optional[float] = None
    county: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    jurisdiction: Optional[str] = None
    survey_date: Optional[str] = None
    surveyor: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "SITE_NAME": self.site_name,
            "SITE_ID": self.site_id,
            "AGENCY_NAME": self.agency_name,
            "SITE_ADDRESS": self.site_address,
            "SITE_LATITUDE": self.site_latitude,
            "SITE_LONGITUDE": self.site_longitude,
            "SITE_ELEVATION": self.site_elevation,
            "COUNTY_NAME": self.county,
            "STATE_NAME": self.state,
            "ZIP_CODE": self.zip_code,
            "JURISDICTION": self.jurisdiction,
            "SURVEY_DATE": self.survey_date,
            "SURVEYOR": self.surveyor,
        }

    @classmethod
    def from_json(cls, data: dict) -> SiteIdentity:
        return cls(
            site_name=data["SITE_NAME"],
            site_id=data["SITE_ID"],
            agency_name=data["AGENCY_NAME"],
            site_address=data["SITE_ADDRESS"],
            site_latitude=data["SITE_LATITUDE"],
            site_longitude=data["SITE_LONGITUDE"],
            site_elevation=data.get("SITE_ELEVATION"),
            county=data.get("COUNTY_NAME"),
            state=data.get("STATE_NAME"),
            zip_code=data.get("ZIP_CODE"),
            jurisdiction=data.get("JURISDICTION"),
            survey_date=data.get("SURVEY_DATE"),
            surveyor=data.get("SURVEYOR"),
        )


@dataclass
class InstallInfo:
    install_type: Optional[str] = None   # Roof / Pole / Wall / Ground
    dock_type: Optional[str] = None      # Single Dock / Dual Dock
    future_expansion: Optional[bool] = None

    def to_json(self) -> dict:
        return {
            "INSTALL_TYPE": self.install_type,
            "DOCK_TYPE": self.dock_type,
            "FUTURE_EXPANSION": self.future_expansion,
        }

    @classmethod
    def from_json(cls, data: dict) -> InstallInfo:
        return cls(
            install_type=data.get("INSTALL_TYPE"),
            dock_type=data.get("DOCK_TYPE"),
            future_expansion=data.get("FUTURE_EXPANSION"),
        )


@dataclass
class AccessInfo:
    access_type: Optional[str] = None
    roof_access: Optional[str] = None
    escort_required: Optional[bool] = None
    key_required: Optional[bool] = None
    after_hours_access: Optional[bool] = None
    parking_available: Optional[bool] = None

    def to_json(self) -> dict:
        return {
            "ACCESS_TYPE": self.access_type,
            "ROOF_ACCESS": self.roof_access,
            "ESCORT_REQUIRED": self.escort_required,
            "KEY_REQUIRED": self.key_required,
            "AFTER_HOURS_ACCESS": self.after_hours_access,
            "PARKING_AVAILABLE": self.parking_available,
        }

    @classmethod
    def from_json(cls, data: dict) -> AccessInfo:
        return cls(
            access_type=data.get("ACCESS_TYPE"),
            roof_access=data.get("ROOF_ACCESS"),
            escort_required=data.get("ESCORT_REQUIRED"),
            key_required=data.get("KEY_REQUIRED"),
            after_hours_access=data.get("AFTER_HOURS_ACCESS"),
            parking_available=data.get("PARKING_AVAILABLE"),
        )


@dataclass
class StructuralInfo:
    building_height: Optional[float] = None
    roof_type: Optional[str] = None
    parapet_height: Optional[float] = None
    roof_condition: Optional[str] = None
    structural_concerns: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "BUILDING_HEIGHT": self.building_height,
            "ROOF_TYPE": self.roof_type,
            "PARAPET_HEIGHT": self.parapet_height,
            "ROOF_CONDITION": self.roof_condition,
            "STRUCTURAL_CONCERNS": self.structural_concerns,
        }

    @classmethod
    def from_json(cls, data: dict) -> StructuralInfo:
        return cls(
            building_height=data.get("BUILDING_HEIGHT"),
            roof_type=data.get("ROOF_TYPE"),
            parapet_height=data.get("PARAPET_HEIGHT"),
            roof_condition=data.get("ROOF_CONDITION"),
            structural_concerns=data.get("STRUCTURAL_CONCERNS"),
        )


@dataclass
class DockLocation:
    dock_latitude: Optional[float] = None
    dock_longitude: Optional[float] = None
    dock_elevation: Optional[float] = None
    distance_to_edge: Optional[float] = None
    distance_to_power: Optional[float] = None
    distance_to_network: Optional[float] = None
    distance_to_antenna: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "DOCK_LATITUDE": self.dock_latitude,
            "DOCK_LONGITUDE": self.dock_longitude,
            "DOCK_ELEVATION": self.dock_elevation,
            "DISTANCE_TO_EDGE": self.distance_to_edge,
            "DISTANCE_TO_POWER": self.distance_to_power,
            "DISTANCE_TO_NETWORK": self.distance_to_network,
            "DISTANCE_TO_ANTENNA": self.distance_to_antenna,
        }

    @classmethod
    def from_json(cls, data: dict) -> DockLocation:
        return cls(
            dock_latitude=data.get("DOCK_LATITUDE"),
            dock_longitude=data.get("DOCK_LONGITUDE"),
            dock_elevation=data.get("DOCK_ELEVATION"),
            distance_to_edge=data.get("DISTANCE_TO_EDGE"),
            distance_to_power=data.get("DISTANCE_TO_POWER"),
            distance_to_network=data.get("DISTANCE_TO_NETWORK"),
            distance_to_antenna=data.get("DISTANCE_TO_ANTENNA"),
        )


@dataclass
class ElectricalInfo:
    power_available: Optional[bool] = None
    voltage_available: Optional[str] = None
    breaker_available: Optional[bool] = None
    dedicated_circuit: Optional[bool] = None
    panel_location: Optional[str] = None
    distance_to_power: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "POWER_AVAILABLE": self.power_available,
            "VOLTAGE_AVAILABLE": self.voltage_available,
            "BREAKER_AVAILABLE": self.breaker_available,
            "DEDICATED_CIRCUIT": self.dedicated_circuit,
            "PANEL_LOCATION": self.panel_location,
            "DISTANCE_TO_POWER": self.distance_to_power,
        }

    @classmethod
    def from_json(cls, data: dict) -> ElectricalInfo:
        return cls(
            power_available=data.get("POWER_AVAILABLE"),
            voltage_available=data.get("VOLTAGE_AVAILABLE"),
            breaker_available=data.get("BREAKER_AVAILABLE"),
            dedicated_circuit=data.get("DEDICATED_CIRCUIT"),
            panel_location=data.get("PANEL_LOCATION"),
            distance_to_power=data.get("DISTANCE_TO_POWER"),
        )


@dataclass
class NetworkInfo:
    isp_provider: Optional[str] = None
    connection_type: Optional[str] = None
    upload_speed: Optional[str] = None
    download_speed: Optional[str] = None
    static_ip_available: Optional[bool] = None
    switch_location: Optional[str] = None
    patch_panel_location: Optional[str] = None
    distance_to_network: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "ISP_PROVIDER": self.isp_provider,
            "CONNECTION_TYPE": self.connection_type,
            "UPLOAD_SPEED": self.upload_speed,
            "DOWNLOAD_SPEED": self.download_speed,
            "STATIC_IP_AVAILABLE": self.static_ip_available,
            "SWITCH_LOCATION": self.switch_location,
            "PATCH_PANEL_LOCATION": self.patch_panel_location,
            "DISTANCE_TO_NETWORK": self.distance_to_network,
        }

    @classmethod
    def from_json(cls, data: dict) -> NetworkInfo:
        return cls(
            isp_provider=data.get("ISP_PROVIDER"),
            connection_type=data.get("CONNECTION_TYPE"),
            upload_speed=data.get("UPLOAD_SPEED"),
            download_speed=data.get("DOWNLOAD_SPEED"),
            static_ip_available=data.get("STATIC_IP_AVAILABLE"),
            switch_location=data.get("SWITCH_LOCATION"),
            patch_panel_location=data.get("PATCH_PANEL_LOCATION"),
            distance_to_network=data.get("DISTANCE_TO_NETWORK"),
        )


@dataclass
class RFInfo:
    antenna_latitude: Optional[float] = None
    antenna_longitude: Optional[float] = None
    antenna_elevation: Optional[float] = None
    line_of_sight_status: Optional[str] = None
    obstruction_trees: Optional[bool] = None
    obstruction_buildings: Optional[bool] = None
    obstruction_water_towers: Optional[bool] = None
    obstruction_cell_towers: Optional[bool] = None
    coverage_direction: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "ANTENNA_LATITUDE": self.antenna_latitude,
            "ANTENNA_LONGITUDE": self.antenna_longitude,
            "ANTENNA_ELEVATION": self.antenna_elevation,
            "LINE_OF_SIGHT_STATUS": self.line_of_sight_status,
            "OBSTRUCTION_TREES": self.obstruction_trees,
            "OBSTRUCTION_BUILDINGS": self.obstruction_buildings,
            "OBSTRUCTION_WATER_TOWERS": self.obstruction_water_towers,
            "OBSTRUCTION_CELL_TOWERS": self.obstruction_cell_towers,
            "COVERAGE_DIRECTION": self.coverage_direction,
        }

    @classmethod
    def from_json(cls, data: dict) -> RFInfo:
        return cls(
            antenna_latitude=data.get("ANTENNA_LATITUDE"),
            antenna_longitude=data.get("ANTENNA_LONGITUDE"),
            antenna_elevation=data.get("ANTENNA_ELEVATION"),
            line_of_sight_status=data.get("LINE_OF_SIGHT_STATUS"),
            obstruction_trees=data.get("OBSTRUCTION_TREES"),
            obstruction_buildings=data.get("OBSTRUCTION_BUILDINGS"),
            obstruction_water_towers=data.get("OBSTRUCTION_WATER_TOWERS"),
            obstruction_cell_towers=data.get("OBSTRUCTION_CELL_TOWERS"),
            coverage_direction=data.get("COVERAGE_DIRECTION"),
        )


@dataclass
class FlightOps:
    primary_response_area: Optional[str] = None
    launch_direction: Optional[str] = None
    emergency_landing_zone: Optional[str] = None
    nearby_airports: Optional[str] = None
    nearby_heliports: Optional[str] = None
    airspace_class: Optional[str] = None
    flight_restrictions: Optional[str] = None

    def to_json(self) -> dict:
        return {
            "PRIMARY_RESPONSE_AREA": self.primary_response_area,
            "LAUNCH_DIRECTION": self.launch_direction,
            "EMERGENCY_LANDING_ZONE": self.emergency_landing_zone,
            "NEARBY_AIRPORTS": self.nearby_airports,
            "NEARBY_HELIPORTS": self.nearby_heliports,
            "AIRSPACE_CLASS": self.airspace_class,
            "FLIGHT_RESTRICTIONS": self.flight_restrictions,
        }

    @classmethod
    def from_json(cls, data: dict) -> FlightOps:
        return cls(
            primary_response_area=data.get("PRIMARY_RESPONSE_AREA"),
            launch_direction=data.get("LAUNCH_DIRECTION"),
            emergency_landing_zone=data.get("EMERGENCY_LANDING_ZONE"),
            nearby_airports=data.get("NEARBY_AIRPORTS"),
            nearby_heliports=data.get("NEARBY_HELIPORTS"),
            airspace_class=data.get("AIRSPACE_CLASS"),
            flight_restrictions=data.get("FLIGHT_RESTRICTIONS"),
        )


@dataclass
class SiteScores:
    """Placeholder — scoring deferred to future phase."""
    installation_score: Optional[float] = None
    engineering_score: Optional[float] = None
    rf_score: Optional[float] = None
    safety_score: Optional[float] = None
    overall_score: Optional[float] = None

    def to_json(self) -> dict:
        return {
            "INSTALLATION_SCORE": self.installation_score,
            "ENGINEERING_SCORE": self.engineering_score,
            "RF_SCORE": self.rf_score,
            "SAFETY_SCORE": self.safety_score,
            "OVERALL_SCORE": self.overall_score,
        }

    @classmethod
    def from_json(cls, data: dict) -> SiteScores:
        return cls(
            installation_score=data.get("INSTALLATION_SCORE"),
            engineering_score=data.get("ENGINEERING_SCORE"),
            rf_score=data.get("RF_SCORE"),
            safety_score=data.get("SAFETY_SCORE"),
            overall_score=data.get("OVERALL_SCORE"),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_site_model.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add site_model.py tests/test_site_model.py
git commit -m "feat: add SurveyPhoto and sub-model dataclasses with serialization"
```

---

## Task 2: Data Model — CandidateSite

**Files:**
- Modify: `site_model.py`
- Modify: `tests/test_site_model.py`

- [ ] **Step 1: Write failing tests for CandidateSite**

```python
# Append to tests/test_site_model.py
from site_model import CandidateSite
import json
import csv
import io


class TestCandidateSite:
    def _make_site(self, site_id="CPD_20260621_1", name="Police HQ"):
        return CandidateSite(
            identity=SiteIdentity(
                site_name=name,
                site_id=site_id,
                agency_name="Chicago PD",
                site_address="1412 S Blue Island Ave",
                site_latitude=41.862644,
                site_longitude=-87.661244,
                site_elevation=180.0,
                survey_date="2026-06-21",
                surveyor="Steven Beltran",
            ),
            photos=[
                SurveyPhoto(
                    photo_id="IMG_001",
                    file_path="/path/001.jpg",
                    category="Site",
                    gps_latitude=41.862644,
                    gps_longitude=-87.661244,
                ),
            ],
        )

    def test_create_with_defaults(self):
        site = self._make_site()
        assert site.identity.site_name == "Police HQ"
        assert site.installation.install_type is None
        assert site.electrical.power_available is None
        assert site.scores.overall_score is None
        assert len(site.photos) == 1

    def test_to_json_roundtrip(self):
        site = self._make_site()
        site.electrical.power_available = True
        site.checklist_provenance["POWER_AVAILABLE"] = "pm"
        data = site.to_json()
        restored = CandidateSite.from_json(data)
        assert restored.identity.site_id == "CPD_20260621_1"
        assert restored.electrical.power_available is True
        assert restored.checklist_provenance["POWER_AVAILABLE"] == "pm"
        assert len(restored.photos) == 1

    def test_to_csv_row_flat_dict(self):
        site = self._make_site()
        site.electrical.power_available = True
        row = site.to_csv_row()
        assert row["SITE_NAME"] == "Police HQ"
        assert row["SITE_ID"] == "CPD_20260621_1"
        assert row["POWER_AVAILABLE"] is True
        assert row["SITE_LATITUDE"] == 41.862644

    def test_to_json_string(self):
        site = self._make_site()
        json_str = json.dumps(site.to_json(), indent=2)
        parsed = json.loads(json_str)
        assert parsed["identity"]["SITE_NAME"] == "Police HQ"


class TestFromSiteDict:
    def test_convert_legacy_site_dict(self):
        """Convert the dict format returned by processor.py into CandidateSite."""
        legacy = {
            "site_id": "SITE-001",
            "folder_name": "Site_1_Chicago_1412_S_Blue_Island",
            "folder_path": "/output/Site_1",
            "batch_folder_path": "/output",
            "address": "1412 S Blue Island Ave, Chicago, Cook County, Illinois, US",
            "city": "Chicago",
            "agency_name": "Chicago Police Department",
            "latitude": 41.862644,
            "longitude": -87.661244,
            "images": [
                {
                    "path": "/raw/001.jpg",
                    "filename": "building_front.jpg",
                    "lat": 41.862644,
                    "lon": -87.661244,
                    "time": "2026-06-21 14:30:00",
                    "dest_path": "/output/Site_1/building_front.jpg",
                },
            ],
        }
        site = CandidateSite.from_site_dict(legacy)
        assert site.identity.site_name == "Chicago"
        assert site.identity.agency_name == "Chicago Police Department"
        assert site.identity.site_latitude == 41.862644
        assert len(site.photos) == 1
        assert site.photos[0].file_path == "/output/Site_1/building_front.jpg"

    def test_missing_optional_fields(self):
        legacy = {
            "site_id": "SITE-002",
            "address": "Unknown",
            "latitude": 40.0,
            "longitude": -88.0,
            "images": [],
        }
        site = CandidateSite.from_site_dict(legacy)
        assert site.identity.site_name == "Unknown"
        assert site.identity.agency_name == ""
        assert site.photos == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_site_model.py::TestCandidateSite -v
python -m pytest tests/test_site_model.py::TestFromSiteDict -v
```

Expected: FAIL — `ImportError: cannot import name 'CandidateSite'`

- [ ] **Step 3: Implement CandidateSite dataclass**

Add to the bottom of `site_model.py`:

```python
# ── Candidate Site (top-level model) ───────────────────────────────

PHOTO_CATEGORY_KEYWORDS = {
    "Site": ["front", "rear", "overview", "building", "panorama", "360"],
    "Installation": ["dock", "proposed", "north_view", "south_view", "east_view", "west_view"],
    "Infrastructure": ["panel", "breaker", "network", "closet", "switch", "demarc"],
    "RF": ["antenna", "rf", "radio", "transmit"],
    "Access": ["hatch", "ladder", "stair", "elevator", "gate", "access"],
}


def categorize_photo_by_filename(filename: str) -> str:
    """Guess photo category from filename keywords. Returns 'Site' as default."""
    lower = filename.lower()
    for category, keywords in PHOTO_CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return category
    return "Site"


@dataclass
class CandidateSite:
    identity: SiteIdentity
    installation: InstallInfo = field(default_factory=InstallInfo)
    access: AccessInfo = field(default_factory=AccessInfo)
    structure: StructuralInfo = field(default_factory=StructuralInfo)
    dock: DockLocation = field(default_factory=DockLocation)
    electrical: ElectricalInfo = field(default_factory=ElectricalInfo)
    network: NetworkInfo = field(default_factory=NetworkInfo)
    rf: RFInfo = field(default_factory=RFInfo)
    flight: FlightOps = field(default_factory=FlightOps)
    photos: list = field(default_factory=list)  # list[SurveyPhoto]
    scores: SiteScores = field(default_factory=SiteScores)
    checklist_provenance: dict = field(default_factory=dict)  # field_id -> "auto" | "pm"

    def to_json(self) -> dict:
        return {
            "identity": self.identity.to_json(),
            "installation": self.installation.to_json(),
            "access": self.access.to_json(),
            "structure": self.structure.to_json(),
            "dock": self.dock.to_json(),
            "electrical": self.electrical.to_json(),
            "network": self.network.to_json(),
            "rf": self.rf.to_json(),
            "flight": self.flight.to_json(),
            "photos": [p.to_json() for p in self.photos],
            "scores": self.scores.to_json(),
            "checklist_provenance": dict(self.checklist_provenance),
        }

    @classmethod
    def from_json(cls, data: dict) -> CandidateSite:
        return cls(
            identity=SiteIdentity.from_json(data["identity"]),
            installation=InstallInfo.from_json(data.get("installation", {})),
            access=AccessInfo.from_json(data.get("access", {})),
            structure=StructuralInfo.from_json(data.get("structure", {})),
            dock=DockLocation.from_json(data.get("dock", {})),
            electrical=ElectricalInfo.from_json(data.get("electrical", {})),
            network=NetworkInfo.from_json(data.get("network", {})),
            rf=RFInfo.from_json(data.get("rf", {})),
            flight=FlightOps.from_json(data.get("flight", {})),
            photos=[SurveyPhoto.from_json(p) for p in data.get("photos", [])],
            scores=SiteScores.from_json(data.get("scores", {})),
            checklist_provenance=data.get("checklist_provenance", {}),
        )

    @classmethod
    def from_site_dict(cls, data: dict) -> CandidateSite:
        """Convert legacy site dict from processor.py into CandidateSite."""
        city = data.get("city") or ""
        address = data.get("address", "")
        site_name = city if city else address.split(",")[0] if address else "Unknown"

        identity = SiteIdentity(
            site_name=site_name,
            site_id=data.get("site_id", ""),
            agency_name=data.get("agency_name", ""),
            site_address=address,
            site_latitude=data.get("latitude", 0.0),
            site_longitude=data.get("longitude", 0.0),
        )

        photos = []
        for img in data.get("images", []):
            filename = img.get("filename", os.path.basename(img.get("path", "")))
            file_path = img.get("dest_path", img.get("path", ""))
            photo = SurveyPhoto(
                photo_id=filename,
                file_path=file_path,
                category=categorize_photo_by_filename(filename),
                gps_latitude=img.get("lat"),
                gps_longitude=img.get("lon"),
                photo_date=str(img.get("time", "")).split(" ")[0] if img.get("time") else None,
                photo_time=str(img.get("time", "")).split(" ")[1] if img.get("time") and " " in str(img.get("time")) else None,
            )
            photos.append(photo)

        # Carry forward analysis data if present
        site = cls(identity=identity, photos=photos)

        analysis = data.get("analysis", {})
        if analysis:
            site.access.roof_access = analysis.get("roof_access")
            site.structure.roof_type = analysis.get("roof_type")

        airspace = data.get("airspace", {})
        if airspace:
            site.flight.airspace_class = airspace.get("designator") or airspace.get("airspace_class")

        airfield = data.get("airfield_info", {})
        if airfield:
            site.flight.nearby_airports = airfield.get("name")

        return site

    def to_csv_row(self) -> dict:
        """Flatten all fields into a single dict for CSV export."""
        row = {}
        for sub in [self.identity, self.installation, self.access,
                     self.structure, self.dock, self.electrical,
                     self.network, self.rf, self.flight, self.scores]:
            row.update(sub.to_json())
        return row

    def compute_scores(self):
        """Placeholder — scoring deferred."""
        pass

    @staticmethod
    def rank_sites(sites: list) -> list:
        """Placeholder — returns sites in input order."""
        return list(sites)
```

Add `import os` to the top of `site_model.py` if not already there.

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_site_model.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add site_model.py tests/test_site_model.py
git commit -m "feat: add CandidateSite model with from_site_dict and export methods"
```

---

## Task 3: DBSCAN Clustering

**Files:**
- Modify: `processor.py` (add `cluster_images_dbscan` function)
- Modify: `requirements.txt` (add `scikit-learn`)
- Create: `tests/test_clustering.py`

- [ ] **Step 1: Write failing tests for DBSCAN clustering**

```python
# tests/test_clustering.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from processor import cluster_images_dbscan


class TestDBSCANClustering:
    def test_two_distinct_clusters(self):
        """Photos at two locations ~500m apart should form 2 clusters."""
        images = [
            {"path": "a1.jpg", "lat": 41.862644, "lon": -87.661244, "time": None},
            {"path": "a2.jpg", "lat": 41.862700, "lon": -87.661300, "time": None},
            {"path": "b1.jpg", "lat": 41.867000, "lon": -87.665000, "time": None},
            {"path": "b2.jpg", "lat": 41.867050, "lon": -87.665050, "time": None},
        ]
        clusters = cluster_images_dbscan(images)
        assert len(clusters) == 2
        cluster_sizes = sorted([len(c) for c in clusters])
        assert cluster_sizes == [2, 2]

    def test_single_cluster(self):
        """All photos within 50m should form 1 cluster."""
        images = [
            {"path": "a1.jpg", "lat": 41.862644, "lon": -87.661244, "time": None},
            {"path": "a2.jpg", "lat": 41.862650, "lon": -87.661250, "time": None},
            {"path": "a3.jpg", "lat": 41.862660, "lon": -87.661260, "time": None},
        ]
        clusters = cluster_images_dbscan(images)
        assert len(clusters) == 1
        assert len(clusters[0]) == 3

    def test_single_image(self):
        """One image should still produce one cluster."""
        images = [
            {"path": "solo.jpg", "lat": 41.862644, "lon": -87.661244, "time": None},
        ]
        clusters = cluster_images_dbscan(images)
        assert len(clusters) == 1

    def test_empty_input(self):
        clusters = cluster_images_dbscan([])
        assert clusters == []

    def test_no_gps_images_excluded(self):
        """Images without GPS should be excluded from clusters."""
        images = [
            {"path": "a.jpg", "lat": 41.862644, "lon": -87.661244, "time": None},
            {"path": "nogps.jpg", "lat": None, "lon": None, "time": None},
        ]
        clusters = cluster_images_dbscan(images)
        total_images = sum(len(c) for c in clusters)
        assert total_images == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_clustering.py -v
```

Expected: FAIL — `ImportError: cannot import name 'cluster_images_dbscan'`

- [ ] **Step 3: Add scikit-learn to requirements.txt**

Add this line to the end of `requirements.txt`:

```
scikit-learn>=1.3.0
```

- [ ] **Step 4: Install the new dependency**

```bash
pip install scikit-learn>=1.3.0
```

- [ ] **Step 5: Implement cluster_images_dbscan in processor.py**

Add the following function after the existing `cluster_images` function (after line 178 in `processor.py`):

```python
def cluster_images_dbscan(images_meta, eps_meters=90.0, min_samples=1):
    """Cluster images by GPS proximity using DBSCAN.

    Args:
        images_meta: list of dicts with 'path', 'lat', 'lon', 'time' keys.
        eps_meters: maximum distance in meters between points in the same cluster.
        min_samples: minimum images to form a cluster (default 1 = no noise).

    Returns:
        list of lists, each inner list is a cluster of image meta dicts.
    """
    if not images_meta:
        return []

    # Filter out images without GPS
    gps_images = [m for m in images_meta if m.get("lat") is not None and m.get("lon") is not None]
    if not gps_images:
        return []

    import numpy as np
    from sklearn.cluster import DBSCAN

    # Convert lat/lon to radians for haversine
    coords_rad = np.array([[np.radians(m["lat"]), np.radians(m["lon"])] for m in gps_images])

    # eps in radians: meters / earth_radius_meters
    eps_rad = eps_meters / 6371000.0

    db = DBSCAN(eps=eps_rad, min_samples=min_samples, metric="haversine")
    labels = db.fit_predict(coords_rad)

    clusters_dict = {}
    for img, label in zip(gps_images, labels):
        if label == -1:
            # Noise point — treat as its own cluster
            noise_key = f"noise_{id(img)}"
            clusters_dict[noise_key] = [img]
        else:
            clusters_dict.setdefault(label, []).append(img)

    return list(clusters_dict.values())
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_clustering.py -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add processor.py requirements.txt tests/test_clustering.py
git commit -m "feat: add DBSCAN clustering option to processor"
```

---

## Task 4: GIS Enrichment

**Files:**
- Modify: `analyzer.py` (add `enrich_gis` function)
- Create: `tests/test_gis_enrichment.py`

- [ ] **Step 1: Write failing tests for GIS enrichment**

```python
# tests/test_gis_enrichment.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from site_model import CandidateSite, SiteIdentity
from analyzer import enrich_gis


def _make_site(lat=41.862644, lon=-87.661244):
    return CandidateSite(
        identity=SiteIdentity(
            site_name="Test Site",
            site_id="TEST_001",
            agency_name="Test PD",
            site_address="123 Main St",
            site_latitude=lat,
            site_longitude=lon,
        )
    )


class TestEnrichGISNominatim:
    @patch("analyzer.requests.get")
    def test_extracts_county_state_zip(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "address": {
                "county": "Cook County",
                "state": "Illinois",
                "postcode": "60608",
                "city": "Chicago",
            }
        }
        mock_get.return_value = mock_resp

        site = _make_site()
        enrich_gis(site)

        assert site.identity.county == "Cook County"
        assert site.identity.state == "Illinois"
        assert site.identity.zip_code == "60608"
        assert site.checklist_provenance["COUNTY_NAME"] == "auto"

    @patch("analyzer.requests.get")
    def test_graceful_failure_on_api_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        site = _make_site()
        # Should not raise
        enrich_gis(site)
        assert site.identity.site_elevation is None


class TestEnrichGISElevation:
    @patch("analyzer.requests.get")
    def test_sets_elevation(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": [{"elevation": 181.5}]
        }
        mock_get.return_value = mock_resp

        site = _make_site()
        enrich_gis(site, skip_nominatim=True)

        assert site.identity.site_elevation == 181.5
        assert site.checklist_provenance.get("SITE_ELEVATION") == "auto"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_gis_enrichment.py -v
```

Expected: FAIL — `ImportError: cannot import name 'enrich_gis'`

- [ ] **Step 3: Implement enrich_gis in analyzer.py**

Add the following at the end of `analyzer.py`:

```python
def enrich_gis(site, skip_nominatim=False):
    """Enrich a CandidateSite with free GIS data.

    Populates: county, state, zip (from Nominatim), elevation (from Open-Elevation),
    airport/heliport distances (from Overpass).

    Gracefully degrades — any API failure leaves the field as None for PM to fill.
    """
    import requests as _requests

    lat = site.identity.site_latitude
    lon = site.identity.site_longitude
    if lat is None or lon is None:
        return

    # ── Nominatim reverse geocode (county, state, zip) ──
    if not skip_nominatim:
        try:
            resp = _requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
                headers={"User-Agent": "BRINC-DFR-SiteSurvey/1.0"},
                timeout=10,
            )
            if resp.status_code == 200:
                addr = resp.json().get("address", {})
                county = addr.get("county", "")
                state = addr.get("state", "")
                postcode = addr.get("postcode", "")
                city = addr.get("city") or addr.get("town") or addr.get("village", "")

                # Build full address if we don't have one
                if site.identity.site_address in ("", "Unknown", None):
                    parts = [p for p in [city, county, state, postcode] if p]
                    site.identity.site_address = ", ".join(parts)

                site.identity.county = county
                site.identity.state = state
                site.identity.zip_code = postcode
                site.identity.jurisdiction = city or county
                site.checklist_provenance["COUNTY_NAME"] = "auto"
                site.checklist_provenance["STATE_NAME"] = "auto"
                site.checklist_provenance["ZIP_CODE"] = "auto"
                site.checklist_provenance["JURISDICTION"] = "auto"
        except Exception:
            pass

    # ── Open-Elevation API ──
    try:
        resp = _requests.get(
            "https://api.open-elevation.com/api/v1/lookup",
            params={"locations": f"{lat},{lon}"},
            timeout=10,
        )
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                site.identity.site_elevation = results[0].get("elevation")
                site.checklist_provenance["SITE_ELEVATION"] = "auto"
    except Exception:
        pass

    # ── Overpass: airport and heliport distances ──
    try:
        overpass_query = f"""
        [out:json][timeout:10];
        (
          node["aeroway"="aerodrome"](around:16000,{lat},{lon});
          way["aeroway"="aerodrome"](around:16000,{lat},{lon});
          node["aeroway"="helipad"](around:16000,{lat},{lon});
          way["aeroway"="helipad"](around:16000,{lat},{lon});
        );
        out center;
        """
        resp = _requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": overpass_query},
            timeout=15,
        )
        if resp.status_code == 200:
            from geopy.distance import geodesic
            elements = resp.json().get("elements", [])
            min_airport_dist = None
            min_heliport_dist = None
            nearest_airport_name = None
            nearest_heliport_name = None

            for el in elements:
                el_lat = el.get("lat") or el.get("center", {}).get("lat")
                el_lon = el.get("lon") or el.get("center", {}).get("lon")
                if el_lat is None or el_lon is None:
                    continue

                dist_mi = geodesic((lat, lon), (el_lat, el_lon)).miles
                tags = el.get("tags", {})
                name = tags.get("name", "Unknown")
                aeroway = tags.get("aeroway", "")

                if aeroway == "helipad":
                    if min_heliport_dist is None or dist_mi < min_heliport_dist:
                        min_heliport_dist = round(dist_mi, 2)
                        nearest_heliport_name = name
                else:
                    if min_airport_dist is None or dist_mi < min_airport_dist:
                        min_airport_dist = round(dist_mi, 2)
                        nearest_airport_name = name

            if nearest_airport_name:
                site.flight.nearby_airports = f"{nearest_airport_name} ({min_airport_dist} mi)"
                site.checklist_provenance["NEARBY_AIRPORTS"] = "auto"
            if nearest_heliport_name:
                site.flight.nearby_heliports = f"{nearest_heliport_name} ({min_heliport_dist} mi)"
                site.checklist_provenance["NEARBY_HELIPORTS"] = "auto"
    except Exception:
        pass

    # ── Gemini Flash: building height from photo ──
    if site.structure.building_height is None:
        # Find the first "Site" category photo (building overview)
        overview_photos = [p for p in site.photos if p.category == "Site" and
                          any(kw in p.photo_id.lower() for kw in ["overview", "front", "building"])]
        if not overview_photos and site.photos:
            overview_photos = [site.photos[0]]  # fallback to first photo
        if overview_photos:
            import os as _os
            photo_path = overview_photos[0].file_path
            if _os.path.exists(photo_path):
                result = estimate_building_height_gemini(photo_path)
                if result and result.get("estimated_height_ft"):
                    site.structure.building_height = float(result["estimated_height_ft"])
                    site.checklist_provenance["BUILDING_HEIGHT"] = "auto"

    # ── Overpass: building height from OSM (fallback) ──
    try:
        bldg_query = f"""
        [out:json][timeout:10];
        way["building"](around:30,{lat},{lon});
        out tags;
        """
        resp = _requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": bldg_query},
            timeout=10,
        )
        if resp.status_code == 200:
            elements = resp.json().get("elements", [])
            for el in elements:
                tags = el.get("tags", {})
                height_str = tags.get("height") or tags.get("building:height")
                levels_str = tags.get("building:levels")
                if height_str and site.structure.building_height is None:
                    try:
                        site.structure.building_height = float(height_str.replace("m", "").strip()) * 3.281
                        site.checklist_provenance["BUILDING_HEIGHT"] = "auto"
                    except ValueError:
                        pass
                elif levels_str and site.structure.building_height is None:
                    try:
                        site.structure.building_height = float(levels_str) * 13.0
                        site.checklist_provenance["BUILDING_HEIGHT"] = "auto"
                    except ValueError:
                        pass
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_gis_enrichment.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add analyzer.py tests/test_gis_enrichment.py
git commit -m "feat: add GIS enrichment with Nominatim, Open-Elevation, Overpass"
```

---

## Task 5: Gemini Flash Building Height Estimation

**Files:**
- Modify: `analyzer.py` (add `estimate_building_height_gemini` function)
- Modify: `requirements.txt` (add `google-generativeai`)
- Modify: `tests/test_gis_enrichment.py` (add tests)

- [ ] **Step 1: Write failing test for Gemini height estimation**

```python
# Append to tests/test_gis_enrichment.py
from analyzer import estimate_building_height_gemini


class TestGeminiBuildingHeight:
    @patch("analyzer.genai")
    def test_returns_height_from_gemini(self, mock_genai):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"floors": 3, "estimated_height_ft": 39}'
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        result = estimate_building_height_gemini("/path/to/building.jpg")
        assert result == {"floors": 3, "estimated_height_ft": 39}

    @patch("analyzer.genai")
    def test_returns_none_on_failure(self, mock_genai):
        mock_genai.GenerativeModel.side_effect = Exception("API error")
        result = estimate_building_height_gemini("/path/to/building.jpg")
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_gis_enrichment.py::TestGeminiBuildingHeight -v
```

Expected: FAIL — `ImportError: cannot import name 'estimate_building_height_gemini'`

- [ ] **Step 3: Add google-generativeai to requirements.txt**

Add this line to `requirements.txt`:

```
google-generativeai>=0.5.0
```

- [ ] **Step 4: Install the new dependency**

```bash
pip install google-generativeai>=0.5.0
```

- [ ] **Step 5: Implement estimate_building_height_gemini in analyzer.py**

Add at the top of `analyzer.py` (after existing imports):

```python
try:
    import google.generativeai as genai
except ImportError:
    genai = None
```

Add the function after `enrich_gis`:

```python
def estimate_building_height_gemini(image_path, api_key=None):
    """Use Gemini Flash free tier to estimate building height from a photo.

    Args:
        image_path: path to a building overview photo.
        api_key: Gemini API key. If None, tries GOOGLE_GEMINI_API_KEY env var
                 or Streamlit secrets.

    Returns:
        dict with 'floors' and 'estimated_height_ft', or None on failure.
    """
    if genai is None:
        return None

    if api_key is None:
        api_key = os.environ.get("GOOGLE_GEMINI_API_KEY", "")
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GOOGLE_GEMINI_API_KEY", "")
            except Exception:
                pass
    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")

        import PIL.Image
        img = PIL.Image.open(image_path)

        response = model.generate_content(
            [
                img,
                "How many floors does this building have? Estimate the building "
                "height in feet. Return ONLY valid JSON: "
                '{"floors": <int>, "estimated_height_ft": <int>}',
            ]
        )

        import json
        text = response.text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception:
        return None
```

Add `import os` to the top of `analyzer.py` if not already there.

- [ ] **Step 6: Run tests to verify they pass**

```bash
python -m pytest tests/test_gis_enrichment.py -v
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add analyzer.py requirements.txt tests/test_gis_enrichment.py
git commit -m "feat: add Gemini Flash building height estimation"
```

---

## Task 6: Processor Pipeline Integration

**Files:**
- Modify: `processor.py` (update `process_and_organize_images` to return `list[CandidateSite]`)

This task wires the new data model into the existing processing pipeline. The function currently returns `list[dict]` — it will now also return `list[CandidateSite]` while keeping backward compatibility.

- [ ] **Step 1: Write failing test for CandidateSite output**

```python
# Append to tests/test_clustering.py
from site_model import CandidateSite


class TestProcessorCandidateSiteOutput:
    def test_cluster_to_candidate_sites(self):
        """cluster_to_candidate_sites converts cluster output to CandidateSite list."""
        from processor import cluster_to_candidate_sites

        clusters = [
            [
                {"path": "/img/a1.jpg", "filename": "building_front.jpg",
                 "lat": 41.862644, "lon": -87.661244, "time": "2026-06-21 14:30:00",
                 "dest_path": "/out/a1.jpg"},
                {"path": "/img/a2.jpg", "filename": "roof_overview.jpg",
                 "lat": 41.862650, "lon": -87.661250, "time": "2026-06-21 14:31:00",
                 "dest_path": "/out/a2.jpg"},
            ],
            [
                {"path": "/img/b1.jpg", "filename": "antenna_north.jpg",
                 "lat": 41.867000, "lon": -87.665000, "time": "2026-06-21 15:00:00",
                 "dest_path": "/out/b1.jpg"},
            ],
        ]

        sites = cluster_to_candidate_sites(clusters, agency_name="Chicago PD")
        assert len(sites) == 2
        assert isinstance(sites[0], CandidateSite)
        assert sites[0].identity.agency_name == "Chicago PD"
        assert len(sites[0].photos) == 2
        assert sites[0].photos[0].category == "Site"  # "building_front" -> Site
        assert sites[1].photos[0].category == "RF"    # "antenna_north" -> RF
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_clustering.py::TestProcessorCandidateSiteOutput -v
```

Expected: FAIL — `ImportError: cannot import name 'cluster_to_candidate_sites'`

- [ ] **Step 3: Implement cluster_to_candidate_sites in processor.py**

Add at the top of `processor.py`:

```python
from site_model import CandidateSite, SiteIdentity, SurveyPhoto, categorize_photo_by_filename
```

Add the function after `cluster_images_dbscan`:

```python
def cluster_to_candidate_sites(clusters, agency_name="", survey_date=None):
    """Convert cluster output into a list of CandidateSite objects.

    Args:
        clusters: list of lists of image meta dicts (from cluster_images or cluster_images_dbscan).
        agency_name: agency name to set on all sites.
        survey_date: survey date string (YYYY-MM-DD). Defaults to today.

    Returns:
        list[CandidateSite]
    """
    from datetime import datetime
    if survey_date is None:
        survey_date = datetime.now().strftime("%Y-%m-%d")

    sites = []
    for idx, cluster in enumerate(clusters, start=1):
        if not cluster:
            continue

        # Calculate cluster center
        lats = [m["lat"] for m in cluster if m.get("lat") is not None]
        lons = [m["lon"] for m in cluster if m.get("lon") is not None]
        center_lat = sum(lats) / len(lats) if lats else 0.0
        center_lon = sum(lons) / len(lons) if lons else 0.0

        # Reverse geocode for site name
        addr = ""
        city = ""
        try:
            result = reverse_geocode(center_lat, center_lon)
            if result:
                addr = result
                city = extract_city_from_address(result)
        except Exception:
            pass

        site_name = city if city else f"Site {idx}"
        safe_agency = agency_name.replace(" ", "_") if agency_name else "Survey"
        site_id = f"{safe_agency}_{survey_date.replace('-', '')}_{idx}"

        identity = SiteIdentity(
            site_name=site_name,
            site_id=site_id,
            agency_name=agency_name,
            site_address=addr,
            site_latitude=center_lat,
            site_longitude=center_lon,
            survey_date=survey_date,
        )

        photos = []
        for img in cluster:
            filename = img.get("filename", os.path.basename(img.get("path", "")))
            file_path = img.get("dest_path", img.get("path", ""))
            time_str = str(img.get("time", "")) if img.get("time") else ""
            photo = SurveyPhoto(
                photo_id=filename,
                file_path=file_path,
                category=categorize_photo_by_filename(filename),
                gps_latitude=img.get("lat"),
                gps_longitude=img.get("lon"),
                photo_date=time_str.split(" ")[0] if time_str else None,
                photo_time=time_str.split(" ")[1] if " " in time_str else None,
            )
            photos.append(photo)

        sites.append(CandidateSite(identity=identity, photos=photos))

    return sites
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_clustering.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add processor.py tests/test_clustering.py
git commit -m "feat: add cluster_to_candidate_sites conversion function"
```

---

## Task 7: Dynamic Report Generation

**Files:**
- Modify: `reporter.py` (add `generate_candidate_site_report` function)
- Create: `tests/test_report_dynamic.py`

The existing `generate_word_report` is preserved. A new function generates the enhanced report from `CandidateSite` objects.

- [ ] **Step 1: Write failing tests for dynamic report**

```python
# tests/test_report_dynamic.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
from site_model import (
    CandidateSite, SiteIdentity, SurveyPhoto, ElectricalInfo,
    NetworkInfo, RFInfo, FlightOps, StructuralInfo, AccessInfo,
)
from reporter import generate_candidate_site_report


def _make_candidate(site_id="TEST_001", name="Police HQ", n_photos=3):
    photos = []
    categories = ["Site", "Infrastructure", "RF"]
    for i in range(n_photos):
        photos.append(SurveyPhoto(
            photo_id=f"IMG_{i:03d}",
            file_path=f"/fake/path/img_{i}.jpg",
            category=categories[i % len(categories)],
        ))
    return CandidateSite(
        identity=SiteIdentity(
            site_name=name,
            site_id=site_id,
            agency_name="Chicago PD",
            site_address="1412 S Blue Island Ave, Chicago, IL",
            site_latitude=41.862644,
            site_longitude=-87.661244,
            site_elevation=180.0,
            survey_date="2026-06-21",
            surveyor="Steven Beltran",
        ),
        electrical=ElectricalInfo(power_available=True, voltage_available="120V"),
        network=NetworkInfo(isp_provider="Comcast", download_speed="200 Mbps"),
        flight=FlightOps(airspace_class="G", nearby_airports="Midway (5.2 mi)"),
        structure=StructuralInfo(building_height=39.0, roof_type="Flat Concrete"),
        access=AccessInfo(roof_access="Roof Hatch", escort_required=False),
        photos=photos,
    )


class TestDynamicReport:
    def test_single_site_report(self):
        sites = [_make_candidate()]
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            output_path = f.name
        try:
            result = generate_candidate_site_report(sites, output_path)
            assert os.path.exists(result)
            assert os.path.getsize(result) > 0
        finally:
            os.unlink(output_path)

    def test_multi_site_report(self):
        sites = [
            _make_candidate("TEST_001", "Police HQ"),
            _make_candidate("TEST_002", "Public Works"),
            _make_candidate("TEST_003", "Training Center"),
        ]
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            output_path = f.name
        try:
            result = generate_candidate_site_report(sites, output_path)
            assert os.path.exists(result)

            from docx import Document
            doc = Document(result)
            text = "\n".join([p.text for p in doc.paragraphs])
            assert "Police HQ" in text
            assert "Public Works" in text
            assert "Training Center" in text
            assert "Installer Quick Reference" in text
        finally:
            os.unlink(output_path)

    def test_empty_sites_still_generates(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            output_path = f.name
        try:
            result = generate_candidate_site_report([], output_path)
            assert os.path.exists(result)
        finally:
            os.unlink(output_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_report_dynamic.py -v
```

Expected: FAIL — `ImportError: cannot import name 'generate_candidate_site_report'`

- [ ] **Step 3: Implement generate_candidate_site_report in reporter.py**

Add at the end of `reporter.py`:

```python
def generate_candidate_site_report(candidate_sites, output_filepath,
                                    customer_info=None, drive_manager=None,
                                    drive_reports_folder_id=None):
    """Generate a dynamic DOCX report from CandidateSite objects.

    Report structure:
    1. Executive Summary
    2. Candidate Site sections (1-N, dynamic)
    3. Installer Quick Reference (1 page per site)
    4. Annotated Photo Appendix

    Args:
        candidate_sites: list of CandidateSite objects.
        output_filepath: path for the output .docx file.
        customer_info: optional dict with agency/POC details.
        drive_manager: optional GoogleDriveManager for upload.
        drive_reports_folder_id: optional Drive folder ID.

    Returns:
        output_filepath string.
    """
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    import os

    doc = Document()

    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(10)

    # ── 1. Executive Summary ──
    title = doc.add_heading("DFR SITE SURVEY REPORT", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    agency = ""
    survey_date = ""
    surveyor = ""
    if candidate_sites:
        agency = candidate_sites[0].identity.agency_name
        survey_date = candidate_sites[0].identity.survey_date or ""
        surveyor = candidate_sites[0].identity.surveyor or ""
    if customer_info:
        agency = customer_info.get("agency_name", agency)

    doc.add_paragraph(f"Agency: {agency}")
    doc.add_paragraph(f"Survey Date: {survey_date}")
    doc.add_paragraph(f"Surveyor: {surveyor}")
    doc.add_paragraph(f"Candidate Sites Found: {len(candidate_sites)}")
    doc.add_page_break()

    # ── 2. Candidate Site Sections ──
    for idx, site in enumerate(candidate_sites, start=1):
        doc.add_heading(f"Candidate Site {idx}: {site.identity.site_name}", level=1)

        # 2a. Site Overview
        doc.add_heading("Site Overview", level=2)
        overview_data = [
            ["Field", "Value"],
            ["Site ID", site.identity.site_id],
            ["Address", site.identity.site_address],
            ["Latitude", str(site.identity.site_latitude)],
            ["Longitude", str(site.identity.site_longitude)],
            ["Elevation", f"{site.identity.site_elevation} ft" if site.identity.site_elevation else "—"],
            ["Building Height", f"{site.structure.building_height} ft" if site.structure.building_height else "—"],
            ["Roof Type", site.structure.roof_type or "—"],
        ]
        add_styled_table(doc, overview_data[1:], overview_data[0])

        # 2b. Site Photos by Category
        doc.add_heading("Site Photos", level=2)
        categories_order = ["Site", "Installation", "Infrastructure", "RF", "Access"]
        for cat in categories_order:
            cat_photos = [p for p in site.photos if p.category == cat and p.selected_for_report]
            if not cat_photos:
                continue
            doc.add_heading(f"{cat} Photos", level=3)
            for photo in cat_photos:
                if os.path.exists(photo.file_path):
                    try:
                        doc.add_picture(photo.file_path, width=Inches(5.0))
                    except Exception:
                        doc.add_paragraph(f"[Photo: {photo.photo_id}]")
                else:
                    doc.add_paragraph(f"[Photo: {photo.photo_id}]")

        # 2c. Checklist Summary
        doc.add_heading("Assessment Summary", level=2)

        # Access
        doc.add_heading("Access", level=3)
        access_data = [
            ["Access Type", site.access.access_type or "—"],
            ["Roof Access", site.access.roof_access or "—"],
            ["Escort Required", _yn(site.access.escort_required)],
            ["Key Required", _yn(site.access.key_required)],
            ["After Hours Access", _yn(site.access.after_hours_access)],
            ["Parking Available", _yn(site.access.parking_available)],
        ]
        add_styled_table(doc, access_data, ["Field", "Value"])

        # 2d. Electrical
        doc.add_heading("Electrical Assessment", level=3)
        elec_data = [
            ["Power Available", _yn(site.electrical.power_available)],
            ["Voltage", site.electrical.voltage_available or "—"],
            ["Breaker Available", _yn(site.electrical.breaker_available)],
            ["Dedicated Circuit", _yn(site.electrical.dedicated_circuit)],
            ["Panel Location", site.electrical.panel_location or "—"],
            ["Distance to Power", f"{site.electrical.distance_to_power} ft" if site.electrical.distance_to_power else "—"],
        ]
        add_styled_table(doc, elec_data, ["Field", "Value"])

        # 2e. Network
        doc.add_heading("Network Assessment", level=3)
        net_data = [
            ["ISP Provider", site.network.isp_provider or "—"],
            ["Connection Type", site.network.connection_type or "—"],
            ["Download Speed", site.network.download_speed or "—"],
            ["Upload Speed", site.network.upload_speed or "—"],
            ["Static IP", _yn(site.network.static_ip_available)],
            ["Switch Location", site.network.switch_location or "—"],
            ["Distance to Network", f"{site.network.distance_to_network} ft" if site.network.distance_to_network else "—"],
        ]
        add_styled_table(doc, net_data, ["Field", "Value"])

        # 2f. RF
        doc.add_heading("RF Assessment", level=3)
        rf_data = [
            ["Line of Sight", site.rf.line_of_sight_status or "—"],
            ["Obstructions - Trees", _yn(site.rf.obstruction_trees)],
            ["Obstructions - Buildings", _yn(site.rf.obstruction_buildings)],
            ["Obstructions - Water Towers", _yn(site.rf.obstruction_water_towers)],
            ["Obstructions - Cell Towers", _yn(site.rf.obstruction_cell_towers)],
            ["Coverage Direction", site.rf.coverage_direction or "—"],
        ]
        add_styled_table(doc, rf_data, ["Field", "Value"])

        # 2g. Airspace
        doc.add_heading("Airspace Assessment", level=3)
        air_data = [
            ["Airspace Class", site.flight.airspace_class or "—"],
            ["Nearby Airports", site.flight.nearby_airports or "—"],
            ["Nearby Heliports", site.flight.nearby_heliports or "—"],
            ["Flight Restrictions", site.flight.flight_restrictions or "—"],
        ]
        add_styled_table(doc, air_data, ["Field", "Value"])

        doc.add_page_break()

    # ── 3. Installer Quick Reference ──
    doc.add_heading("Installer Quick Reference", level=1)
    for idx, site in enumerate(candidate_sites, start=1):
        doc.add_heading(f"Site {idx}: {site.identity.site_name}", level=2)
        ref_data = [
            ["Address", site.identity.site_address],
            ["Access Method", site.access.roof_access or site.access.access_type or "—"],
            ["Power Location", site.electrical.panel_location or "—"],
            ["Network Location", site.network.switch_location or "—"],
            ["Antenna Location", f"{site.rf.antenna_latitude}, {site.rf.antenna_longitude}" if site.rf.antenna_latitude else "—"],
            ["Escort Required", _yn(site.access.escort_required)],
        ]
        add_styled_table(doc, ref_data, ["Item", "Details"])

        # Add contact info if available
        if customer_info:
            poc = customer_info.get("poc_name", "")
            phone = customer_info.get("poc_phone", "")
            if poc:
                doc.add_paragraph(f"Site Contact: {poc}  {phone}")

        doc.add_page_break()

    # ── 4. Annotated Photo Appendix ──
    doc.add_heading("Annotated Photo Appendix", level=1)
    has_annotations = False
    for idx, site in enumerate(candidate_sites, start=1):
        # Look for engineering layout PNGs in the site folder
        folder = getattr(site.identity, '_folder_path', None)
        if folder and os.path.isdir(folder):
            for fname in sorted(os.listdir(folder)):
                if fname.startswith("engineering_layout") and fname.endswith(".png"):
                    img_path = os.path.join(folder, fname)
                    doc.add_heading(f"Site {idx}: {site.identity.site_name}", level=3)
                    try:
                        doc.add_picture(img_path, width=Inches(6.0))
                        has_annotations = True
                    except Exception:
                        doc.add_paragraph(f"[Annotation: {fname}]")
                    doc.add_paragraph("")

    if not has_annotations:
        doc.add_paragraph("No annotated engineering layouts available.")

    # ── Save ──
    doc.save(output_filepath)

    # Upload to Drive if configured
    if drive_manager and drive_reports_folder_id:
        try:
            drive_manager.upload_file(output_filepath, drive_reports_folder_id)
        except Exception:
            pass

    return output_filepath


def _yn(value):
    """Convert bool/None to Yes/No/— string."""
    if value is True:
        return "Yes"
    elif value is False:
        return "No"
    return "—"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_report_dynamic.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add reporter.py tests/test_report_dynamic.py
git commit -m "feat: add dynamic candidate site report generation"
```

---

## Task 8: JSON and CSV Export

**Files:**
- Modify: `site_model.py` (add `export_sites_json` and `export_sites_csv` functions)
- Modify: `tests/test_site_model.py` (add export tests)

- [ ] **Step 1: Write failing tests for export functions**

```python
# Append to tests/test_site_model.py
import tempfile


class TestExportJSON:
    def test_export_single_site(self):
        from site_model import export_sites_json
        site = TestCandidateSite()._make_site()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            output = f.name
        try:
            export_sites_json([site], output)
            with open(output, "r") as f:
                data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["identity"]["SITE_NAME"] == "Police HQ"
        finally:
            os.unlink(output)

    def test_export_multiple_sites(self):
        from site_model import export_sites_json
        s1 = TestCandidateSite()._make_site("ID1", "Site A")
        s2 = TestCandidateSite()._make_site("ID2", "Site B")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            output = f.name
        try:
            export_sites_json([s1, s2], output)
            with open(output, "r") as f:
                data = json.load(f)
            assert len(data) == 2
        finally:
            os.unlink(output)


class TestExportCSV:
    def test_export_csv_headers(self):
        from site_model import export_sites_csv
        site = TestCandidateSite()._make_site()
        site.electrical.power_available = True
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as f:
            output = f.name
        try:
            export_sites_csv([site], output)
            with open(output, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["SITE_NAME"] == "Police HQ"
            assert rows[0]["POWER_AVAILABLE"] == "True"
        finally:
            os.unlink(output)

    def test_export_csv_multi_row(self):
        from site_model import export_sites_csv
        s1 = TestCandidateSite()._make_site("ID1", "Site A")
        s2 = TestCandidateSite()._make_site("ID2", "Site B")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", newline="") as f:
            output = f.name
        try:
            export_sites_csv([s1, s2], output)
            with open(output, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["SITE_ID"] == "ID1"
            assert rows[1]["SITE_ID"] == "ID2"
        finally:
            os.unlink(output)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_site_model.py::TestExportJSON -v
python -m pytest tests/test_site_model.py::TestExportCSV -v
```

Expected: FAIL — `ImportError: cannot import name 'export_sites_json'`

- [ ] **Step 3: Implement export functions in site_model.py**

Add at the end of `site_model.py`:

```python
# ── Export functions ────────────────────────────────────────────────

def export_sites_json(sites: list, output_path: str) -> str:
    """Export a list of CandidateSite objects to a JSON file.

    Args:
        sites: list of CandidateSite objects.
        output_path: path for the output JSON file.

    Returns:
        output_path string.
    """
    import json
    data = [site.to_json() for site in sites]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    return output_path


def export_sites_csv(sites: list, output_path: str) -> str:
    """Export a list of CandidateSite objects to a CSV file.

    One row per site. Columns are the stable field IDs.

    Args:
        sites: list of CandidateSite objects.
        output_path: path for the output CSV file.

    Returns:
        output_path string.
    """
    import csv
    if not sites:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            f.write("")
        return output_path

    rows = [site.to_csv_row() for site in sites]
    # Use first row keys as fieldnames to ensure consistent column order
    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Convert non-string values to strings for CSV
            writer.writerow({k: str(v) if v is not None else "" for k, v in row.items()})

    return output_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_site_model.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add site_model.py tests/test_site_model.py
git commit -m "feat: add JSON and CSV export for candidate sites"
```

---

## Task 9: Dashboard — Unified Checklist UI

**Files:**
- Modify: `dashboard.py` (add checklist card UI per candidate site)

This task adds the unified checklist to the Survey Pipeline tab. After photo processing, each candidate site gets an expandable checklist card where the PM can view auto-filled fields and fill in the rest.

- [ ] **Step 1: Add CandidateSite import and session state key**

At the top of `dashboard.py`, add to the imports section:

```python
from site_model import CandidateSite, export_sites_json, export_sites_csv
```

In the session state initialization block (around lines 96-131), add:

```python
if "candidate_sites" not in st.session_state:
    st.session_state.candidate_sites = []  # list[CandidateSite]
```

- [ ] **Step 2: Add checklist rendering function**

Add this function before the main tab layout (before line 461):

```python
def _render_site_checklist(site, site_idx):
    """Render a unified checklist card for a CandidateSite."""
    prov = site.checklist_provenance

    def _indicator(field_id):
        """Green dot if auto-filled, yellow if empty."""
        if prov.get(field_id) == "auto":
            return "\u2705"  # green check
        return "\u26A0\uFE0F"  # warning

    with st.expander(f"Site {site_idx}: {site.identity.site_name} — {site.identity.site_address}", expanded=False):
        st.markdown(f"**Site ID:** {site.identity.site_id}")
        st.markdown(f"**Coordinates:** {site.identity.site_latitude:.6f}, {site.identity.site_longitude:.6f}")
        if site.identity.site_elevation:
            st.markdown(f"**Elevation:** {site.identity.site_elevation:.1f} ft {_indicator('SITE_ELEVATION')}")

        st.markdown("---")

        # ── Access ──
        st.markdown("#### Access")
        col1, col2 = st.columns(2)
        with col1:
            site.access.access_type = st.selectbox(
                "Access Type", ["", "Stairs", "Ladder", "Elevator", "Roof Hatch"],
                index=0, key=f"access_type_{site_idx}",
            )
            site.access.escort_required = st.checkbox(
                "Escort Required", value=site.access.escort_required or False,
                key=f"escort_{site_idx}",
            )
            site.access.key_required = st.checkbox(
                "Key Required", value=site.access.key_required or False,
                key=f"key_{site_idx}",
            )
        with col2:
            site.access.roof_access = st.selectbox(
                "Roof Access", ["", "Roof Hatch", "Exterior Ladder", "Interior Stairs", "Elevator"],
                index=0, key=f"roof_access_{site_idx}",
            )
            site.access.after_hours_access = st.checkbox(
                "After Hours Access", value=site.access.after_hours_access or False,
                key=f"after_hours_{site_idx}",
            )
            site.access.parking_available = st.checkbox(
                "Parking Available", value=site.access.parking_available or False,
                key=f"parking_{site_idx}",
            )

        st.markdown("---")

        # ── Structural ──
        st.markdown("#### Structural")
        col1, col2 = st.columns(2)
        with col1:
            height_default = site.structure.building_height or 0.0
            site.structure.building_height = st.number_input(
                f"Building Height (ft) {_indicator('BUILDING_HEIGHT')}",
                value=height_default, min_value=0.0, step=1.0,
                key=f"bldg_height_{site_idx}",
            )
            site.structure.roof_type = st.selectbox(
                "Roof Type",
                ["", "Flat Concrete", "EPDM / Rubber Membrane", "TPO / Single-ply Vinyl",
                 "Standing Seam Metal", "Tar and Gravel", "Pitched / Shingle"],
                index=0, key=f"roof_type_{site_idx}",
            )
        with col2:
            parapet_default = site.structure.parapet_height or 0.0
            site.structure.parapet_height = st.number_input(
                "Parapet Height (ft)", value=parapet_default, min_value=0.0, step=0.5,
                key=f"parapet_{site_idx}",
            )
            site.structure.roof_condition = st.selectbox(
                "Roof Condition", ["", "Good", "Fair", "Poor"],
                index=0, key=f"roof_cond_{site_idx}",
            )

        st.markdown("---")

        # ── Electrical ──
        st.markdown("#### Electrical")
        col1, col2 = st.columns(2)
        with col1:
            site.electrical.power_available = st.checkbox(
                "Power Available", value=site.electrical.power_available or False,
                key=f"power_{site_idx}",
            )
            site.electrical.voltage_available = st.selectbox(
                "Voltage", ["", "120V", "208V", "240V", "480V"],
                index=0, key=f"voltage_{site_idx}",
            )
            site.electrical.dedicated_circuit = st.checkbox(
                "Dedicated Circuit", value=site.electrical.dedicated_circuit or False,
                key=f"ded_circuit_{site_idx}",
            )
        with col2:
            site.electrical.breaker_available = st.checkbox(
                "Breaker Available", value=site.electrical.breaker_available or False,
                key=f"breaker_{site_idx}",
            )
            site.electrical.panel_location = st.text_input(
                "Panel Location", value=site.electrical.panel_location or "",
                key=f"panel_loc_{site_idx}",
            )
            dist_power = site.electrical.distance_to_power or 0.0
            site.electrical.distance_to_power = st.number_input(
                "Distance to Power (ft)", value=dist_power, min_value=0.0, step=1.0,
                key=f"dist_power_{site_idx}",
            )

        st.markdown("---")

        # ── Network ──
        st.markdown("#### Network")
        col1, col2 = st.columns(2)
        with col1:
            site.network.isp_provider = st.text_input(
                "ISP Provider", value=site.network.isp_provider or "",
                key=f"isp_{site_idx}",
            )
            site.network.download_speed = st.text_input(
                "Download Speed", value=site.network.download_speed or "",
                key=f"dl_speed_{site_idx}",
            )
            site.network.static_ip_available = st.checkbox(
                "Static IP Available", value=site.network.static_ip_available or False,
                key=f"static_ip_{site_idx}",
            )
        with col2:
            site.network.connection_type = st.selectbox(
                "Connection Type", ["", "Fiber", "Cable", "DSL", "Cellular", "Satellite"],
                index=0, key=f"conn_type_{site_idx}",
            )
            site.network.upload_speed = st.text_input(
                "Upload Speed", value=site.network.upload_speed or "",
                key=f"ul_speed_{site_idx}",
            )
            site.network.switch_location = st.text_input(
                "Switch Location", value=site.network.switch_location or "",
                key=f"switch_loc_{site_idx}",
            )

        st.markdown("---")

        # ── RF ──
        st.markdown("#### RF")
        col1, col2 = st.columns(2)
        with col1:
            site.rf.line_of_sight_status = st.selectbox(
                "Line of Sight", ["", "Clear", "Partial", "Obstructed"],
                index=0, key=f"los_{site_idx}",
            )
            site.rf.obstruction_trees = st.checkbox("Trees", key=f"obs_trees_{site_idx}")
            site.rf.obstruction_buildings = st.checkbox("Buildings", key=f"obs_bldg_{site_idx}")
        with col2:
            site.rf.coverage_direction = st.text_input(
                "Coverage Direction", value=site.rf.coverage_direction or "",
                key=f"coverage_dir_{site_idx}",
            )
            site.rf.obstruction_water_towers = st.checkbox("Water Towers", key=f"obs_water_{site_idx}")
            site.rf.obstruction_cell_towers = st.checkbox("Cell Towers", key=f"obs_cell_{site_idx}")

        st.markdown("---")

        # ── Flight / Airspace ──
        st.markdown(f"#### Airspace {_indicator('AIRSPACE_CLASS')}")
        col1, col2 = st.columns(2)
        with col1:
            site.flight.airspace_class = st.text_input(
                "Airspace Class", value=site.flight.airspace_class or "",
                key=f"airspace_{site_idx}",
            )
            st.text(f"Nearby Airports: {site.flight.nearby_airports or '—'}")
            st.text(f"Nearby Heliports: {site.flight.nearby_heliports or '—'}")
        with col2:
            site.flight.launch_direction = st.text_input(
                "Launch Direction", value=site.flight.launch_direction or "",
                key=f"launch_dir_{site_idx}",
            )
            site.flight.emergency_landing_zone = st.text_input(
                "Emergency Landing Zone", value=site.flight.emergency_landing_zone or "",
                key=f"elz_{site_idx}",
            )

        # ── Photo Category Assignment ──
        uncategorized = [p for p in site.photos if p.category == "Site" and
                         "front" not in p.photo_id.lower() and
                         "rear" not in p.photo_id.lower() and
                         "overview" not in p.photo_id.lower() and
                         "panorama" not in p.photo_id.lower()]
        if uncategorized:
            st.markdown("---")
            st.markdown("#### Photo Categories")
            st.caption("Assign categories to uncategorized photos:")
            for photo in uncategorized:
                photo.category = st.selectbox(
                    f"{photo.photo_id}",
                    ["Site", "Installation", "Infrastructure", "RF", "Access"],
                    key=f"photo_cat_{site_idx}_{photo.photo_id}",
                )
```

- [ ] **Step 3: Wire checklist into the Survey Pipeline tab**

In `dashboard.py`, inside `tab1`, after the existing site processing results display and before the report generation button (around line 1040), add:

```python
# ── Candidate Site Checklists ──
if st.session_state.candidate_sites:
    st.markdown("---")
    st.markdown("### Site Assessment Checklists")
    for i, site in enumerate(st.session_state.candidate_sites, start=1):
        _render_site_checklist(site, i)
```

- [ ] **Step 4: Convert processed_sites to candidate_sites after processing**

In `dashboard.py`, after the auto-processing block completes (around line 430 where `st.session_state.processed_sites` is set), add:

```python
from processor import cluster_to_candidate_sites
from analyzer import enrich_gis

if st.session_state.processed_sites and not st.session_state.candidate_sites:
    agency = st.session_state.customer_info.get("agency_name", "")
    # Convert legacy site dicts to CandidateSite objects
    st.session_state.candidate_sites = [
        CandidateSite.from_site_dict(s) for s in st.session_state.processed_sites
    ]
    # Run GIS enrichment on each
    for site in st.session_state.candidate_sites:
        enrich_gis(site)
```

- [ ] **Step 5: Test manually in browser**

```bash
cd "G:/My Drive/PRIVATE NO ACCESS/Python/app/Monster/ant"
streamlit run dashboard.py
```

Verify:
1. Upload photos — sites process normally
2. Checklist cards appear below the map for each site
3. Auto-filled fields show green indicators
4. PM can fill empty fields
5. Photo category dropdowns appear for uncategorized photos

- [ ] **Step 6: Commit**

```bash
git add dashboard.py
git commit -m "feat: add unified checklist UI per candidate site"
```

---

## Task 10: Dashboard — Export Buttons and Report Integration

**Files:**
- Modify: `dashboard.py` (add export buttons, wire new report function)

- [ ] **Step 1: Add export buttons after report generation**

In `dashboard.py`, after the existing report generation block (around line 1105 where `st.session_state.generated_report` is set), add export buttons:

```python
# ── Export Buttons ──
if st.session_state.candidate_sites and st.session_state.get("generated_report"):
    st.markdown("---")
    st.markdown("### Export Data")
    exp_col1, exp_col2, exp_col3 = st.columns(3)

    with exp_col1:
        if st.button("Download JSON", key="dl_json"):
            import tempfile
            json_path = os.path.join(
                tempfile.gettempdir(), "survey_export.json"
            )
            export_sites_json(st.session_state.candidate_sites, json_path)
            with open(json_path, "r") as jf:
                st.download_button(
                    "Save JSON", jf.read(), "survey_export.json",
                    mime="application/json", key="json_save",
                )
            # Upload to Drive
            if st.session_state.get("metadata_folder_id") and 'report_drive' in dir():
                try:
                    report_drive.upload_file(json_path, st.session_state.metadata_folder_id)
                except Exception:
                    pass

    with exp_col2:
        if st.button("Download CSV", key="dl_csv"):
            import tempfile
            csv_path = os.path.join(
                tempfile.gettempdir(), "survey_export.csv"
            )
            export_sites_csv(st.session_state.candidate_sites, csv_path)
            with open(csv_path, "r") as cf:
                st.download_button(
                    "Save CSV", cf.read(), "survey_export.csv",
                    mime="text/csv", key="csv_save",
                )
            if st.session_state.get("metadata_folder_id") and 'report_drive' in dir():
                try:
                    report_drive.upload_file(csv_path, st.session_state.metadata_folder_id)
                except Exception:
                    pass

    with exp_col3:
        report_path = st.session_state.generated_report
        if os.path.exists(report_path):
            with open(report_path, "rb") as rf:
                st.download_button(
                    "Download DOCX", rf.read(),
                    os.path.basename(report_path),
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    key="docx_save",
                )
```

- [ ] **Step 2: Add option to use new report generator**

In the report generation button handler (around line 1045), add a toggle above the button:

```python
use_new_report = st.checkbox(
    "Use enhanced multi-site report format",
    value=True,
    key="use_new_report",
)
```

Then modify the report generation call to branch:

```python
if use_new_report and st.session_state.candidate_sites:
    from reporter import generate_candidate_site_report
    report_path = generate_candidate_site_report(
        st.session_state.candidate_sites,
        report_path,
        customer_info=customer_info,
        drive_manager=report_drive if report_drive else None,
        drive_reports_folder_id=st.session_state.get("reports_folder_id"),
    )
else:
    report_path = reporter.generate_word_report(
        st.session_state.processed_sites,
        report_path,
        customer_info=customer_info,
        drive_manager=report_drive if report_drive else None,
        drive_reports_folder_id=st.session_state.get("reports_folder_id"),
    )
```

- [ ] **Step 3: Test manually in browser**

```bash
streamlit run dashboard.py
```

Verify:
1. Upload photos, fill checklist
2. Toggle "Use enhanced multi-site report format" is checked
3. Click "Build Report & Upload to Drive"
4. Report generates with candidate site sections
5. Export buttons appear — JSON, CSV, DOCX downloads work
6. Toggle off enhanced format — old report still works

- [ ] **Step 4: Commit**

```bash
git add dashboard.py
git commit -m "feat: add export buttons and enhanced report toggle"
```

---

## Task 11: Dashboard — Clustering Method Selector

**Files:**
- Modify: `dashboard.py` (add clustering method dropdown)

- [ ] **Step 1: Add clustering method selector**

In `dashboard.py`, inside the upload expander (around line 326), add a selectbox before the file uploader:

```python
clustering_method = st.selectbox(
    "Clustering Method",
    ["Radius (90m)", "DBSCAN (auto)"],
    index=0,
    key="clustering_method",
    help="Radius: groups photos within 90m. DBSCAN: auto-detects clusters by density.",
)
```

- [ ] **Step 2: Wire the clustering method into processing**

In `dashboard.py`, find the call to `processor.process_and_organize_images` (around line 400). After the processing completes and `st.session_state.processed_sites` is set, modify the candidate site creation to use the selected method:

```python
if st.session_state.processed_sites and not st.session_state.candidate_sites:
    agency = st.session_state.customer_info.get("agency_name", "")

    if st.session_state.get("clustering_method") == "DBSCAN (auto)":
        # Re-cluster using DBSCAN from raw image metadata
        from processor import cluster_images_dbscan, cluster_to_candidate_sites
        all_images = []
        for site in st.session_state.processed_sites:
            all_images.extend(site.get("images", []))
        clusters = cluster_images_dbscan(all_images)
        st.session_state.candidate_sites = cluster_to_candidate_sites(
            clusters, agency_name=agency
        )
    else:
        st.session_state.candidate_sites = [
            CandidateSite.from_site_dict(s) for s in st.session_state.processed_sites
        ]

    for site in st.session_state.candidate_sites:
        enrich_gis(site)
```

- [ ] **Step 3: Test manually in browser**

```bash
streamlit run dashboard.py
```

Verify:
1. Select "DBSCAN (auto)" before uploading
2. Upload photos from multiple locations
3. Verify clusters match expected groupings
4. Switch to "Radius (90m)" and re-upload — verify original behavior

- [ ] **Step 4: Commit**

```bash
git add dashboard.py
git commit -m "feat: add clustering method selector (Radius / DBSCAN)"
```

---

## Task 12: Run Full Test Suite and Final Verification

**Files:** None (verification only)

- [ ] **Step 1: Run all tests**

```bash
cd "G:/My Drive/PRIVATE NO ACCESS/Python/app/Monster/ant"
python -m pytest tests/ -v
```

Expected: All tests PASS, including existing tests (`test_processor.py`, `test_pipeline.py`, `test_google_oauth.py`).

- [ ] **Step 2: Verify no import errors**

```bash
python -c "from site_model import CandidateSite, export_sites_json, export_sites_csv; print('site_model OK')"
python -c "from processor import cluster_images_dbscan, cluster_to_candidate_sites; print('processor OK')"
python -c "from analyzer import enrich_gis, estimate_building_height_gemini; print('analyzer OK')"
python -c "from reporter import generate_candidate_site_report; print('reporter OK')"
```

Expected: All print "OK" with no errors.

- [ ] **Step 3: Manual end-to-end test in browser**

```bash
streamlit run dashboard.py
```

Full workflow:
1. Upload 5+ photos with GPS data from at least 2 locations
2. Verify clustering creates separate candidate sites
3. Fill in checklist fields for each site
4. Click "Build Report & Upload to Drive" with enhanced format
5. Download DOCX — verify it has per-site sections, installer quick reference, appendix
6. Download JSON — verify stable field IDs
7. Download CSV — verify one row per site with all field columns

- [ ] **Step 4: Commit any final fixes**

```bash
git add -A
git commit -m "fix: final adjustments from end-to-end testing"
```

- [ ] **Step 5: Update graphify knowledge graph**

```bash
graphify update .
```
