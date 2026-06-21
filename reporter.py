import os
import re
import datetime
import requests
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from geopy.distance import geodesic
from PIL import Image, ImageDraw, ImageFont


def _load_font(bold=False, size=28):
    """Load a TrueType font, trying Windows Arial first then Linux DejaVu."""
    candidates = (
        ["arialbd.ttf", "Arial Bold.ttf"] if bold
        else ["arial.ttf", "Arial.ttf"]
    ) + [
        # Linux / Streamlit Cloud paths
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _format_short_address(full_address):
    """Shorten a Nominatim address to just street, city, state zip."""
    if not full_address:
        return str(full_address)
    addr = str(full_address).strip()
    if addr.startswith("Site Coordinate"):
        return addr

    parts = [p.strip() for p in addr.split(',') if p.strip()]

    # Remove country names and county/parish parts
    excluded = {'united states', 'usa', 'us'}
    filtered = [
        p for p in parts
        if p.lower() not in excluded
        and 'county' not in p.lower()
        and 'parish' not in p.lower()
    ]

    # Drop leading POI/business name when followed by a house number
    if (len(filtered) >= 2
            and not filtered[0][0].isdigit()
            and filtered[1].strip().isdigit()):
        filtered = filtered[1:]

    # Merge house number + street name  ("1075", "Parkway Drive" -> "1075 Parkway Drive")
    combined = []
    i = 0
    while i < len(filtered):
        if (filtered[i].isdigit()
                and i + 1 < len(filtered)
                and not filtered[i + 1][0].isdigit()):
            combined.append(f"{filtered[i]} {filtered[i + 1]}")
            i += 2
        else:
            combined.append(filtered[i])
            i += 1

    # Merge state + zip  ("Indiana", "46077" -> "Indiana 46077")
    final = []
    i = 0
    while i < len(combined):
        if (i + 1 < len(combined)
                and re.match(r'^\d{5}(-\d{4})?$', combined[i + 1])):
            final.append(f"{combined[i]} {combined[i + 1]}")
            i += 2
        else:
            final.append(combined[i])
            i += 1

    return ', '.join(final)

def query_nearest_airfield(lat, lon):
    """
    Search for the nearest aerodrome (airfield/airport) within 25km
    using the OpenStreetMap Overpass API.
    """
    url = "https://overpass-api.de/api/interpreter"
    query = f"""
    [out:json][timeout:5];
    (
      node["aeroway"="aerodrome"](around:25000,{lat},{lon});
      way["aeroway"="aerodrome"](around:25000,{lat},{lon});
      relation["aeroway"="aerodrome"](around:25000,{lat},{lon});
    );
    out center;
    """
    try:
        response = requests.post(url, data={"data": query}, timeout=1.5)
        if response.status_code == 200:
            data = response.json()
            elements = data.get("elements", [])
            
            nearest = None
            min_dist = float('inf')
            
            for elem in elements:
                elem_lat = elem.get('lat') or elem.get('center', {}).get('lat')
                elem_lon = elem.get('lon') or elem.get('center', {}).get('lon')
                
                if elem_lat and elem_lon:
                    dist = geodesic((lat, lon), (elem_lat, elem_lon)).miles
                    if dist < min_dist:
                        min_dist = dist
                        tags = elem.get("tags", {})
                        name = tags.get("name") or tags.get("icao") or tags.get("iata") or "Unnamed Airfield"
                        nearest = (name, min_dist)
            return nearest
    except Exception as e:
        print(f"Error querying airfield from Overpass: {e}")
    
    return ("Local Regional Airport", 8.2)

def query_airspace_class(lat, lon):
    """
    Lookup Airspace Class (B, C, D, E, G) for coordinate.
    """
    faa_url = "https://services.arcgis.com/ssuPAZ6sA156nEBb/arcgis/rest/services/US_Class_Airspace/FeatureServer/0/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "CLASS",
        "f": "json",
        "returnGeometry": "false"
    }
    try:
        response = requests.get(faa_url, params=params, timeout=1.5)
        if response.status_code == 200:
            data = response.json()
            features = data.get("features", [])
            if features:
                airspace_class = features[0].get("attributes", {}).get("CLASS")
                if airspace_class:
                    return f"Controlled (Class {airspace_class})"
    except Exception as e:
        print(f"Error querying FAA airspace service: {e}")
        
    return "Class G"


