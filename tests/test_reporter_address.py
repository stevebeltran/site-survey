import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reporter import _format_short_address


class TestFormatShortAddress:
    """Test address shortening for display in reports and engineering drawings."""

    def test_strips_police_department_poi(self):
        addr = "Polk Avenue Police Department, 1075 Parkway Drive, West Memphis, Crittenden County, Arkansas, United States"
        result = _format_short_address(addr)
        assert "Polk Avenue Police Department" not in result
        assert "West Memphis" in result
        assert "Arkansas" in result

    def test_strips_fire_station_poi(self):
        addr = "Central Fire Station, 200 Main St, Springfield, Sangamon County, Illinois, United States"
        result = _format_short_address(addr)
        assert "Central Fire Station" not in result
        assert "Springfield" in result

    def test_strips_city_hall_poi(self):
        addr = "Zionsville City Hall, 1100 West Oak Street, Zionsville, Boone County, Indiana, United States"
        result = _format_short_address(addr)
        assert "City Hall" not in result
        assert "Zionsville" in result

    def test_strips_unnamed_poi_followed_by_street_address(self):
        addr = "Some Random Building, 500 Elm Ave, Dallas, Dallas County, Texas, United States"
        result = _format_short_address(addr)
        assert "Some Random Building" not in result
        assert "Dallas" in result

    def test_keeps_normal_street_address(self):
        addr = "1075 Parkway Drive, West Memphis, Crittenden County, Arkansas, United States"
        result = _format_short_address(addr)
        assert "1075 Parkway Drive" in result
        assert "West Memphis" in result
        assert "Arkansas" in result

    def test_removes_county(self):
        addr = "123 Main St, Lansing, Ingham County, Michigan, United States"
        result = _format_short_address(addr)
        assert "County" not in result
        assert "United States" not in result

    def test_removes_country(self):
        addr = "123 Main St, Lansing, Michigan, United States"
        result = _format_short_address(addr)
        assert "United States" not in result

    def test_empty_input(self):
        assert _format_short_address("") == ""
        assert _format_short_address(None) == "None"

    def test_coordinate_fallback(self):
        addr = "Site Coordinate (35.123, -90.456)"
        assert _format_short_address(addr) == addr
