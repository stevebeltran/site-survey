import os
import shutil
import datetime

try:
    import exifread
except Exception:
    exifread = None

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

def _exifread_ratio_to_float(value):
    """Convert ExifRead Ratio objects or numeric values to float."""
    if hasattr(value, 'num') and hasattr(value, 'den'):
        if value.den == 0:
            return 0.0
        return float(value.num) / float(value.den)
    return float(value)

def _parse_exifread_dms(dms, ref):
    """Convert ExifRead DMS values into decimal degrees."""
    degrees = _exifread_ratio_to_float(dms[0])
    minutes = _exifread_ratio_to_float(dms[1])
    seconds = _exifread_ratio_to_float(dms[2])

    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if str(ref).upper() in ['S', 'W']:
        decimal = -decimal
    return decimal

def _extract_gps_with_exifread(image_path):
    """Extract GPS metadata using ExifRead without decoding the image."""
    if exifread is None:
        return None, None, None

    try:
        with open(image_path, 'rb') as fh:
            tags = exifread.process_file(fh, details=False)

        lat_tag = tags.get('GPS GPSLatitude')
        lat_ref = tags.get('GPS GPSLatitudeRef')
        lon_tag = tags.get('GPS GPSLongitude')
        lon_ref = tags.get('GPS GPSLongitudeRef')

        if not (lat_tag and lat_ref and lon_tag and lon_ref):
            return None, None, None

        lat_values = getattr(lat_tag, 'values', lat_tag)
        lon_values = getattr(lon_tag, 'values', lon_tag)
        lat = _parse_exifread_dms(lat_values, lat_ref)
        lon = _parse_exifread_dms(lon_values, lon_ref)

        capture_time = None
        for time_key in ('EXIF DateTimeOriginal', 'Image DateTime', 'EXIF DateTimeDigitized'):
            time_tag = tags.get(time_key)
            if time_tag:
                capture_time = str(time_tag)
                break

        if capture_time:
            try:
                dt = datetime.datetime.strptime(capture_time, '%Y:%m:%d %H:%M:%S')
            except ValueError:
                dt = capture_time
        else:
            dt = datetime.datetime.fromtimestamp(os.path.getctime(image_path))

        return lat, lon, dt
    except Exception as e:
        print(f"ExifRead GPS extraction failed for {image_path}: {e}")
        return None, None, None

def get_decimal_from_dms(dms, ref):
    """Convert degrees, minutes, seconds to decimal degrees."""
    degrees = float(dms[0])
    minutes = float(dms[1])
    seconds = float(dms[2])
    
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    if ref in ['S', 'W']:
        decimal = -decimal
    return decimal

def extract_exif_gps(image_path):
    """
    Extract GPS coordinates and capture time from image metadata.
    Returns (lat, lon, capture_time) or (None, None, None).
    """
    lat_lon_time = _extract_gps_with_exifread(image_path)
    if lat_lon_time != (None, None, None):
        return lat_lon_time

    try:
        with Image.open(image_path) as img:
            exif_data = img._getexif()
            if not exif_data:
                return None, None, None
            
            gps_info = {}
            capture_time = None
            
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                if tag_name == 'GPSInfo':
                    for gps_tag_id in value:
                        gps_tag_name = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        gps_info[gps_tag_name] = value[gps_tag_id]
                elif tag_name in ('DateTimeOriginal', 'DateTime'):
                    capture_time = value

            if 'GPSLatitude' in gps_info and 'GPSLatitudeRef' in gps_info and \
               'GPSLongitude' in gps_info and 'GPSLongitudeRef' in gps_info:
                lat = get_decimal_from_dms(gps_info['GPSLatitude'], gps_info['GPSLatitudeRef'])
                lon = get_decimal_from_dms(gps_info['GPSLongitude'], gps_info['GPSLongitudeRef'])
                
                # Format capture time as datetime object or string
                if capture_time:
                    try:
                        dt = datetime.datetime.strptime(capture_time, '%Y:%m:%d %H:%M:%S')
                    except ValueError:
                        dt = capture_time
                else:
                    # Fallback to file system creation time
                    dt = datetime.datetime.fromtimestamp(os.path.getctime(image_path))
                
                return lat, lon, dt
    except Exception as e:
        print(f"Error reading EXIF from {image_path}: {e}")
    return None, None, None

