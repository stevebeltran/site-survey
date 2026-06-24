import os
import shutil
import datetime
import logging
import tempfile

from site_model import CandidateSite, SiteIdentity, SurveyPhoto, categorize_photo_by_filename

logger = logging.getLogger(__name__)

try:
    import exifread
except Exception:
    exifread = None

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

from PIL import Image, ImageOps
from PIL.ExifTags import TAGS, GPSTAGS
from geopy.distance import geodesic
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

try:
    from reporter import _format_short_address as _report_short_address
except Exception:
    _report_short_address = None

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

def split_clusters_by_time_gap(clusters, gap_minutes=10, min_spatial_meters=50):
    """Split clusters where consecutive photos have both a large time gap and spatial separation.

    Requires BOTH conditions to split: time gap >= gap_minutes AND the centroid of the
    current group is >= min_spatial_meters from the next photo. This prevents splitting
    a single physical site where a surveyor paused before continuing to photograph.

    Args:
        clusters: list of lists of image meta dicts (each dict has 'time').
        gap_minutes: minimum gap in minutes to trigger a split.
        min_spatial_meters: minimum centroid-to-point distance in meters to trigger a split.

    Returns:
        list of lists — same shape, but clusters with internal time AND spatial gaps
        are split into separate entries.
    """
    from datetime import timedelta

    gap_threshold = timedelta(minutes=gap_minutes)
    result = []

    for cluster in clusters:
        timed = [img for img in cluster if img.get("time") is not None]
        untimed = [img for img in cluster if img.get("time") is None]

        if len(timed) <= 1:
            result.append(cluster)
            continue

        timed.sort(key=lambda m: m["time"])
        current_group = [timed[0]]

        for prev, curr in zip(timed, timed[1:]):
            time_gap = curr["time"] - prev["time"] >= gap_threshold
            if time_gap and curr.get("lat") and curr.get("lon"):
                lats = [m["lat"] for m in current_group if m.get("lat")]
                lons = [m["lon"] for m in current_group if m.get("lon")]
                if lats and lons:
                    centroid = (sum(lats) / len(lats), sum(lons) / len(lons))
                    dist = geodesic(centroid, (curr["lat"], curr["lon"])).meters
                    if dist >= min_spatial_meters:
                        result.append(current_group)
                        current_group = [curr]
                        continue
            current_group.append(curr)

        current_group.extend(untimed)
        result.append(current_group)

    return result


MIN_SITE_PHOTOS = 5  # Clusters with fewer photos are random, not real sites


def cluster_to_candidate_sites(clusters, agency_name="", survey_date=None):
    """Convert cluster output into a list of CandidateSite objects.

    Clusters with fewer than MIN_SITE_PHOTOS images are dropped.

    Args:
        clusters: list of lists of image meta dicts.
        agency_name: agency name to set on all sites.
        survey_date: survey date string (YYYY-MM-DD). Defaults to today.

    Returns:
        list[CandidateSite]
    """
    from datetime import datetime as _dt
    if survey_date is None:
        survey_date = _dt.now().strftime("%Y-%m-%d")

    sites = []
    for idx, cluster in enumerate(clusters, start=1):
        if not cluster or len(cluster) < MIN_SITE_PHOTOS:
            continue

        lats = [m["lat"] for m in cluster if m.get("lat") is not None]
        lons = [m["lon"] for m in cluster if m.get("lon") is not None]
        center_lat = sum(lats) / len(lats) if lats else 0.0
        center_lon = sum(lons) / len(lons) if lons else 0.0

        addr = ""
        city = ""
        try:
            result = reverse_geocode(center_lat, center_lon)
            if result:
                addr = result
                city = extract_city_from_address(result)
        except Exception as e:
            logger.warning("Reverse geocode failed for cluster %d at (%s, %s): %s", idx, center_lat, center_lon, e)

        site_name = city if city else f"Site {idx}"
        safe_agency = agency_name.replace(" ", "_") if agency_name else "Survey"
        site_id = f"{safe_agency}_{survey_date.replace('-', '')}_{idx}"

        identity = SiteIdentity(
            site_name=site_name,
            site_id=site_id,
            agency_name=agency_name,
            site_address=addr,
            site_latitude=center_lat,
            site_longitude=center_lon,
            survey_date=survey_date,
        )

        photos = []
        for img in cluster:
            filename = img.get("filename", os.path.basename(img.get("path", "")))
            file_path = img.get("dest_path", img.get("path", ""))
            time_str = str(img.get("time", "")) if img.get("time") else ""
            photo = SurveyPhoto(
                photo_id=filename,
                file_path=file_path,
                category=categorize_photo_by_filename(filename),
                gps_latitude=img.get("lat"),
                gps_longitude=img.get("lon"),
                photo_date=time_str.split(" ")[0] if time_str else None,
                photo_time=time_str.split(" ")[1] if " " in time_str else None,
            )
            photos.append(photo)

        sites.append(CandidateSite(identity=identity, photos=photos))

    return sites


