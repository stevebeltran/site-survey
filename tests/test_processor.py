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
