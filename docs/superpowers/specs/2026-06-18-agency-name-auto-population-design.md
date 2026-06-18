# Design: Auto-Populate Agency Name from GPS Coordinates

**Date:** 2026-06-18  
**Status:** Approved  
**Scope:** Site survey image ingestion pipeline  

---

## Overview

When images are ingested, extract GPS coordinates from EXIF metadata, reverse-geocode to find the city/town, and auto-populate the "Agency Name" field in the format `{City} Police Department` (e.g., "Lansing Police Department"). If geocoding fails, mark the field as pending and prompt the user to enter it manually. Users can edit or override the auto-populated value at any time.

---

## Requirements

1. **GPS-to-City Mapping:** Extract city name from reverse-geocoded address
2. **Auto-Populate:** Generate `agency_name = "{City} Police Department"` during image processing
3. **Null Handling:** If city cannot be determined, set `agency_name = None` and mark as pending
4. **User Override:** Users can edit agency_name in dashboard and changes persist
5. **Cross-Session Persistence:** Edits saved to metadata.json so they survive dashboard reloads

---

## Design Details

### 1. City Extraction Function (processor.py)

**New function:** `extract_city_from_address(full_address: str) -> Optional[str]`

**Logic:**
- Parse the reverse-geocoded address string (typically comma-separated components)
- City is typically the 1st or 2nd component (before county/state)
- Examples:
  - `"123 Main St, Lansing, Ingham County, Michigan, United States"` → `"Lansing"`
  - `"Lake Street, Zionsville, Boone County, Indiana, United States"` → `"Zionsville"`
  - `"Site Coordinate (42.1234, -85.5678)"` (no reverse geocode) → `None`

**Return:** City name as string, or None if not found

---

### 2. Site Data Enhancement (processor.py)

**In `process_and_organize_images()` function:**

After reverse geocoding each site cluster:
```python
full_address = reverse_geocode(center_lat, center_lon)
city = extract_city_from_address(full_address)
agency_name = f"{city} Police Department" if city else None

site_data.append({
    'site_id': f"SITE-{idx+1:03d}",
    'folder_name': short_name,
    'folder_path': site_folder,
    'batch_folder_path': batch_folder,
    'address': full_address,
    'city': city,                          # NEW
    'agency_name': agency_name,            # NEW
    'latitude': center_lat,
    'longitude': center_lon,
    'images': copied_images
})
```

**Output example:**
```python
{
    'site_id': 'SITE-001',
    'address': '2710 S Park Ave, Lansing, Ingham County, Michigan, United States',
    'city': 'Lansing',
    'agency_name': 'Lansing Police Department',
    'latitude': 42.7335,
    'longitude': -84.5555,
    ...
}
```

---

### 3. Handling Missing Cities

When reverse geocoding fails (network error, timeout, coordinate in ocean, etc.):

```python
{
    'site_id': 'SITE-002',
    'address': 'Site Coordinate (40.1234, -120.5678)',  # Fallback coordinate-only address
    'city': None,
    'agency_name': None,                   # Marked as pending
    'latitude': 40.1234,
    'longitude': -120.5678,
    ...
}
```

**Dashboard layer** will display: `⚠️ Agency Name - Requires User Input`

---

### 4. User Editing & Persistence

**Dashboard (`dashboard.py`)** displays site in "Customer & Agency Information" form:
- Show `agency_name` field (editable text input)
- If `agency_name is None`, show pending indicator and required validation
- Allow user to override any pre-populated value

**On user save:**
1. Update `agency_name` in site_data
2. Write metadata file: `{batch_folder_path}/agency_metadata.json`
   ```json
   {
     "SITE-001": "Lansing Police Department",
     "SITE-002": "Ingham County Sheriff Office",
     "SITE-003": null
   }
   ```

**On dashboard reload:**
- Load site_data from images (standard processing)
- If `agency_metadata.json` exists, overlay saved agency names:
  ```python
  metadata = load_json(batch_folder / "agency_metadata.json")
  for site in site_data:
      if site['site_id'] in metadata:
          site['agency_name'] = metadata[site['site_id']]
  ```

---

## Files Changed

| File | Change | Impact |
|------|--------|--------|
| `processor.py` | Add `extract_city_from_address()`, modify `process_and_organize_images()` | Site data now includes `city` and `agency_name` |
| `dashboard.py` | Add "Customer & Agency Information" form section (future PR) | Users can view/edit agency_name and save to metadata.json |
| `reporter.py` | Use `site['agency_name']` in Word report output | Report now displays user-supplied or auto-populated agency name |
| `analyzer.py` | No changes | — |
| `main.py` | No changes | — |

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Reverse geocode timeout | Full address becomes coordinate fallback, city=None, agency_name=None |
| Coordinate in ocean/remote area | Same as timeout — no city found, marked pending |
| Address parse fails | City extraction returns None, agency_name set to None |
| User enters blank agency_name in form | Validation requires non-empty input before save |
| metadata.json corrupted | Silently fall back to auto-populated values, log warning |

---

## Testing Checklist

- [ ] Extract city correctly from various address formats
- [ ] Handle None addresses gracefully
- [ ] Site data includes city and agency_name fields
- [ ] Metadata file created/updated on save
- [ ] Metadata file reloaded on dashboard restart
- [ ] User can override pre-populated agency_name
- [ ] Pending indicator shows when agency_name is None
- [ ] Word report uses updated agency_name

---

## Future Enhancements (Out of Scope)

- Multi-agency support (multiple police departments per site)
- API integration for official police department directory
- Agency name validation against known directory
- Batch edit for multiple sites' agency names

---