def extract_city_from_address(full_address):
    """
    Extract city/town name from a reverse-geocoded full address.

    Handles various address formats:
    - "123 Main St, Lansing, Ingham County, Michigan, United States"
    - "Lake Street, Zionsville, Boone County, Indiana, United States"
    - "Zionsville Police Department, 1075 Parkway Drive, ..." -> Returns "Zionsville"
    - "Site Coordinate (42.7335, -84.5555)" -> Returns None

    Args:
        full_address (str or None): Full reverse-geocoded address string

    Returns:
        str: City/town name (without "Police Department" suffix), or None if not found or address is invalid
    """
    if not full_address:
        return None

    # Use structured city data from Nominatim when available (GeoResult)
    if hasattr(full_address, 'city') and full_address.city:
        return full_address.city

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

    # Single-word geographic terms to exclude (matched per-word)
    excluded_words = {
        'county', 'parish', 'district', 'region',
        'usa', 'us',
    }
    # Multi-word phrases to exclude (matched against full part)
    excluded_phrases = {
        'united states',
        'england', 'scotland', 'wales', 'northern ireland',
        'france', 'germany', 'italy', 'spain', 'canada', 'mexico',
        'australia', 'new zealand',
    }

    # Street type words (matched per-word, not as substrings)
    street_indicators = {
        'street', 'st', 'road', 'rd', 'avenue', 'ave', 'blvd', 'boulevard',
        'lane', 'ln', 'drive', 'dr', 'way', 'circle', 'cir', 'court', 'ct',
        'place', 'pl', 'terrace', 'parkway', 'path', 'trails',
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

        # Skip if it starts with a digit (street address like "123 Main St")
        if part[0].isdigit():
            continue

        # Word-level matching: split into individual words for precise checks
        part_words = set(part_lower.split())

        # Skip if any word is an excluded geographic term (e.g. "Crittenden County")
        if part_words & excluded_words:
            continue

        # Skip if full part matches a multi-word excluded phrase
        if part_lower in excluded_phrases:
            continue

        # Skip if any word is a street type indicator
        # (word-level match prevents "st" from matching inside "West")
        if part_words & street_indicators:
            continue

        # This is likely the city. Remove "Police Department" suffix if present
        # (handles cases where reverse geocode returns "City Police Department")
        city = part.strip()
        if city.lower().endswith(" police department"):
            city = city[:-len(" police department")].strip()

        return city if city else None

    return None


class GeoResult(str):
    """String subclass that carries structured city/state data from Nominatim.

    Behaves exactly like a str (the full address) everywhere existing code
    uses it, but also exposes .city and .state attributes extracted from
    Nominatim's structured address fields.
    """
    def __new__(cls, address, city=None, state=None):
        instance = super().__new__(cls, address)
        instance.city = city
        instance.state = state
        return instance


def reverse_geocode(lat, lon):
    """
    Get address name for a coordinate using Nominatim.
    Includes rate-limit handling and offline fallback names.
    Returns a GeoResult (str subclass) with a .city attribute from structured data.
    """
    try:
        # Nominatim requires a descriptive user_agent
        geolocator = Nominatim(user_agent="dfr_site_survey_automation_processor")
        location = geolocator.reverse((lat, lon), timeout=1.5)
        if location and location.address:
            # Extract city and state from Nominatim's structured address fields
            city = None
            raw_addr = location.raw.get('address', {})
            for key in ('city', 'town', 'village', 'hamlet', 'municipality'):
                if key in raw_addr:
                    city = raw_addr[key]
                    break
            state = raw_addr.get('state')
            return GeoResult(location.address, city=city, state=state)
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"Geocoding service unavailable or timed out: {e}")
    except Exception as e:
        print(f"Geocoding error: {e}")

    return GeoResult(f"Site Coordinate ({lat:.5f}, {lon:.5f})")


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


def _drive_site_folder_name(full_address, site_id=None):
    """Build a readable Drive folder name for a site using its address."""
    short_address = _report_short_address(full_address) if _report_short_address else full_address
    address_name = _sanitize_folder_name(short_address, fallback="")
    if address_name:
        return address_name
    if site_id:
        return _sanitize_folder_name(site_id, fallback="Site")
    return "Site"


