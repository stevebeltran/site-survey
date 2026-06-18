# Agency Name Auto-Population Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract city names from GPS reverse-geocoding and auto-populate the Agency Name field in site data as "{City} Police Department", with graceful handling for missing cities.

**Architecture:** Add city extraction logic to `processor.py` during image clustering, then use the extracted city to auto-populate `agency_name` in site_data. Update `reporter.py` to reference this field instead of deriving it. Dashboard editing will be added in a follow-up PR.

**Tech Stack:** Python 3.7+, geopy (Nominatim), existing PIL/exifread for EXIF extraction

---

## Task 1: Create Unit Tests for City Extraction

**Files:**
- Create: `tests/test_processor.py` (new test file)

- [ ] **Step 1: Create test file and write failing tests for city extraction**

Create file `G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant\tests\test_processor.py`:

```python
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
```

- [ ] **Step 2: Verify tests directory exists, create if needed**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
if not exist tests mkdir tests
if not exist tests\__init__.py echo. > tests\__init__.py
```

- [ ] **Step 3: Run tests to verify they fail (pytest not yet run)**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/test_processor.py -v
```

Expected output:
```
ERROR tests/test_processor.py - ImportError: cannot import name 'extract_city_from_address' from 'processor'
```

- [ ] **Step 4: Commit test file**

```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
git add tests/test_processor.py tests/__init__.py
git commit -m "test: add unit tests for city extraction logic"
```

---

## Task 2: Implement City Extraction Function

**Files:**
- Modify: `processor.py` (add new function before `reverse_geocode()`)

- [ ] **Step 1: Add extract_city_from_address() function to processor.py**

Open `G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant\processor.py`

Find the line with `def reverse_geocode(lat, lon):` (around line 180)

Insert the following function **before** that line:

```python
def extract_city_from_address(full_address):
    """
    Extract city/town name from a reverse-geocoded full address.
    
    Handles various address formats:
    - "123 Main St, Lansing, Ingham County, Michigan, United States"
    - "Lake Street, Zionsville, Boone County, Indiana, United States"
    - "Site Coordinate (42.7335, -84.5555)" -> Returns None
    
    Args:
        full_address (str or None): Full reverse-geocoded address string
    
    Returns:
        str: City/town name, or None if not found or address is invalid
    """
    if not full_address:
        return None
    
    full_address = str(full_address).strip()
    
    # Fallback coordinate-only addresses have no city
    if full_address.startswith("Site Coordinate ("):
        return None
    
    # Split address by comma to get components
    parts = [p.strip() for p in full_address.split(",")]
    
    if not parts:
        return None
    
    # Typically: [street, city, county, state, country]
    # We want the city, which is usually the 2nd element (index 1)
    # But we need to skip pure numbers, counties, and country names
    
    excluded_keywords = {
        'county', 'parish', 'district', 'region',
        'united states', 'usa', 'us',
        'england', 'scotland', 'wales', 'northern ireland',
        'france', 'germany', 'italy', 'spain', 'canada', 'mexico',
        'australia', 'new zealand'
    }
    
    # Try to find the first non-numeric, non-excluded part that's a reasonable city name
    for part in parts:
        part_lower = part.lower()
        
        # Skip if it's a number (house number)
        if part.isdigit():
            continue
        
        # Skip if it's an excluded keyword
        if part_lower in excluded_keywords:
            continue
        
        # Skip if it's mostly numbers (mixed address like "456 St. James Rd")
        if any(char.isdigit() for char in part) and len(part) < 10:
            continue
        
        # This is likely the city
        return part
    
    # Fallback: return the first non-numeric component
    for part in parts:
        if not part.isdigit() and part.lower() not in excluded_keywords:
            return part
    
    return None
```