def cluster_images(images_meta, radius_meters=90.0):
    """
    Group images into clusters based on proximity of GPS coordinates.
    images_meta: List of dicts, each with 'path', 'lat', 'lon', 'time'
    Returns: List of lists of image metadata dicts (each sublist is a cluster).
    """
    # Filter out images without GPS data
    gps_images = [img for img in images_meta if img['lat'] is not None and img['lon'] is not None]
    if not gps_images:
        return []

    clusters = []
    unvisited = set(range(len(gps_images)))

    while unvisited:
        seed_idx = unvisited.pop()
        cluster_indices = {seed_idx}
        frontier = [seed_idx]

        while frontier:
            current_idx = frontier.pop()
            current = gps_images[current_idx]
            neighbors = []

            for candidate_idx in list(unvisited):
                candidate = gps_images[candidate_idx]
                dist = geodesic((current['lat'], current['lon']), (candidate['lat'], candidate['lon'])).meters
                if dist <= radius_meters:
                    neighbors.append(candidate_idx)

            for neighbor_idx in neighbors:
                unvisited.remove(neighbor_idx)
                cluster_indices.add(neighbor_idx)
                frontier.append(neighbor_idx)

        clusters.append([gps_images[idx] for idx in sorted(cluster_indices)])

    return clusters

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

    # Filter out empty strings from splitting (e.g., ",,," case)
    parts = [p for p in parts if p]

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

    street_indicators = {
        'street', 'st', 'road', 'rd', 'avenue', 'ave', 'blvd', 'boulevard',
        'lane', 'ln', 'drive', 'dr', 'way', 'circle', 'cir', 'court', 'ct',
        'place', 'pl', 'terrace', 'parkway', 'path', 'trails'
    }

    # Try to find the first non-street, non-excluded part that's a reasonable city name
    for part in parts:
        part_lower = part.lower()

        # Skip if it's empty
        if not part:
            continue

        # Skip if it's a number (house number)
        if part.isdigit():
            continue

        # Skip if it's an excluded keyword
        if part_lower in excluded_keywords:
            continue

        # Skip if it starts with a digit (street address like "123 Main St")
        if part[0].isdigit():
            continue

        # Skip if it's a street indicator (contains street terms)
        if any(indicator in part_lower for indicator in street_indicators):
            continue

        # This is likely the city
        return part

    return None

def reverse_geocode(lat, lon):
    """
    Get address name for a coordinate using Nominatim.
    Includes rate-limit handling and offline fallback names.
    """
    try:
        # Nominatim requires a descriptive user_agent
        geolocator = Nominatim(user_agent="dfr_site_survey_automation_processor")
        location = geolocator.reverse((lat, lon), timeout=1.5)
        if location and location.address:
            return location.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding service unavailable or timed out: {e}")
    except Exception as e:
        print(f"Geocoding error: {e}")
        
    return f"Site Coordinate ({lat:.5f}, {lon:.5f})"


def _sanitize_folder_name(value, fallback="Police_Department"):
    cleaned = []
    for char in str(value):
        if char.isalnum() or char in ("_", "-"):
            cleaned.append(char)
        else:
            cleaned.append("_")
    name = "".join(cleaned)
    while "__" in name:
        name = name.replace("__", "_")
    name = name.strip("_")
    return name or fallback


def _derive_department_folder_name(full_address=None):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if not full_address or str(full_address).startswith("Site Coordinate ("):
        base = "Police_Department"
    else:
        parts = [part.strip() for part in str(full_address).split(",") if part.strip()]
        location_part = None
        for part in parts:
            normalized = part.lower()
            if any(char.isdigit() for char in part):
                continue
            if "county" in normalized or normalized in {"united states", "usa"}:
                continue
            location_part = part
            break

        if not location_part:
            location_part = parts[0] if parts else "Police_Department"

        base = _sanitize_folder_name(location_part)
        if "police" not in base.lower():
            base = f"{base}_Police_Department"

    return f"{_sanitize_folder_name(base)}_{timestamp}"


