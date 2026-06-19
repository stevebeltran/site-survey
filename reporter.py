import os
import datetime
import requests
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from geopy.distance import geodesic
from PIL import Image, ImageDraw, ImageFont

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
    try:
        font_bubble = ImageFont.truetype("arialbd.ttf", 28)
        font_legend = ImageFont.truetype("arialbd.ttf", 26)
        font_title = ImageFont.truetype("arialbd.ttf", 22)
        font_small = ImageFont.truetype("arial.ttf", 14)
        font_note = ImageFont.truetype("arial.ttf", 16)
    except:
        font_bubble = None
        font_legend = None
        font_title = None
        font_small = None
        font_note = None

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
        addr_text = str(address).strip()
        addr_bbox = draw.textbbox((0, 0), addr_text, font=font_title)
        addr_width = addr_bbox[2] - addr_bbox[0]
        addr_height = addr_bbox[3] - addr_bbox[1]

        # Position at top center of photo area
        addr_x = (bg_w - addr_width) // 2
        addr_y = 10

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
    for m in markers:
        # Convert percent to actual pixel coords
        nx = int((m['node_x'] / 100.0) * bg_w)
        ny = int((m['node_y'] / 100.0) * canvas_h)
        lx = int((m['label_x'] / 100.0) * bg_w)
        ly = int((m['label_y'] / 100.0) * canvas_h)
        
        m_type = m.get('type', 'Electric')
        label_text = m.get('label', '')
        
        # Select color matching type
        border_color = '#EF4444' # Default Red (Electric)
        if m_type == 'Data':
            border_color = '#F97316' # Orange
        elif m_type == 'RF':
            border_color = '#A855F7' # Purple
        elif m_type == 'Unistrut':
            border_color = '#94A3B8'
        elif m_type == 'Lift':
            border_color = '#EAB308'
            
        # Draw connection line from Node to Callout Label
        # Draw a path with intermediate node circles if specified
        draw.line([(nx, ny), (lx, ly)], fill=border_color, width=3)
        
        # Draw small circles at the connection endpoints
        draw.ellipse([nx-6, ny-6, nx+6, ny+6], fill=border_color)
        draw.ellipse([lx-4, ly-4, lx+4, ly+4], fill=border_color)
        
        # Calculate text bounding box to wrap in rounded rectangle
        # Roughly calculate text size
        text_w = len(label_text) * 11
        text_h = 24
        
        pad_x, pad_y = 12, 12
        rx1, ry1 = lx - text_w // 2 - pad_x, ly - text_h // 2 - pad_y
        rx2, ry2 = lx + text_w // 2 + pad_x, ly + text_h // 2 + pad_y
        
        # Draw Rounded Rect for text
        draw.rounded_rectangle([rx1, ry1, rx2, ry2], radius=12, outline=border_color, width=3, fill='#000000')
        
        # Draw Text
        draw.text((rx1 + pad_x, ry1 + pad_y - 2), label_text, fill='#FFFFFF', font=font_bubble)

    # Draw Engineer's Note Box in the Bottom Right
    note_w, note_h = 240, 250
    nx1, ny1 = canvas_w - note_w - 15, canvas_h - note_h - 15
    nx2, ny2 = canvas_w - 15, canvas_h - 15

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
    Construct a clean, well-padded Table styled matching LANSING_PD_Site_Survey
    """
    table = doc.add_table(rows=len(data) + 1, cols=2)
    table.style = 'Table Grid'
    
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = headers[0]
    hdr_cells[1].text = headers[1]
    
    for i in range(2):
        hdr_cells[i].paragraphs[0].runs[0].font.bold = True
        hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = RGBColor(255, 255, 255)
        
    for r_idx, (key, val) in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        row_cells[0].text = str(key)
        row_cells[1].text = str(val)
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
            ("Site Address", site['address']),
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
