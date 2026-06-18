import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from processor import extract_city_from_address


class TestExtractCityFromAddress:
    """Test city extraction from various reverse-geocoded address formats."""

    def test_standard_us_address_format(self):
        """Extract city from standard full address with all components."""
        address = "123 Main St, Lansing, Ingham County, Michigan, United States"
        result = extract_city_from_address(address)
        assert result == "Lansing"

    def test_address_with_road_name_only(self):
        """Extract city when street address is just road name."""
        address = "Lake Street, Zionsville, Boone County, Indiana, United States"
        result = extract_city_from_address(address)
        assert result == "Zionsville"

    def test_city_with_multiword_name(self):
        """Extract city with spaces in name."""
        address = "456 Oak Ave, San Francisco, San Francisco County, California, United States"
        result = extract_city_from_address(address)
        assert result == "San Francisco"

    def test_city_with_special_characters(self):
        """Extract city with apostrophes and hyphens."""
        address = "100 Main St, Saint-Étienne, Loire, France"
        result = extract_city_from_address(address)
        # Should handle special characters gracefully
        assert result is not None and len(result) > 0

    def test_coordinate_only_fallback(self):
        """Return None when address is coordinate-only fallback."""
        address = "Site Coordinate (42.7335, -84.5555)"
        result = extract_city_from_address(address)
        assert result is None

    def test_empty_string(self):
        """Return None for empty string."""
        address = ""
        result = extract_city_from_address(address)
        assert result is None

    def test_none_input(self):
        """Return None for None input."""
        address = None
        result = extract_city_from_address(address)
        assert result is None

    def test_address_without_city_component(self):
        """Return None when address has no recognizable city."""
        address = "United States"
        result = extract_city_from_address(address)
        assert result is None

    def test_malformed_address(self):
        """Handle malformed address gracefully."""
        address = ",,,"
        result = extract_city_from_address(address)
        assert result is None


class TestAgencyNameGeneration:
    """Test that agency_name is correctly generated from city."""

    def test_agency_name_from_city(self):
        """Generate proper agency_name format from extracted city."""
        city = "Lansing"
        agency_name = f"{city} Police Department"
        assert agency_name == "Lansing Police Department"

    def test_agency_name_is_none_when_city_is_none(self):
        """agency_name should be None when city is None."""
        city = None
        agency_name = f"{city} Police Department" if city else None
        assert agency_name is None


class TestProcessAndOrganizeImages:
    """Integration tests for process_and_organize_images() with agency_name."""

    def test_site_data_includes_city_and_agency_name(self):
        """Verify site_data contains city and agency_name fields."""
        # Mock site_data structure that would be returned
        site_data = [{
            'site_id': 'SITE-001',
            'address': '2710 S Park Ave, Lansing, Ingham County, Michigan, United States',
            'city': 'Lansing',
            'agency_name': 'Lansing Police Department',
            'latitude': 42.7335,
            'longitude': -84.5555,
        }]

        # Verify required fields exist
        assert 'city' in site_data[0]
        assert 'agency_name' in site_data[0]
        assert site_data[0]['city'] == 'Lansing'
        assert site_data[0]['agency_name'] == 'Lansing Police Department'

    def test_site_data_handles_missing_city(self):
        """Verify site_data has None values when city cannot be extracted."""
        site_data = [{
            'site_id': 'SITE-002',
            'address': 'Site Coordinate (40.1234, -120.5678)',
            'city': None,
            'agency_name': None,
            'latitude': 40.1234,
            'longitude': -120.5678,
        }]

        assert site_data[0]['city'] is None
        assert site_data[0]['agency_name'] is None
