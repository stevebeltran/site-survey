import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import json
import csv
import io
from site_model import (
    SurveyPhoto, SiteIdentity, InstallInfo, AccessInfo,
    StructuralInfo, DockLocation, ElectricalInfo, NetworkInfo,
    RFInfo, FlightOps, SiteScores, CandidateSite,
)


class TestSurveyPhoto:
    def test_create_with_required_fields(self):
        photo = SurveyPhoto(photo_id="IMG_001", file_path="/path/to/img.jpg", category="Site")
        assert photo.photo_id == "IMG_001"
        assert photo.category == "Site"
        assert photo.gps_latitude is None
        assert photo.annotations == []

    def test_to_json_roundtrip(self):
        photo = SurveyPhoto(
            photo_id="IMG_002", file_path="/path/to/img.jpg", category="Infrastructure",
            gps_latitude=41.862, gps_longitude=-87.661,
            photo_date="2026-06-21", photo_time="14:30:00",
            photo_heading=270.0, photo_altitude=15.0,
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
            site_name="Police HQ", site_id="Chicago_PD_20260621_1",
            agency_name="Chicago Police Department",
            site_address="1412 S Blue Island Ave, Chicago, IL",
            site_latitude=41.862644, site_longitude=-87.661244,
        )
        assert identity.site_name == "Police HQ"
        assert identity.site_elevation is None
        assert identity.survey_date is None

    def test_identity_to_json(self):
        identity = SiteIdentity(
            site_name="HQ", site_id="CPD_20260621_1", agency_name="CPD",
            site_address="123 Main St", site_latitude=41.0, site_longitude=-87.0,
            site_elevation=200.0, survey_date="2026-06-21", surveyor="Steven Beltran",
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
        info = NetworkInfo(isp_provider="Comcast", upload_speed="50 Mbps", download_speed="200 Mbps")
        data = info.to_json()
        restored = NetworkInfo.from_json(data)
        assert restored.isp_provider == "Comcast"
        assert restored.upload_speed == "50 Mbps"


class TestCandidateSite:
    def _make_site(self, site_id="CPD_20260621_1", name="Police HQ"):
        return CandidateSite(
            identity=SiteIdentity(
                site_name=name, site_id=site_id, agency_name="Chicago PD",
                site_address="1412 S Blue Island Ave", site_latitude=41.862644,
                site_longitude=-87.661244, site_elevation=180.0,
                survey_date="2026-06-21", surveyor="Steven Beltran",
            ),
            photos=[
                SurveyPhoto(photo_id="IMG_001", file_path="/path/001.jpg",
                            category="Site", gps_latitude=41.862644, gps_longitude=-87.661244),
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