def query_city_boundary(city_name, state_name=None):
    """Fetch the GeoJSON boundary polygon for a city from OpenStreetMap.

    Uses the Overpass API to find the administrative boundary (admin_level=8)
    matching the city name. Returns the polygon as GeoJSON geometry, or None.

    Args:
        city_name: e.g. "Zionsville"
        state_name: e.g. "Indiana" (optional, helps disambiguate)

    Returns:
        dict with GeoJSON geometry (type, coordinates), or None on failure.
    """
    if not city_name:
        return None

    url = "https://overpass-api.de/api/interpreter"
    # admin_level=8 is city/town in the US
    area_filter = ""
    if state_name:
        area_filter = f'area["name"="{state_name}"]["admin_level"="4"]->.state;'

    in_area = "(area.state)" if state_name else ""
    query = f"""
    [out:json][timeout:10];
    {area_filter}
    relation["name"="{city_name}"]["admin_level"="8"]{in_area};
    out geom;
    """
    try:
        headers = {"Accept": "application/json", "User-Agent": "DFR-SiteSurvey/1.0"}
        response = requests.post(url, data={"data": query}, headers=headers, timeout=20)
        if response.status_code != 200:
            return None
        data = response.json()
        elements = data.get("elements", [])
        if not elements:
            return None

        # Build the polygon from the relation's members
        relation = elements[0]
        outer_rings = []
        for member in relation.get("members", []):
            if member.get("type") == "way" and member.get("role") in ("outer", ""):
                coords = [(pt["lon"], pt["lat"]) for pt in member.get("geometry", [])]
                if coords:
                    outer_rings.append(coords)

        if not outer_rings:
            return None

        # Try to merge connected ways into a single ring
        merged = _merge_way_segments(outer_rings)

        if len(merged) == 1:
            return {"type": "Polygon", "coordinates": [merged[0]]}
        else:
            return {"type": "MultiPolygon", "coordinates": [[ring] for ring in merged]}

    except Exception as e:
        print(f"Error querying city boundary from Overpass: {e}")
        return None


def _merge_way_segments(segments):
    """Merge ordered way segments into closed rings by connecting endpoints."""
    if not segments:
        return []
    # Work with copies
    remaining = [list(s) for s in segments]
    rings = []

    while remaining:
        current = remaining.pop(0)
        changed = True
        while changed:
            changed = False
            for i, seg in enumerate(remaining):
                # Check if seg connects to the end of current
                if _coords_close(current[-1], seg[0]):
                    current.extend(seg[1:])
                    remaining.pop(i)
                    changed = True
                    break
                elif _coords_close(current[-1], seg[-1]):
                    current.extend(reversed(seg[:-1]))
                    remaining.pop(i)
                    changed = True
                    break
                elif _coords_close(current[0], seg[-1]):
                    current = seg[:-1] + current
                    remaining.pop(i)
                    changed = True
                    break
                elif _coords_close(current[0], seg[0]):
                    current = list(reversed(seg[1:])) + current
                    remaining.pop(i)
                    changed = True
                    break
        # Close the ring if needed
        if not _coords_close(current[0], current[-1]):
            current.append(current[0])
        rings.append(current)

    return rings


def _coords_close(a, b, tol=1e-6):
    """Check if two (lon, lat) coordinate pairs are approximately equal."""
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def draw_styled_map(site_data_list, output_map_path):
    """
    Create a beautiful stylized site coordinates map visualization using PIL.
    """
    width, height = 800, 450
    img = Image.new('RGB', (width, height), color='#0F172A')
    draw = ImageDraw.Draw(img)
    
    # Draw dark grid lines
    grid_spacing = 50
    for x in range(0, width, grid_spacing):
        draw.line([(x, 0), (x, height)], fill='#1E293B', width=1)
    for y in range(0, height, grid_spacing):
        draw.line([(0, y), (width, y)], fill='#1E293B', width=1)
        
    if not site_data_list:
        img.save(output_map_path)
        return output_map_path
        
    lats = [s['latitude'] for s in site_data_list]
    lons = [s['longitude'] for s in site_data_list]
    
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    lat_range = max(max_lat - min_lat, 0.01)
    lon_range = max(max_lon - min_lon, 0.01)
    
    def to_pixel(lat, lon):
        x = 100 + ((lon - min_lon) / lon_range) * 600
        y = 350 - ((lat - min_lat) / lat_range) * 250
        return int(x), int(y)
        
    coords = [to_pixel(s['latitude'], s['longitude']) for s in site_data_list]
    if len(coords) > 1:
        draw.line(coords + [coords[0]], fill='#3B82F6', width=2)
        
    for idx, site in enumerate(site_data_list):
        px, py = to_pixel(site['latitude'], site['longitude'])
        draw.ellipse([px-12, py-12, px+12, py+12], outline='#3B82F6', width=2)
        draw.ellipse([px-6, py-6, px+6, py+6], fill='#EF4444')
        label = f"Location #{idx+1} - {site['address'].split(',')[0]}"
        draw.text((px+16, py-8), label, fill='#F8FAFC')
        
    draw.rectangle([10, 10, 320, 70], fill='#1E293B', outline='#3B82F6')
    draw.text((20, 20), "DFR DEPLOYMENT NETWORK MAP", fill='#3B82F6')
    draw.text((20, 40), f"Active Locations: {len(site_data_list)} Nodes", fill='#94A3B8')
    
    img.save(output_map_path)
    return output_map_path

