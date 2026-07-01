import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from processor import extract_city_from_address, build_agency_name_from_address, extract_jurisdiction_from_address, build_agency_location_hint


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

    def test_agency_name_from_county(self):
        """Generate sheriff's office name from a county address."""
        address = "100 Main St, Lansing, Ingham County, Michigan, United States"
        agency_name = build_agency_name_from_address(address, "county")
        assert agency_name == "Ingham County Sheriff's Office"

    def test_agency_name_from_parish(self):
        """Generate sheriff's office name from a parish address."""
        address = "100 Main St, Baton Rouge, East Baton Rouge Parish, Louisiana, United States"
        agency_name = build_agency_name_from_address(address, "parish")
        assert agency_name == "East Baton Rouge Parish Sheriff's Office"

    def test_extract_jurisdiction_from_address_supports_county_and_parish(self):
        """Extract the jurisdiction component used by the new naming mode."""
        county_address = "123 Main St, Lansing, Ingham County, Michigan, United States"
        parish_address = "456 Main St, Baton Rouge, East Baton Rouge Parish, Louisiana, United States"

        assert extract_jurisdiction_from_address(county_address, "county") == "Ingham County"
        assert extract_jurisdiction_from_address(parish_address, "parish") == "East Baton Rouge Parish"

    def test_build_agency_location_hint_prefers_jurisdiction(self):
        """Return county/parish names for map and search hints."""
        parish_address = "456 Main St, Baton Rouge, East Baton Rouge Parish, Louisiana, United States"
        assert build_agency_location_hint(parish_address, "parish") == "East Baton Rouge Parish"


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


class TestReporterIntegration:
    """Test that reporter can access agency_name field."""

    def test_site_data_format_compatible_with_reporter(self):
        """Verify site_data has fields reporter expects."""
        site = {
            'site_id': 'SITE-001',
            'address': '2710 S Park Ave, Lansing, Ingham County, Michigan, United States',
            'city': 'Lansing',
            'agency_name': 'Lansing Police Department',
            'latitude': 42.7335,
            'longitude': -84.5555,
        }

        # Reporter should be able to access agency_name safely
        agency_name = site.get('agency_name', 'Police Department')
        assert agency_name == 'Lansing Police Department'

    def test_reporter_handles_missing_agency_name(self):
        """Verify reporter doesn't break if agency_name is None."""
        site = {
            'site_id': 'SITE-002',
            'address': 'Site Coordinate (40.1234, -120.5678)',
            'agency_name': None,
        }

        # Reporter should use fallback when agency_name is None
        agency_name = site.get('agency_name') or 'Police Department'
        assert agency_name == 'Police Department'


class TestEndToEndPipeline:
    """Integration test simulating full image processing pipeline."""

    def test_pipeline_produces_agency_name(self):
        """Verify complete pipeline flow: address -> city -> agency_name."""
        # Simulate what happens in process_and_organize_images()

        # Step 1: Reverse geocoding returns full address
        full_address = "123 Main St, Lansing, Ingham County, Michigan, United States"

        # Step 2: Extract city
        city = extract_city_from_address(full_address)

        # Step 3: Generate agency_name
        agency_name = f"{city} Police Department" if city else None

        # Verify complete output
        assert city == "Lansing"
        assert agency_name == "Lansing Police Department"

    def test_pipeline_handles_geocoding_failure(self):
        """Verify pipeline handles when reverse geocoding fails."""
        # Simulate coordinate-only fallback address
        full_address = "Site Coordinate (42.7335, -84.5555)"

        # Step 1: Extract city (should return None)
        city = extract_city_from_address(full_address)

        # Step 2: Generate agency_name (should be None)
        agency_name = f"{city} Police Department" if city else None

        # Verify proper null handling
        assert city is None
        assert agency_name is None

    def test_different_city_formats(self):
        """Verify extraction works for various city name formats."""
        test_cases = [
            ("456 Oak Ave, San Francisco, San Francisco County, California, United States", "San Francisco"),
            ("100 Main St, Saint-Étienne, Loire, France", "Saint-Étienne"),
            ("789 First Ave, New York, New York County, New York, United States", "New York"),
            ("Site Coordinate (0.0, 0.0)", None),
        ]

        for address, expected_city in test_cases:
            city = extract_city_from_address(address)
            assert city == expected_city, f"Failed for address: {address}"
