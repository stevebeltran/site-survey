import os
import json
import base64
import logging
import requests

logger = logging.getLogger(__name__)

try:
    from google import genai
except ImportError:
    genai = None

def analyze_image_heuristics(image_path):
    """
    Simulate computer vision analysis of site images.
    Parses filenames and uses heuristic patterns to yield high-fidelity,
    structured findings for local testing.
    """
    filename = os.path.basename(image_path).lower()
    
    # Defaults
    roof_access = "Unknown / Not observed"
    roof_type = "Flat Concrete"
    mounting_structures = []
    hardware = []
    confidence = 0.75
    
    # Filename keyword heuristics
    if "hatch" in filename or "door" in filename or "stairs" in filename:
        roof_access = "Roof Access Hatch detected"
        confidence = 0.92
    elif "ladder" in filename or "fire_escape" in filename:
        roof_access = "Exterior Fixed Ladder"
        confidence = 0.88
        
    if "rubber" in filename or "epdm" in filename:
        roof_type = "EPDM / Rubber Membrane"
    elif "vinyl" in filename or "tpo" in filename:
        roof_type = "TPO / Single-ply Vinyl"
    elif "metal" in filename or "corrugated" in filename:
        roof_type = "Standing Seam Metal"
    elif "gravel" in filename or "tar" in filename:
        roof_type = "Tar and Gravel (Built-up Roof)"
        
    if "mount" in filename or "pole" in filename or "mast" in filename:
        mounting_structures.append("Non-penetrating Ballast Mount")
        mounting_structures.append("Steel Antenna Mast")
        confidence = 0.85
    elif "parapet" in filename:
        mounting_structures.append("Parapet Wall Mount")
        confidence = 0.90
    else:
        # Generic fallback mounts
        mounting_structures.append("Non-penetrating Ballast Sled")
        
    if "power" in filename or "conduit" in filename or "box" in filename:
        hardware.append("NEMA 4X Weatherproof Enclosure")
        hardware.append("Liquid-tight Flexible Conduit")
    else:
        hardware.append("Standard Grounding Kit")
        hardware.append("RJ45 Weatherproof Feedthrough")

    return {
        "image_file": os.path.basename(image_path),
        "roof_access": roof_access,
        "roof_type": roof_type,
        "mounting_structures": list(set(mounting_structures)),
        "hardware": list(set(hardware)),
        "confidence_score": confidence
    }

def analyze_image_via_api(image_path, api_key=None, api_url=None):
    """
    Placeholder for cloud/Vision LLM API integration.
    If api_key and api_url are supplied, attempts a payload request.
    Otherwise, falls back to the local heuristics engine.
    """
    if not api_key or not api_url:
        return analyze_image_heuristics(image_path)
        
    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Adjust query/prompt to suit the target API (e.g. Gemini, OpenAI, custom CV model)
        payload = {
            "model": "gemini-2.5-flash" if "gemini" in api_url else "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyze this site survey photo for Drone as a First Responder (DFR) installation. "
                                "Identify: 1. Roof access points (hatch, door, ladder, none). 2. Roof material/type (rubber, TPO, concrete, metal, gravel). "
                                "3. Potential mounting structures (ballasted, parapet, tripod). 4. Hardware/cabling path presence. "
                                "Respond ONLY with valid JSON matching these keys: 'roof_access', 'roof_type', 'mounting_structures' (array), 'hardware' (array), 'confidence_score'."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded_image}"
                            }
                        }
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        response = requests.post(api_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            result = response.json()
            # Parse the inner assistant text if wrapped
            choices = result.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "{}")
                return json.loads(text)
            return result
    except Exception as e:
        print(f"API CV Analysis failed, using heuristics engine. Error: {e}")
        
    return analyze_image_heuristics(image_path)

def analyze_site(site_data_dict, api_key=None, api_url=None):
    """
    Iterates through all images in a site and aggregates infrastructure findings.
    """
    images = site_data_dict.get('images', [])
    findings = []
    
    for img in images:
        path = img.get('dest_path') or img.get('path')
        if os.path.exists(path):
            img_finding = analyze_image_via_api(path, api_key, api_url)
            findings.append(img_finding)
            
    # Aggregate results for the site
    if not findings:
        return {
            "roof_access": "Unknown",
            "roof_type": "Unknown",
            "mounting_structures": [],
            "hardware": [],
            "individual_findings": []
        }
        
    # Consolidate findings (take the highest confidence, or combine arrays)
    roof_access_votes = [f.get("roof_access") for f in findings if f.get("roof_access") != "Unknown / Not observed"]
    roof_types = [f.get("roof_type") for f in findings]
    
    primary_access = roof_access_votes[0] if roof_access_votes else "Unknown / Not observed"
    primary_roof = max(set(roof_types), key=roof_types.count) if roof_types else "Unknown"
    
    all_mounts = set()
    all_hardware = set()
    for f in findings:
        all_mounts.update(f.get("mounting_structures", []))
        all_hardware.update(f.get("hardware", []))
        
    return {
        "roof_access": primary_access,
        "roof_type": primary_roof,
        "mounting_structures": list(all_mounts),
        "hardware": list(all_hardware),
        "individual_findings": findings
    }


