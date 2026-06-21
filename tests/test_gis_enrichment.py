import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import patch, MagicMock
from site_model import CandidateSite, SiteIdentity
from analyzer import enrich_gis, estimate_building_height_gemini


def _make_site(lat=41.862644, lon=-87.661244):
    return CandidateSite(
        identity=SiteIdentity(
            site_name="Test Site", site_id="TEST_001", agency_name="Test PD",
            site_address="123 Main St", site_latitude=lat, site_longitude=lon,
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
        enrich_gis(site)
        assert site.identity.site_elevation is None


class TestEnrichGISElevation:
    @patch("analyzer.requests.get")
    def test_sets_elevation(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"results": [{"elevation": 181.5}]}
        mock_get.return_value = mock_resp
        site = _make_site()
        enrich_gis(site, skip_nominatim=True)
        assert site.identity.site_elevation == 181.5
        assert site.checklist_provenance.get("SITE_ELEVATION") == "auto"


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