def _prepare_drive_image_upload(src_path, work_dir, max_side=2400, jpeg_quality=82):
    """Create a smaller Drive-only copy of an image when possible."""
    if not os.path.exists(src_path):
        return src_path, os.path.basename(src_path)

    try:
        with Image.open(src_path) as src_img:
            image = ImageOps.exif_transpose(src_img)
            image.thumbnail((max_side, max_side), Image.LANCZOS)

            has_alpha = (
                image.mode in ("RGBA", "LA")
                or (image.mode == "P" and "transparency" in image.info)
            )
            base_name = os.path.splitext(os.path.basename(src_path))[0]
            if has_alpha:
                output_path = os.path.join(work_dir, f"{base_name}_drive.png")
                image.save(output_path, format="PNG", optimize=True)
            else:
                output_path = os.path.join(work_dir, f"{base_name}_drive.jpg")
                if image.mode != "RGB":
                    image = image.convert("RGB")
                image.save(
                    output_path,
                    format="JPEG",
                    quality=jpeg_quality,
                    optimize=True,
                    progressive=True,
                )
            return output_path, os.path.basename(output_path)
    except Exception as e:
        print(f"Drive image compression skipped for {src_path}: {e}")
        return src_path, os.path.basename(src_path)


def _derive_department_folder_name(full_address=None, agency_name=None):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # Prefer the explicit agency name when provided
    if agency_name and str(agency_name).strip():
        base = _sanitize_folder_name(agency_name)
        return f"{base}_{timestamp}"

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


def process_and_organize_images(source_dir, output_dir, radius_meters=90.0, progress_callback=None, image_paths=None, drive_manager=None, drive_output_folder_id=None, agency_name=None):
    """
    Scan source_dir for images, cluster by GPS, reverse-geocode,
    create subdirectories in output_dir, copy files, and return structure.

    Can optionally upload processed files to Google Drive if drive_manager and
    drive_output_folder_id are provided.

    Args:
        source_dir: Directory containing source images
        output_dir: Directory for local output
        radius_meters: GPS clustering radius (default 90m)
        progress_callback: Optional callback for progress updates
        image_paths: Optional list of specific image paths to process
        drive_manager: Optional GoogleDriveManager instance for Drive upload
        drive_output_folder_id: Optional Google Drive folder ID for upload
        agency_name: Optional agency name for folder labeling

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
    clusters = cluster_images(images_meta, radius_meters=radius_meters)
    clusters = split_clusters_by_time_gap(clusters)
    clusters = [c for c in clusters if len(c) >= MIN_SITE_PHOTOS]

    site_data = []
    batch_folder_name = _derive_department_folder_name(
        full_address=reverse_geocode(clusters[0][0]["lat"], clusters[0][0]["lon"]) if clusters else None,
        agency_name=agency_name,
    )
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
        # Create a shorter, filesystem-friendly folder name from the short address
        short_name = _drive_site_folder_name(full_address, f"SITE_{idx+1:03d}")
        
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
            
        # Extract city from full address; use caller-provided agency name if available
        city = extract_city_from_address(full_address)
        site_agency = agency_name or (f"{city} Police Department" if city else None)

        site_data.append({
            'site_id': f"SITE-{idx+1:03d}",
            'folder_name': short_name,
            'folder_path': site_folder,
            'batch_folder_path': batch_folder,
            'address': full_address,
            'city': city,
            'agency_name': site_agency,
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

    # If using Google Drive, upload processed files
    if drive_manager and drive_output_folder_id:
        drive_upload_dir = tempfile.mkdtemp(prefix="dfr_drive_uploads_")
        try:
            for site in site_data:
                # Upload site folder structure to Drive
                site_folder_name = _drive_site_folder_name(
                    site.get('address'),
                    site.get('site_id')
                )
                drive_site_folder_id = drive_manager.get_or_create_folder(
                    drive_output_folder_id,
                    site_folder_name
                )

                # Upload images from this site
                for img in site.get('images', []):
                    if 'dest_path' in img and os.path.exists(img['dest_path']):
                        upload_path, upload_name = _prepare_drive_image_upload(
                            img['dest_path'],
                            drive_upload_dir,
                        )
                        drive_manager.upload_file(
                            upload_path,
                            drive_site_folder_id,
                            file_name=upload_name,
                        )
        except ValueError as e:
            print(f"Drive upload error: {e}")
        except Exception as e:
            print(f"Unexpected error during Drive upload: {e}")
        finally:
            shutil.rmtree(drive_upload_dir, ignore_errors=True)

    _report_progress(100, "EXIF scan and clustering complete.")
    return site_data