def estimate_building_height_gemini(image_path, api_key=None):
    """Use Gemini Flash free tier to estimate building height from a photo.
    Returns dict with 'floors' and 'estimated_height_ft', or None on failure."""
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

    try:
        client = genai.Client(api_key=api_key or "")
        try:
            import PIL.Image
            image_input = PIL.Image.open(image_path)
        except Exception:
            image_input = image_path
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                image_input,
                "How many floors does this building have? Estimate the building "
                "height in feet. Return ONLY valid JSON: "
                '{"floors": <int>, "estimated_height_ft": <int>}',
            ],
        )
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(text)
    except Exception:
        return None


def enrich_gis(site, skip_nominatim=False, progress_callback=None):
    """Enrich a CandidateSite with free GIS data.
    Populates: county, state, zip, elevation, airport/heliport distances, building height.
    Gracefully degrades — any API failure leaves the field as None.

    Args:
        progress_callback: Optional callable(step_name: str) called before each API step.
    """
    def _progress(step):
        if progress_callback:
            progress_callback(step)

    lat = site.identity.site_latitude
    lon = site.identity.site_longitude
    if lat is None or lon is None:
        return

    # ── Nominatim reverse geocode ──
    if not skip_nominatim:
        _progress("Reverse geocoding address...")
        try:
            resp = requests.get(
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
        except Exception as e:
            logger.warning("Nominatim reverse geocode failed for (%s, %s): %s", lat, lon, e)
            site.checklist_provenance["COUNTY_NAME"] = "failed"
            site.checklist_provenance["STATE_NAME"] = "failed"
            site.checklist_provenance["ZIP_CODE"] = "failed"
            site.checklist_provenance["JURISDICTION"] = "failed"

    # ── Open-Elevation API (fallback if EXIF elevation not available) ──
    _progress("Looking up elevation...")
    if site.identity.site_elevation is None:
        try:
            resp = requests.get(
                "https://api.open-elevation.com/api/v1/lookup",
                params={"locations": f"{lat},{lon}"},
                timeout=10,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if results:
                    site.identity.site_elevation = results[0].get("elevation")
                    site.checklist_provenance["SITE_ELEVATION"] = "auto"
        except Exception as e:
            logger.warning("Open-Elevation lookup failed for (%s, %s): %s", lat, lon, e)
            site.checklist_provenance["SITE_ELEVATION"] = "failed"
    else:
        site.checklist_provenance["SITE_ELEVATION"] = "auto"

    # ── Gemini Flash: building height from photo ──
    _progress("Estimating building height...")
    if site.structure.building_height is None:
        overview_photos = [p for p in site.photos if p.category == "Site" and
                          any(kw in p.photo_id.lower() for kw in ["overview", "front", "building"])]
        if not overview_photos and site.photos:
            overview_photos = [site.photos[0]]
        if overview_photos:
            photo_path = overview_photos[0].file_path
            if os.path.exists(photo_path):
                result = estimate_building_height_gemini(photo_path)
                if result and result.get("estimated_height_ft"):
                    site.structure.building_height = float(result["estimated_height_ft"])
                    site.checklist_provenance["BUILDING_HEIGHT"] = "auto"

    # ── Overpass: building height from OSM (fallback) ──
    _progress("Querying OSM building data...")
    if site.structure.building_height is None:
        try:
            bldg_query = f"""
            [out:json][timeout:10];
            way["building"](around:30,{lat},{lon});
            out tags;
            """
            resp = requests.post(
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
                    if height_str:
                        try:
                            site.structure.building_height = float(height_str.replace("m", "").strip()) * 3.281
                            site.checklist_provenance["BUILDING_HEIGHT"] = "auto"
                        except ValueError:
                            pass
                    elif levels_str:
                        try:
                            site.structure.building_height = float(levels_str) * 13.0
                            site.checklist_provenance["BUILDING_HEIGHT"] = "auto"
                        except ValueError:
                            pass
        except Exception as e:
            logger.warning("Overpass building-height lookup failed for (%s, %s): %s", lat, lon, e)
            site.checklist_provenance["BUILDING_HEIGHT"] = site.checklist_provenance.get("BUILDING_HEIGHT") or "failed"

    # ── Elevation delta: Calculate from roof elevation if photo EXIF available ──
    # Store roof elevation from any photo EXIF (before elevation delta calculation)
    if not hasattr(site, '_roof_elevation'):
        site._roof_elevation = None
        for photo in site.photos:
            if hasattr(photo, 'exif_data') and photo.exif_data and photo.exif_data.get('altitude'):
                site._roof_elevation = photo.exif_data.get('altitude')
                site.structure.roof_elevation = site._roof_elevation
                break

    # Calculate height from elevation delta if other methods failed
    if site.structure.building_height is None and site.structure.roof_elevation and site.identity.site_elevation:
        height_delta = site.structure.roof_elevation - site.identity.site_elevation
        if height_delta > 0:
            site.structure.building_height = height_delta
            site.structure.building_height_source = f"Elevation delta (roof {site.structure.roof_elevation:.0f}ft - ground {site.identity.site_elevation:.0f}ft)"
            site.checklist_provenance["BUILDING_HEIGHT"] = "auto"

    # ── Overpass: airport and heliport distances ──
    _progress("Searching for nearby airports & heliports...")
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
        resp = requests.post(
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
    except Exception as e:
        logger.warning("Overpass airport/heliport lookup failed for (%s, %s): %s", lat, lon, e)
        site.checklist_provenance["NEARBY_AIRPORTS"] = site.checklist_provenance.get("NEARBY_AIRPORTS") or "failed"
        site.checklist_provenance["NEARBY_HELIPORTS"] = site.checklist_provenance.get("NEARBY_HELIPORTS") or "failed"
