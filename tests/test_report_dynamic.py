import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
from unittest.mock import patch
from PIL import Image
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
            photo_id=f"IMG_{i:03d}", file_path=f"/fake/path/img_{i}.jpg",
            category=categories[i % len(categories)],
        ))
    return CandidateSite(
        identity=SiteIdentity(
            site_name=name, site_id=site_id, agency_name="Chicago PD",
            site_address="1412 S Blue Island Ave, Chicago, IL",
            site_latitude=41.862644, site_longitude=-87.661244,
            site_elevation=180.0, survey_date="2026-06-21", surveyor="Steven Beltran",
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
            basemap = Image.new("RGBA", (1332, 714), color=(240, 244, 248, 255))
            with patch("reporter.query_city_boundary", return_value=None), \
                 patch("reporter._build_tile_basemap", return_value=(basemap, 13)):
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
            basemap = Image.new("RGBA", (1332, 714), color=(240, 244, 248, 255))
            with patch("reporter.query_city_boundary", return_value=None), \
                 patch("reporter._build_tile_basemap", return_value=(basemap, 13)):
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
            basemap = Image.new("RGBA", (1332, 714), color=(240, 244, 248, 255))
            with patch("reporter.query_city_boundary", return_value=None), \
                 patch("reporter._build_tile_basemap", return_value=(basemap, 13)):
                result = generate_candidate_site_report([], output_path)
            assert os.path.exists(result)
        finally:
            os.unlink(output_path)

    def test_report_generates_without_point_of_contact_section(self):
        sites = [_make_candidate()]
        customer_info = {
            "agency_name": "Chicago PD",
            "contacts": [
                {
                    "role": "POC",
                    "name": "Alex Carter",
                    "title": "Captain",
                    "email": "alex@example.com",
                    "phone": "222-333-4444",
                },
                {
                    "role": "Facilities",
                    "name": "Jordan Tech",
                    "title": "Engineer",
                    "email": "jordan@example.com",
                    "phone": "999-111-2222",
                },
            ],
            "poc_name": "",
            "poc_email": "",
            "poc_phone": "",
            "facilities_engineer": "",
            "facilities_email": "",
            "facilities_phone": "",
        }
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            output_path = f.name
        try:
            basemap = Image.new("RGBA", (1332, 714), color=(240, 244, 248, 255))
            with patch("reporter.query_city_boundary", return_value=None), \
                 patch("reporter._build_tile_basemap", return_value=(basemap, 13)):
                result = generate_candidate_site_report(sites, output_path, customer_info=customer_info)
            assert os.path.exists(result)
        finally:
            os.unlink(output_path)