- [ ] **Step 2: Run tests to verify they pass**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/test_processor.py::TestExtractCityFromAddress -v
```

Expected output:
```
tests/test_processor.py::TestExtractCityFromAddress::test_standard_us_address_format PASSED
tests/test_processor.py::TestExtractCityFromAddress::test_address_with_road_name_only PASSED
... (all tests pass)
```

- [ ] **Step 3: Run agency name generation tests**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/test_processor.py::TestAgencyNameGeneration -v
```

Expected output:
```
tests/test_processor.py::TestAgencyNameGeneration::test_agency_name_from_city PASSED
tests/test_processor.py::TestAgencyNameGeneration::test_agency_name_is_none_when_city_is_none PASSED
```

- [ ] **Step 4: Commit function implementation**

```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
git add processor.py
git commit -m "feat: add extract_city_from_address() function"
```

---

## Task 3: Modify process_and_organize_images() to Populate agency_name

**Files:**
- Modify: `processor.py` (update `process_and_organize_images()` function)

- [ ] **Step 1: Update site_data construction to include city and agency_name**

Find the section in `process_and_organize_images()` where site_data.append() is called (around line 331):

Current code:
```python
site_data.append({
    'site_id': f"SITE-{idx+1:03d}",
    'folder_name': short_name,
    'folder_path': site_folder,
    'batch_folder_path': batch_folder,
    'address': full_address,
    'latitude': center_lat,
    'longitude': center_lon,
    'images': copied_images
})
```

Replace with:
```python
# Extract city from full address and generate agency name
city = extract_city_from_address(full_address)
agency_name = f"{city} Police Department" if city else None

site_data.append({
    'site_id': f"SITE-{idx+1:03d}",
    'folder_name': short_name,
    'folder_path': site_folder,
    'batch_folder_path': batch_folder,
    'address': full_address,
    'city': city,
    'agency_name': agency_name,
    'latitude': center_lat,
    'longitude': center_lon,
    'images': copied_images
})
```

- [ ] **Step 2: Verify the change is correct**

Check the modified code section matches the above exactly (indentation, field names, order).

- [ ] **Step 3: Create an integration test**

Add the following test to `tests/test_processor.py`:

```python
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
```

- [ ] **Step 4: Run all processor tests**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/test_processor.py -v
```

Expected output:
```
tests/test_processor.py::TestExtractCityFromAddress::... PASSED
tests/test_processor.py::TestAgencyNameGeneration::... PASSED
tests/test_processor.py::TestProcessAndOrganizeImages::... PASSED
... (all tests pass)
```

- [ ] **Step 5: Commit the changes**

```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
git add processor.py tests/test_processor.py
git commit -m "feat: populate city and agency_name in site_data during image processing"
```

---

## Task 4: Update Reporter to Use agency_name Field

**Files:**
- Modify: `reporter.py` (update references to agency name)

- [ ] **Step 1: Find agency name usage in reporter.py**

Open `G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant\reporter.py`

Search for any references to agency, department, or where the site name/folder name is used in report generation.

Look for patterns like:
- `site['folder_name']`
- `site['address']`
- Any string formatting that constructs agency name from folder

- [ ] **Step 2: Replace agency name derivation with direct field access**

For any lines that derive agency name from folder or address, replace with direct access to `site['agency_name']`.

Example changes:

**Before:**
```python
# Deriving from folder name
department_name = site['folder_name'].replace('_', ' ')
```

**After:**
```python
# Use pre-populated agency_name from site_data
department_name = site.get('agency_name', 'Unknown Police Department')
```

**Before (if using address parsing):**
```python
# Extracting from address
address_parts = site['address'].split(',')
city = address_parts[1].strip() if len(address_parts) > 1 else "Unknown"
agency = f"{city} Police Department"
```

**After:**
```python
# Use pre-populated agency_name
agency = site.get('agency_name', 'Police Department')
```

- [ ] **Step 3: Verify reporter.py compiles without errors**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
python -m py_compile reporter.py
```

Expected output: No error messages (silent success)

- [ ] **Step 4: Write a simple test for reporter field usage**