def process_and_organize_images(source_dir, output_dir, radius_meters=90.0, progress_callback=None, image_paths=None):
    """
    Scan source_dir for images, cluster by GPS, reverse-geocode,
    create subdirectories in output_dir, copy files, and return structure.
    """
    def _report_progress(percent, message):
        if progress_callback:
            progress_callback(percent, message)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    # Find images. When image_paths is provided, scope this run to that upload batch only.
    valid_extensions = ('.jpg', '.jpeg', '.png', '.tiff', '.webp', '.heic', '.heif')
    if image_paths is None:
        image_paths = []
        for root, _, files in os.walk(source_dir):
            for f in files:
                if f.lower().endswith(valid_extensions):
                    image_paths.append(os.path.join(root, f))
    else:
        image_paths = [
            os.path.abspath(path)
            for path in image_paths
            if str(path).lower().endswith(valid_extensions) and os.path.exists(path)
        ]

    total_images = len(image_paths)
    _report_progress(5, f"Found {total_images} image(s). Scanning EXIF metadata...")
                
    # Extract metadata
    images_meta = []
    no_gps_images = []
    for idx, path in enumerate(image_paths, start=1):
        lat, lon, time_captured = extract_exif_gps(path)
        meta = {
            'path': path,
            'filename': os.path.basename(path),
            'lat': lat,
            'lon': lon,
            'time': time_captured
        }
        if lat is not None and lon is not None:
            images_meta.append(meta)
        else:
            no_gps_images.append(meta)

        if total_images:
            scan_percent = 5 + int((idx / total_images) * 55)
            _report_progress(scan_percent, f"Scanning EXIF metadata... {idx}/{total_images}")
            
    # Cluster images with GPS
    _report_progress(65, "Clustering GPS-tagged images...")
    clusters = cluster_images(images_meta, radius_meters)
    
    site_data = []
    batch_folder_name = _derive_department_folder_name(reverse_geocode(clusters[0][0]["lat"], clusters[0][0]["lon"])) if clusters else _derive_department_folder_name()
    batch_folder = os.path.join(output_dir, batch_folder_name)
    if not os.path.exists(batch_folder):
        os.makedirs(batch_folder)
    
    # Process each cluster
    total_clusters = len(clusters)
    for idx, cluster in enumerate(clusters):
        # Calculate cluster center
        lats = [c['lat'] for c in cluster]
        lons = [c['lon'] for c in cluster]
        center_lat = sum(lats) / len(lats)
        center_lon = sum(lons) / len(lons)
        
        # Name the cluster based on geocoding
        full_address = reverse_geocode(center_lat, center_lon)
        # Create a shorter, filesystem-friendly folder name
        parts = [p.strip() for p in full_address.split(',')]
        short_name = f"Site_{idx+1}_" + "_".join(parts[:2]).replace(" ", "_").replace("/", "-")
        # Keep alphanumeric, underscores, hyphens
        short_name = "".join(c for c in short_name if c.isalnum() or c in ('_', '-'))
        
        site_folder = os.path.join(batch_folder, short_name)
        if not os.path.exists(site_folder):
            os.makedirs(site_folder)
            
        copied_images = []
        for img in cluster:
            dest_path = os.path.join(site_folder, img['filename'])
            shutil.copy2(img['path'], dest_path)
            # Create a copy metadata record with new path
            img_copy = img.copy()
            img_copy['dest_path'] = dest_path
            copied_images.append(img_copy)
            
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

        if total_clusters:
            cluster_percent = 70 + int(((idx + 1) / total_clusters) * 20)
            _report_progress(cluster_percent, f"Organizing sites... {idx + 1}/{total_clusters}")
        
    # Handle images without GPS (put them in an unclassified folder or associate with nearest site if time matches)
    if no_gps_images:
        unclassified_folder = os.path.join(batch_folder, "Unclassified_No_GPS")
        if not os.path.exists(unclassified_folder):
            os.makedirs(unclassified_folder)
        for img in no_gps_images:
            dest_path = os.path.join(unclassified_folder, img['filename'])
            shutil.copy2(img['path'], dest_path)
    
    _report_progress(100, "EXIF scan and clustering complete.")
    return site_data