def create_engineering_drawing(bg_path, output_path, markers, engineer_note, address=None, overlay_image_path=None, image_placements=None, images_dir=None):
    """
    Renders an engineering drawing with a black tech sidebar legend (right),
    rounded callout labels with connecting path lines, and an engineer's note box (bottom left).
    Optionally includes placed images at specified coordinates.
    """
    # Canvas Size
    canvas_w, canvas_h = 1200, 675
    bg_w = 960  # Background image width
    sidebar_w = 240  # Sidebar width

    # Create master canvas
    canvas = Image.new('RGB', (canvas_w, canvas_h), color='#000000')
    draw = ImageDraw.Draw(canvas)
    
    # Initialize fonts (must be done before any text rendering below)
    font_bubble = _load_font(bold=True, size=28)
    font_legend = _load_font(bold=True, size=26)
    font_title = _load_font(bold=True, size=22)
    font_small = _load_font(bold=False, size=14)
    font_note = _load_font(bold=False, size=16)

    # Draw background image
    if os.path.exists(bg_path):
        try:
            with Image.open(bg_path) as img:
                img_resized = img.resize((bg_w, canvas_h))
                canvas.paste(img_resized, (0, 0))
        except Exception as e:
            draw.rectangle([0, 0, bg_w, canvas_h], fill='#1e293b')
            draw.text((100, 300), f"Error loading image: {e}", fill='#ffffff')
    else:
        draw.rectangle([0, 0, bg_w, canvas_h], fill='#1e293b')
        draw.text((100, 300), "No background image selected", fill='#ffffff')

    # Add Address at the top center of the photo area
    if address:
        # Draw address header at top center of photo area
        addr_text = _format_short_address(address)
        addr_bbox = draw.textbbox((0, 0), addr_text, font=font_title)
        addr_width = addr_bbox[2] - addr_bbox[0]
        addr_height = addr_bbox[3] - addr_bbox[1]

        # Position at top center of photo area, clamped to stay in bounds
        addr_x = max(12, (bg_w - addr_width) // 2)
        addr_y = 10

        # If text is wider than photo area, truncate with ellipsis
        if addr_width > bg_w - 30:
            while addr_width > bg_w - 30 and len(addr_text) > 10:
                addr_text = addr_text[:-4] + "..."
                addr_bbox = draw.textbbox((0, 0), addr_text, font=font_title)
                addr_width = addr_bbox[2] - addr_bbox[0]
                addr_height = addr_bbox[3] - addr_bbox[1]
            addr_x = max(12, (bg_w - addr_width) // 2)

        # Draw background box for readability
        padding = 12
        draw.rectangle(
            [addr_x - padding, addr_y - padding, addr_x + addr_width + padding, addr_y + addr_height + padding],
            fill='#000000',
            outline='#3B82F6',
            width=2
        )
        draw.text((addr_x, addr_y), addr_text, fill='#F8FAFC', font=font_title)

    # Add BRINC logo in the upper-left corner of the photo area.
    logo_path = os.path.join(os.path.dirname(__file__), "images", "BRINC_Logo_White.png")
    if os.path.exists(logo_path):
        try:
            with Image.open(logo_path) as logo_src:
                logo = logo_src.convert("RGBA")
                max_width = 180
                logo_ratio = max_width / float(logo.width)
                logo_size = (max_width, max(1, int(logo.height * logo_ratio)))
                logo = logo.resize(logo_size, Image.LANCZOS)

                # Remove the black background so the mark sits cleanly on the photo.
                pixels = logo.load()
                for y in range(logo.height):
                    for x in range(logo.width):
                        r, g, b, a = pixels[x, y]
                        if r < 20 and g < 20 and b < 20:
                            pixels[x, y] = (r, g, b, 0)
                        else:
                            pixels[x, y] = (r, g, b, 255)
                canvas.paste(logo, (20, 20), logo)
        except Exception as e:
            draw.text((20, 20), f"Logo load error: {e}", fill='#ffffff')

    # Draw Tech Sidebar Legend on the Right
    # Dark black background
    draw.rectangle([bg_w, 0, canvas_w, canvas_h], fill='#09090b')
    
    # Legend Items
    legend_items = [
        ("Ethernet", "#F97316"),   # Orange
        ("RF Xmit", "#A855F7"),    # Purple
        ("Electric", "#EF4444"),   # Red
        ("Unistrut", "#94A3B8"),   # Grey/Blue
        ("Lift", "#EAB308"),       # Yellow
        ("Station", "#F8FAFC")     # White
    ]
    
    # Draw "LEGEND" header
    legend_header_y = 25
    draw.text((bg_w + 20, legend_header_y), "LEGEND", fill='#F8FAFC', font=font_title)
    draw.line([(bg_w + 20, legend_header_y + 30), (canvas_w - 20, legend_header_y + 30)], fill='#334155', width=1)

    # Center legend items vertically in sidebar (below header, above brinc text)
    legend_item_spacing = 45
    legend_total_height = len(legend_items) * legend_item_spacing
    legend_start_y = legend_header_y + 50  # Start below header line

    for i, (title, color) in enumerate(legend_items):
        item_y = legend_start_y + i * legend_item_spacing
        # Draw colored circle swatch (20px diameter)
        cx, cy = bg_w + 30, item_y + 10
        draw.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=color)
        # Draw label text
        draw.text((bg_w + 55, item_y), title, fill=color, font=font_legend)

    # Draw "brinc" stylized logo at the bottom right
    draw.text((bg_w + 20, canvas_h - 60), "brinc", fill='#F8FAFC', font=font_legend)

    # Draw Markers & Callouts on the background image
    # Track placed bubble rectangles for collision avoidance
    placed_bubbles = []

    for m in markers:
        # Convert percent to actual pixel coords
        nx = int((m['node_x'] / 100.0) * bg_w)
        ny = int((m['node_y'] / 100.0) * canvas_h)

        m_type = m.get('type', 'Electric')
        label_text = m.get('label', '')

        # Select color matching type
        color_map = {
            'Data': '#F97316',
            'RF': '#A855F7',
            'Unistrut': '#94A3B8',
            'Lift': '#EAB308',
        }
        border_color = color_map.get(m_type, '#EF4444')

        # Measure actual text size for accurate bubble dimensions
        bbox = draw.textbbox((0, 0), label_text, font=font_bubble)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        pad_x, pad_y = 14, 14
        bubble_w = text_w + pad_x * 2
        bubble_h = text_h + pad_y * 2

        # Smart bubble placement: try 4 directions, check edge + collision
        offset_x = int(bg_w * 0.15)
        offset_y = int(canvas_h * 0.08)

        candidates = [
            (nx - offset_x - bubble_w // 2, ny - offset_y - bubble_h // 2),  # upper-left
            (nx + offset_x - bubble_w // 2, ny - offset_y - bubble_h // 2),  # upper-right
            (nx + offset_x - bubble_w // 2, ny + offset_y - bubble_h // 2),  # lower-right
            (nx - offset_x - bubble_w // 2, ny + offset_y - bubble_h // 2),  # lower-left
        ]

        best_pos = None
        best_overlap = float('inf')

        for cx, cy in candidates:
            # Clamp to photo area bounds
            cx = max(2, min(cx, bg_w - bubble_w - 2))
            cy = max(2, min(cy, canvas_h - bubble_h - 2))
            candidate_rect = (cx, cy, cx + bubble_w, cy + bubble_h)

            # Check if bubble fits within photo area
            fits_edge = (cx >= 0 and cy >= 0 and cx + bubble_w <= bg_w and cy + bubble_h <= canvas_h)

            # Calculate total overlap with already-placed bubbles
            total_overlap = 0
            for pb in placed_bubbles:
                # AABB intersection area
                ox1 = max(candidate_rect[0], pb[0])
                oy1 = max(candidate_rect[1], pb[1])
                ox2 = min(candidate_rect[2], pb[2])
                oy2 = min(candidate_rect[3], pb[3])
                if ox1 < ox2 and oy1 < oy2:
                    total_overlap += (ox2 - ox1) * (oy2 - oy1)

            if fits_edge and total_overlap == 0:
                best_pos = (cx, cy)
                break
            elif total_overlap < best_overlap:
                best_overlap = total_overlap
                best_pos = (cx, cy)

        if best_pos is None:
            best_pos = (candidates[0][0], candidates[0][1])

        lx, ly = best_pos[0] + bubble_w // 2, best_pos[1] + bubble_h // 2
        rx1, ry1 = best_pos
        rx2, ry2 = rx1 + bubble_w, ry1 + bubble_h

        # Track this bubble for future collision checks
        placed_bubbles.append((rx1, ry1, rx2, ry2))

        # Draw connection line from node dot to bubble center
        draw.line([(nx, ny), (lx, ly)], fill=border_color, width=3)

        # Draw node dot and bubble endpoint dot
        draw.ellipse([nx - 6, ny - 6, nx + 6, ny + 6], fill=border_color)
        draw.ellipse([lx - 4, ly - 4, lx + 4, ly + 4], fill=border_color)

        # Draw rounded rectangle bubble
        draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=12, outline=border_color, width=3, fill='#000000')

        # Draw centered text inside bubble
        text_x = rx1 + (bubble_w - text_w) // 2
        text_y = ry1 + (bubble_h - text_h) // 2
        draw.text((text_x, text_y), label_text, fill='#FFFFFF', font=font_bubble)

    # Draw Engineer's Note Box centered in the sidebar
    note_w, note_h = 220, 250
    nx1 = bg_w + (sidebar_w - note_w) // 2
    ny1 = canvas_h - note_h - 15
    nx2, ny2 = nx1 + note_w, ny1 + note_h

    draw.rectangle([nx1, ny1, nx2, ny2], fill='#FFFFFF', outline='#000000', width=4)
    draw.text((nx1 + 10, ny1 + 10), "ENGINEER'S NOTE:\n-----------------------------", fill='#000000', font=font_note)
    
    # Wrap note text manually
    words = engineer_note.split()
    lines = []
    current_line = []
    for word in words:
        if len(" ".join(current_line + [word])) * 8 > (note_w - 20):
            lines.append(" ".join(current_line))
            current_line = [word]
        else:
            current_line.append(word)
    if current_line:
        lines.append(" ".join(current_line))
        
    line_y = ny1 + 40
    for line in lines[:10]: # Cap at 10 lines
        draw.text((nx1 + 10, line_y), line, fill='#000000', font=font_small)
        line_y += 18

    # Draw placed images at their coordinates
    if image_placements and images_dir:
        for placement in image_placements:
            try:
                image_name = placement.get('image_name')
                x_pct = placement.get('x', 0)
                y_pct = placement.get('y', 0)

                image_path = os.path.join(images_dir, image_name)
                if os.path.exists(image_path):
                    with Image.open(image_path) as img_src:
                        img_overlay = img_src.convert("RGBA")
                        # Scale image to reasonable size (max 100px on largest dimension)
                        max_size = 100
                        img_overlay.thumbnail((max_size, max_size), Image.LANCZOS)

                        # Convert percentages to actual pixel coordinates
                        img_x = int((x_pct / 100.0) * bg_w) - (img_overlay.width // 2)
                        img_y = int((y_pct / 100.0) * canvas_h) - (img_overlay.height // 2)

                        # Ensure image stays within bounds
                        img_x = max(0, min(img_x, bg_w - img_overlay.width))
                        img_y = max(0, min(img_y, canvas_h - img_overlay.height))

                        canvas.paste(img_overlay, (img_x, img_y), img_overlay)
            except Exception as e:
                print(f"Error placing image {placement.get('image_name')}: {e}")

    # Add overlay image in bottom-right corner if provided
    if overlay_image_path and os.path.exists(overlay_image_path):
        try:
            with Image.open(overlay_image_path) as overlay_src:
                overlay = overlay_src.convert("RGBA")
                # Scale overlay to reasonable size (max 120px on largest dimension)
                max_size = 120
                overlay.thumbnail((max_size, max_size), Image.LANCZOS)

                # Position in bottom-right corner with padding
                padding = 15
                overlay_x = canvas_w - overlay.width - padding
                overlay_y = canvas_h - overlay.height - padding

                # Paste with alpha transparency
                canvas.paste(overlay, (overlay_x, overlay_y), overlay)
        except Exception as e:
            print(f"Error adding overlay image: {e}")

    canvas.save(output_path)
    return output_path

def add_styled_table(doc, data, headers):
    """
    Construct a clean, well-padded Table styled matching LANSING_PD_Site_Survey.
    Supports 2 or 3 columns depending on len(headers).
    """
    ncols = len(headers)
    table = doc.add_table(rows=len(data) + 1, cols=ncols)
    table.style = 'Table Grid'

    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h

    for i in range(ncols):
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, row in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        for c_idx, cell_val in enumerate(row):
            row_cells[c_idx].text = str(cell_val)
        row_cells[0].paragraphs[0].runs[0].font.bold = True

    doc.add_paragraph()

def generate_word_report(site_data_list, output_filepath, customer_info=None, drive_manager=None, drive_reports_folder_id=None):
    """
    Generate the Site Survey Word Document.
    site_data_list items contain pre-populated 'agency_name' field from processor.

    If drive_manager and drive_reports_folder_id are provided, the report
    will also be uploaded to Google Drive.
    """
    doc = Document()

    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(10)

    if not customer_info:
        customer_info = {
            "agency_name": "",
            "agency_address": "",
            "poc_name": "",
            "poc_email": "",
            "poc_phone": "",
            "it_director": "",
            "it_email": "",
            "facilities_engineer": "",
            "facilities_email": "",
            "report_date": datetime.date.today().strftime("%B %d, %Y"),
        }
    report_date = customer_info.get("report_date", datetime.date.today().strftime("%B %d, %Y"))
        
    p_title = doc.add_paragraph()
    p_title.alignment = 1
    title_run = p_title.add_run("DFR SITE SURVEY REPORT")
    title_run.bold = True
    title_run.font.size = Pt(24)
    title_run.font.color.rgb = RGBColor(0, 48, 96)
    
    p_agency = doc.add_paragraph()
    p_agency.alignment = 1
    agency_run = p_agency.add_run(f"Agency: {customer_info.get('agency_name')}\nDate: {report_date}")
    agency_run.font.size = Pt(14)
    agency_run.font.color.rgb = RGBColor(100, 100, 100)
    
    # 1. Map Visualisation Section
    doc.add_paragraph().add_run("Site Detail & Map Visualisation").bold = True
    map_image_path = os.path.join(os.path.dirname(output_filepath), "dfr_site_map.png")
    draw_styled_map(site_data_list, map_image_path)
    if os.path.exists(map_image_path):
        doc.add_picture(map_image_path, width=Inches(6.0))
        doc.add_paragraph()
        
    # 2. General Contact Information Table
    h_general = doc.add_paragraph()
    h_general.add_run("GENERAL CONTACT INFORMATION").bold = True
    h_general.runs[0].font.size = Pt(12)
    
    contact_data = [
        ("Agency Name & Address", f"{customer_info.get('agency_name')}\n{customer_info.get('agency_address')}"),
        ("Point of Contact (POC)", f"{customer_info.get('poc_name')} | {customer_info.get('poc_email')} | {customer_info.get('poc_phone')}"),
        ("Information Technology (IT)", f"{customer_info.get('it_director')} | {customer_info.get('it_email')}"),
        ("Facilities Engineer", f"{customer_info.get('facilities_engineer')} | {customer_info.get('facilities_email')}")
    ]
    add_styled_table(doc, contact_data, ["CONTACT INFORMATION", "NOTES / VALUE"])
    
    # 3. Installation Timeframe
    timeframe_data = [
        ("Survey / Delivery Target", "Week of June 9, 2026"),
        ("Follow up requirements", "Infrastructure checklist completion prior to hardware delivery"),
        ("Action items", "Confirm ethernet and dedicated 120V power connectivity is established 30 days before installation.")
    ]
    add_styled_table(doc, timeframe_data, ["INSTALLATION TIMEFRAME", "NOTES / VALUE"])
    
    doc.add_page_break()
    
    # 4. Loop through individual site nodes
    for idx, site in enumerate(site_data_list):
        site_name = site['address'].split(',')[0]
        analysis = site.get('analysis', {})
        # Note: Each site includes pre-populated 'agency_name' and 'city' fields from processor
        site_agency = site.get('agency_name', 'Police Department')
        
        h_site = doc.add_paragraph()
        h_site_run = h_site.add_run(f"Location #{idx+1}/{len(site_data_list)} - {site_name.upper()}")
        h_site_run.bold = True
        h_site_run.font.size = Pt(14)
        h_site_run.font.color.rgb = RGBColor(0, 48, 96)
        
        # If engineering layout has been generated for this site, embed it
        eng_drawing_path = os.path.join(site.get('folder_path', '.'), "engineering_layout.png")
        if os.path.exists(eng_drawing_path):
            doc.add_paragraph().add_run("Engineering Layout Drawing").bold = True
            try:
                doc.add_picture(eng_drawing_path, width=Inches(6.0))
            except Exception as e:
                doc.add_paragraph(f"[Error embedding engineering drawing: {e}]")
            doc.add_paragraph()

        # Site Details
        details_data = [
            ("Site Name", site_name),
            ("Site Address", _format_short_address(site['address'])),
            ("Height of building", "2-story (Assessment required)"),
            ("Access to roof", analysis.get('roof_access', 'Unknown')),
            ("Roof type", analysis.get('roof_type', 'Unknown'))
        ]
        add_styled_table(doc, details_data, ["SITE DETAILS", "NOTES / VALUE"])
        
        # Considerations & Airspace
        considerations_data = [
            ("Operational Considerations", "Coordinate install with local facilities team. Clear line of sight required."),
            ("Airspace Class", site.get('airspace', 'Class G')),
            ("Distance to nearest airfield", site.get('airfield_info', 'Unknown'))
        ]
        add_styled_table(doc, considerations_data, ["OPERATIONAL & AIRSPACE", "NOTES / VALUE"])
        
        # Deployment Requirements
        deployment_data = [
            ("Location (Lat/Long)", f"{site['latitude']:.6f}, {site['longitude']:.6f}"),
            ("Mount Placement Type", "Rooftop / Parapet Mount preferred" if "hatch" in str(analysis).lower() else "Ground Sled / Ballasted"),
            ("Raised Platform required (Snow)", "Yes" if "TPO" in str(analysis) or "EPDM" in str(analysis) else "No"),
            ("Emergency Landing Zone", "Yes (Debris-free zone verified)"),
            ("Power Circuit Requirements", "120V / 15A Dedicated Circuit, Outdoor Rated"),
            ("Internet / Ethernet Access", "DHCP on isolated VLAN (unrestricted outbound)")
        ]
        add_styled_table(doc, deployment_data, ["DEPLOYMENT SPECIFICATIONS", "NOTES / VALUE"])
        
        # Add ONLY selected images
        selected_images = [img for img in site.get('images', []) if img.get('selected_for_report', True)]
        if selected_images:
            p_photos = doc.add_paragraph()
            p_photos.add_run("Survey Photos & Visual Evidence").bold = True
            for img in selected_images:
                img_path = img.get('dest_path') or img.get('path')
                if os.path.exists(img_path):
                    doc.add_paragraph(f"Photo: {img.get('filename')}")
                    try:
                        doc.add_picture(img_path, width=Inches(3.5))
                    except Exception as e:
                        doc.add_paragraph(f"[Unable to embed photo: {e}]")
                    doc.add_paragraph()
                    
        doc.add_page_break()
        
    doc.save(output_filepath)

    # If using Google Drive, upload report
    if drive_manager and drive_reports_folder_id:
        try:
            report_filename = os.path.basename(output_filepath)
            drive_manager.upload_file(
                output_filepath,
                drive_reports_folder_id,
                file_name=report_filename
            )
        except Exception as e:
            print(f"Failed to upload report to Google Drive: {e}")

    return output_filepath


def _yn(value):
    """Convert bool/None to Yes/No/— string."""
    if value is True:
        return "Yes"
    elif value is False:
        return "No"
    return "—"


def generate_candidate_site_report(candidate_sites, output_filepath,
                                    customer_info=None, drive_manager=None,
                                    drive_reports_folder_id=None):
    """Generate a dynamic DOCX report from CandidateSite objects.

    Report structure:
    1. Executive Summary
    2. Candidate Site sections (1-N, dynamic)
    3. Installer Quick Reference (1 page per site)
    4. Annotated Photo Appendix
    """
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Calibri"
    font.size = Pt(10)

    # ── 1. Executive Summary ──
    title = doc.add_heading("DFR SITE SURVEY REPORT", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    agency = ""
    survey_date = ""
    surveyor = ""
    if candidate_sites:
        agency = candidate_sites[0].identity.agency_name
        survey_date = candidate_sites[0].identity.survey_date or ""
        surveyor = candidate_sites[0].identity.surveyor or ""
    if customer_info:
        agency = customer_info.get("agency_name", agency)

    doc.add_paragraph(f"Agency: {agency}")
    doc.add_paragraph(f"Survey Date: {survey_date}")
    doc.add_paragraph(f"Surveyor: {surveyor}")
    doc.add_paragraph(f"Candidate Sites Found: {len(candidate_sites)}")
    doc.add_page_break()

    # ── 2. Candidate Site Sections ──
    for idx, site in enumerate(candidate_sites, start=1):
        doc.add_heading(f"Candidate Site {idx}: {site.identity.site_name}", level=1)

        # 2a. Site Overview
        doc.add_heading("Site Overview", level=2)
        overview_data = [
            ["Site ID", site.identity.site_id],
            ["Address", site.identity.site_address],
            ["Latitude", str(site.identity.site_latitude)],
            ["Longitude", str(site.identity.site_longitude)],
            ["Elevation", f"{site.identity.site_elevation} ft" if site.identity.site_elevation else "—"],
            ["Building Height", f"{site.structure.building_height} ft" if site.structure.building_height else "—"],
            ["Roof Type", site.structure.roof_type or "—"],
        ]
        add_styled_table(doc, overview_data, ["Field", "Value"])

        # 2b. Site Photos by Category
        doc.add_heading("Site Photos", level=2)
        for cat in ["Site", "Installation", "Infrastructure", "RF", "Access"]:
            cat_photos = [p for p in site.photos if p.category == cat and p.selected_for_report]
            if not cat_photos:
                continue
            doc.add_heading(f"{cat} Photos", level=3)
            for photo in cat_photos:
                if os.path.exists(photo.file_path):
                    try:
                        doc.add_picture(photo.file_path, width=Inches(5.0))
                    except Exception:
                        doc.add_paragraph(f"[Photo: {photo.photo_id}]")
                else:
                    doc.add_paragraph(f"[Photo: {photo.photo_id}]")

        # 2c. Checklist Summary
        doc.add_heading("Checklist Summary", level=2)
        summary_rows = []
        field_labels = {
            "ACCESS_TYPE": "Access Type", "ROOF_ACCESS": "Roof Access",
            "ESCORT_REQUIRED": "Escort Required", "KEY_REQUIRED": "Key Required",
            "BUILDING_HEIGHT": "Building Height", "ROOF_TYPE": "Roof Type",
            "PARAPET_HEIGHT": "Parapet Height", "ROOF_CONDITION": "Roof Condition",
            "POWER_AVAILABLE": "Power Available", "VOLTAGE_AVAILABLE": "Voltage",
            "DEDICATED_CIRCUIT": "Dedicated Circuit", "PANEL_LOCATION": "Panel Location",
            "ISP_PROVIDER": "ISP Provider", "DOWNLOAD_SPEED": "Download Speed",
            "UPLOAD_SPEED": "Upload Speed", "STATIC_IP_AVAILABLE": "Static IP",
            "LINE_OF_SIGHT_STATUS": "Line of Sight", "COVERAGE_DIRECTION": "Coverage Direction",
            "AIRSPACE_CLASS": "Airspace Class", "SITE_ELEVATION": "Elevation",
            "COUNTY_NAME": "County", "STATE_NAME": "State", "ZIP_CODE": "ZIP Code",
        }
        all_fields = site.to_csv_row()
        for field_id, label in field_labels.items():
            value = all_fields.get(field_id)
            if value is not None and value != "" and str(value) != "None":
                source = site.checklist_provenance.get(field_id, "pm")
                summary_rows.append([label, str(value), "Auto" if source == "auto" else "Manual"])
        if summary_rows:
            add_styled_table(doc, summary_rows, ["Field", "Value", "Source"])
        else:
            doc.add_paragraph("No checklist fields have been filled.")

        # 2d. Access
        doc.add_heading("Access", level=3)
        add_styled_table(doc, [
            ["Access Type", site.access.access_type or "—"],
            ["Roof Access", site.access.roof_access or "—"],
            ["Escort Required", _yn(site.access.escort_required)],
            ["Key Required", _yn(site.access.key_required)],
            ["After Hours Access", _yn(site.access.after_hours_access)],
            ["Parking Available", _yn(site.access.parking_available)],
        ], ["Field", "Value"])

        # 2e. Electrical Assessment
        doc.add_heading("Electrical Assessment", level=3)
        add_styled_table(doc, [
            ["Power Available", _yn(site.electrical.power_available)],
            ["Voltage", site.electrical.voltage_available or "—"],
            ["Breaker Available", _yn(site.electrical.breaker_available)],
            ["Dedicated Circuit", _yn(site.electrical.dedicated_circuit)],
            ["Panel Location", site.electrical.panel_location or "—"],
            ["Distance to Power", f"{site.electrical.distance_to_power} ft" if site.electrical.distance_to_power else "—"],
        ], ["Field", "Value"])

        # 2f. Network Assessment
        doc.add_heading("Network Assessment", level=3)
        add_styled_table(doc, [
            ["ISP Provider", site.network.isp_provider or "—"],
            ["Connection Type", site.network.connection_type or "—"],
            ["Download Speed", site.network.download_speed or "—"],
            ["Upload Speed", site.network.upload_speed or "—"],
            ["Static IP", _yn(site.network.static_ip_available)],
            ["Switch Location", site.network.switch_location or "—"],
            ["Distance to Network", f"{site.network.distance_to_network} ft" if site.network.distance_to_network else "—"],
        ], ["Field", "Value"])

        # 2g. RF Assessment
        doc.add_heading("RF Assessment", level=3)
        add_styled_table(doc, [
            ["Line of Sight", site.rf.line_of_sight_status or "—"],
            ["Obstructions - Trees", _yn(site.rf.obstruction_trees)],
            ["Obstructions - Buildings", _yn(site.rf.obstruction_buildings)],
            ["Obstructions - Water Towers", _yn(site.rf.obstruction_water_towers)],
            ["Obstructions - Cell Towers", _yn(site.rf.obstruction_cell_towers)],
            ["Coverage Direction", site.rf.coverage_direction or "—"],
        ], ["Field", "Value"])

        # 2h. Airspace Assessment
        doc.add_heading("Airspace Assessment", level=3)
        add_styled_table(doc, [
            ["Airspace Class", site.flight.airspace_class or "—"],
            ["Nearby Airports", site.flight.nearby_airports or "—"],
            ["Nearby Heliports", site.flight.nearby_heliports or "—"],
            ["Flight Restrictions", site.flight.flight_restrictions or "—"],
        ], ["Field", "Value"])

        doc.add_page_break()

    # ── 3. Installer Quick Reference ──
    doc.add_heading("Installer Quick Reference", level=1)
    for idx, site in enumerate(candidate_sites, start=1):
        doc.add_heading(f"Site {idx}: {site.identity.site_name}", level=2)
        add_styled_table(doc, [
            ["Address", site.identity.site_address],
            ["Access Method", site.access.roof_access or site.access.access_type or "—"],
            ["Power Location", site.electrical.panel_location or "—"],
            ["Network Location", site.network.switch_location or "—"],
            ["Antenna Location", f"{site.rf.antenna_latitude}, {site.rf.antenna_longitude}" if site.rf.antenna_latitude else "—"],
            ["Escort Required", _yn(site.access.escort_required)],
        ], ["Item", "Details"])
        if customer_info:
            poc = customer_info.get("poc_name", "")
            phone = customer_info.get("poc_phone", "")
            if poc:
                doc.add_paragraph(f"Site Contact: {poc}  {phone}")
        doc.add_page_break()

    # ── 4. Annotated Photo Appendix ──
    doc.add_heading("Annotated Photo Appendix", level=1)
    has_annotations = False
    for idx, site in enumerate(candidate_sites, start=1):
        folder = site.folder_path
        if folder and os.path.isdir(folder):
            for fname in sorted(os.listdir(folder)):
                if fname.startswith("engineering_layout") and fname.endswith(".png"):
                    img_path = os.path.join(folder, fname)
                    doc.add_heading(f"Site {idx}: {site.identity.site_name}", level=3)
                    try:
                        doc.add_picture(img_path, width=Inches(6.0))
                        has_annotations = True
                    except Exception:
                        doc.add_paragraph(f"[Annotation: {fname}]")
    if not has_annotations:
        doc.add_paragraph("No annotated engineering layouts available.")

    doc.save(output_filepath)

    if drive_manager and drive_reports_folder_id:
        try:
            drive_manager.upload_file(output_filepath, drive_reports_folder_id)
        except Exception:
            pass

    return output_filepath