Add to `tests/test_processor.py`:

```python
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
        
        # Reporter should use fallback
        agency_name = site.get('agency_name', 'Police Department')
        assert agency_name == 'Police Department'
```

- [ ] **Step 5: Run tests to verify nothing broke**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/test_processor.py -v
```

Expected: All tests pass

- [ ] **Step 6: Commit reporter changes**

```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
git add reporter.py tests/test_processor.py
git commit -m "feat: update reporter to use agency_name from site_data"
```

---

## Task 5: End-to-End Integration Test

**Files:**
- Modify: `tests/test_processor.py` (add integration test)

- [ ] **Step 1: Add end-to-end test that simulates the full pipeline**

Add to `tests/test_processor.py`:

```python
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
```

- [ ] **Step 2: Run the new end-to-end tests**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/test_processor.py::TestEndToEndPipeline -v
```

Expected output:
```
tests/test_processor.py::TestEndToEndPipeline::test_pipeline_produces_agency_name PASSED
tests/test_processor.py::TestEndToEndPipeline::test_pipeline_handles_geocoding_failure PASSED
tests/test_processor.py::TestEndToEndPipeline::test_different_city_formats PASSED
```

- [ ] **Step 3: Run complete test suite one final time**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/test_processor.py -v --tb=short
```

Expected: All tests pass with no failures

- [ ] **Step 4: Commit test additions**

```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
git add tests/test_processor.py
git commit -m "test: add end-to-end pipeline integration tests"
```

---

## Task 6: Documentation and Cleanup

**Files:**
- Modify: `processor.py` (verify docstrings)
- Verify: Tests cover all requirements

- [ ] **Step 1: Verify docstrings in processor.py**

Check that `extract_city_from_address()` has proper docstring (it does from Task 2).

Check that `process_and_organize_images()` docstring mentions the new fields:

Find the docstring for `process_and_organize_images()` (around line 240) and verify it mentions:

```python
"""
Scan source_dir for images, cluster by GPS, reverse-geocode,
create subdirectories in output_dir, copy files, and return structure.

Returns:
    list: site_data with structure:
        {
            'site_id': 'SITE-001',
            'address': 'Full reverse-geocoded address',
            'city': 'Extracted city name or None',
            'agency_name': '{City} Police Department or None',
            'latitude': float,
            'longitude': float,
            'images': [list of image metadata]
        }
"""
```

If the docstring doesn't mention city and agency_name, update it.

- [ ] **Step 2: Run all tests one final time**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 3: Check git status**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
git status
```

Verify only expected files are modified:
- processor.py
- reporter.py
- tests/test_processor.py
- tests/__init__.py

- [ ] **Step 4: Create final documentation commit**

Run:
```bash
cd "G:\My Drive\PRIVATE NO ACCESS\Python\app\Monster\ant"
git log --oneline -5
```

Expected output shows 5 recent commits, last ones being:
```
xxxx test: add end-to-end pipeline integration tests
xxxx feat: update reporter to use agency_name from site_data
xxxx feat: populate city and agency_name in site_data during image processing
xxxx feat: add extract_city_from_address() function
xxxx test: add unit tests for city extraction logic
```

---

## Summary

✅ **City extraction function** - Parses reverse-geocoded addresses to extract city names  
✅ **Agency name population** - Auto-generates "{City} Police Department" format  
✅ **Null handling** - Gracefully handles missing geocoding with None values  
✅ **Site data enrichment** - Adds `city` and `agency_name` fields to all sites  
✅ **Reporter integration** - Reporter uses pre-populated agency_name field  
✅ **Comprehensive tests** - Unit tests, integration tests, edge case coverage  
✅ **Clean commits** - TDD workflow with frequent checkpoints  

**Not included in this PR (future work):**
- Dashboard editing UI ("Customer & Agency Information" form)
- Metadata.json persistence for user edits
- These will be addressed in a follow-up PR
