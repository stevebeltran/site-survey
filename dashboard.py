import os
import json
import tempfile
import streamlit as st
import pandas as pd
from PIL import Image
import datetime
from google_drive import get_drive_manager
from gmail_lookup import search_gmail_for_contacts
import google_oauth

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except Exception:
    pillow_heif = None

# Clean working directory from any enclosing quotes on Windows
current_cwd = os.getcwd()
if '"' in current_cwd or "'" in current_cwd:
    os.chdir(current_cwd.replace('"', '').replace("'", ""))

# Import our modules
import processor
import analyzer
import reporter

# Import the image coordinates package
try:
    from streamlit_image_coordinates import streamlit_image_coordinates
except ImportError:
    st.error("Please ensure streamlit-image-coordinates is installed.")

# Page config
st.set_page_config(
    page_title="DFR Site Survey & Deployment Suite",
    page_icon="🚁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Handle OAuth callback before any other UI
google_oauth.handle_callback()

# Premium Theme Styling via Custom CSS
st.markdown("""
<style>
    .reportview-container {
        background: #0F172A;
        color: #F8FAFC;
    }
    .main-header {
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%);
        padding: 10px 20px;
        border-radius: 10px;
        color: white;
        margin-bottom: 15px;
        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.15);
        display: flex;
        align-items: center;
        gap: 16px;
    }
    .main-header img {
        height: 38px;
        width: auto;
    }
    .main-header .header-text h1 {
        margin: 0;
        font-size: 1.4rem;
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        letter-spacing: -0.5px;
    }
    .main-header .header-text p {
        margin: 2px 0 0 0;
        opacity: 0.9;
        font-size: 0.85rem;
    }
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if "processed_sites" not in st.session_state:
    st.session_state.processed_sites = []
if "integration_logs" not in st.session_state:
    st.session_state.integration_logs = []
if "last_click" not in st.session_state:
    st.session_state.last_click = {}
if "customer_info" not in st.session_state:
    # Initialized as entirely blank on first load
    st.session_state.customer_info = {
        "agency_name": "",
        "agency_address": "",
        "poc_name": "",
        "poc_email": "",
        "poc_phone": "",
        "it_director": "",
        "it_email": "",
        "facilities_engineer": "",
        "facilities_email": ""
    }
if "active_bg_image" not in st.session_state:
    st.session_state.active_bg_image = None
if "client_folder_id" not in st.session_state:
    st.session_state.client_folder_id = None
if "raw_images_folder_id" not in st.session_state:
    st.session_state.raw_images_folder_id = None
if "processed_folder_id" not in st.session_state:
    st.session_state.processed_folder_id = None
if "reports_folder_id" not in st.session_state:
    st.session_state.reports_folder_id = None
if "metadata_folder_id" not in st.session_state:
    st.session_state.metadata_folder_id = None
if "client_name" not in st.session_state:
    st.session_state.client_name = None
if "image_paths" not in st.session_state:
    st.session_state.image_paths = []

SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tiff", ".webp", ".heic", ".heif")
APP_DIR = os.path.dirname(os.path.abspath(__file__))

def _resolve_app_path(path):
    """Resolve relative paths against the dashboard file location."""
    cleaned_path = path.strip().replace('"', '').replace("'", "")
    if os.path.isabs(cleaned_path):
        return os.path.abspath(cleaned_path)
    return os.path.abspath(os.path.join(APP_DIR, cleaned_path))


def _extract_town_state_from_address(address):
    """Infer town and state from a reverse-geocoded address string."""
    parts = [part.strip() for part in str(address).split(",") if part.strip()]
    if not parts:
        return "Local", "State"

    town = parts[1] if len(parts) >= 4 else parts[0]
    if any(token in town.lower() for token in ("county", "united states", "usa")):
        town = parts[0]

    state = "State"
    if len(parts) >= 2:
        candidate = parts[-2].split()[0]
        if candidate and not any(token in candidate.lower() for token in ("county", "united states", "usa")):
            state = candidate

    return town or "Local", state or "State"

def _save_session_metadata(site_data):
    """Save metadata to a JSON file inside each site's folder."""
    for site in site_data:
        # Save customer info into the site payload for history loading
        site["customer_info"] = st.session_state.customer_info
        folder_path = site.get("folder_path")
        if folder_path and os.path.exists(folder_path):
            metadata_path = os.path.join(folder_path, "session_metadata.json")
            try:
                # Convert datetime objects to string representation
                serializable_site = json.loads(json.dumps(site, default=str))
                with open(metadata_path, "w") as f:
                    json.dump(serializable_site, f, indent=4)
            except Exception as e:
                print(f"Error saving session metadata: {e}")


def _get_displayable_image_path(image_path):
    """Return a browser-safe image path for Streamlit display, or None if unreadable."""
    if not image_path or not os.path.exists(image_path):
        return None

    safe_extensions = (".jpg", ".jpeg", ".png", ".webp")
    ext = os.path.splitext(image_path)[1].lower()

    try:
        with Image.open(image_path) as img:
            img.load()
            if ext in safe_extensions:
                return image_path

            preview_dir = os.path.join(os.path.dirname(image_path), ".previews")
            os.makedirs(preview_dir, exist_ok=True)
            preview_name = f"{os.path.splitext(os.path.basename(image_path))[0]}.png"
            preview_path = os.path.join(preview_dir, preview_name)
            if not os.path.exists(preview_path):
                img.convert("RGB").save(preview_path, "PNG")
            return preview_path
    except Exception as e:
        print(f"Image preview unavailable for {image_path}: {e}")
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _detect_agency_from_gps(first_file_bytes, first_file_name):
    """Extract GPS from the first uploaded image, reverse geocode, and derive agency info."""
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(first_file_name)[1])
        tmp.write(first_file_bytes)
        tmp.close()
        lat, lon, _ = processor.extract_exif_gps(tmp.name)
        os.unlink(tmp.name)
        if lat is None or lon is None:
            return None
        full_address = processor.reverse_geocode(lat, lon)
        city = processor.extract_city_from_address(full_address)
        agency_name = f"{city} Police Department" if city else None
        return {
            "lat": lat,
            "lon": lon,
            "address": full_address,
            "city": city,
            "agency_name": agency_name,
        }
    except Exception as e:
        print(f"GPS detection error: {e}")
        return None


@st.cache_data(ttl=600, show_spinner="Searching Gmail for agency contacts...")
def _lookup_contacts_from_gmail(agency_name, city=None):
    """Search Gmail and Calendar for kickoff calls / invites with this agency."""
    return search_gmail_for_contacts(agency_name, city)


# Header – compact banner with BRINC logo
import base64 as _b64

def _logo_b64():
    logo_path = os.path.join(APP_DIR, "images", "BRINC_Logo_White.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return _b64.b64encode(f.read()).decode()
    return None

_logo_data = _logo_b64()
_logo_tag = f'<img src="data:image/png;base64,{_logo_data}" />' if _logo_data else ""

_last_updated = datetime.datetime.now().strftime("%m/%d/%Y %I:%M %p")

st.markdown(f"""
<div class="main-header">
    {_logo_tag}
    <div class="header-text">
        <h1>Drone as a First Responder (DFR)</h1>
        <p>Site Survey & Deployment Automation Suite</p>
    </div>
    <div style="margin-left:auto; text-align:right; font-size:0.75rem; opacity:0.7;">
        Last updated<br>{_last_updated}
    </div>
</div>
""", unsafe_allow_html=True)

# Sidebar - Settings & Integration Configs
with st.sidebar:
    st.image(os.path.join(APP_DIR, "images", "BRINC_Logo_White.png"), width=160)
    st.title("Settings & APIs")
    
    st.subheader("1. Survey Settings")
    output_dir = "./processed_sites"
    proximity_radius = st.slider("Clustering Proximity (Meters)", min_value=10, max_value=500, value=90)
    
    st.subheader("2. Integrations & Credentials")
    with st.expander("API Configurations"):
        hubspot_api = st.text_input("HubSpot Access Token", type="password")
        jira_url = st.text_input("Jira Server URL", value="https://jira.dfr-deployments.atlassian.net")
        slack_webhook = st.text_input("Slack Webhook URL", type="password")
        gdrive_folder = st.text_input("Google Drive Folder ID")
        
    st.info("💡 Mocks are enabled automatically for unset credentials.")

    st.divider()
    st.subheader("Google Account")
    user_email = google_oauth.get_user_email()
    if user_email:
        st.success(f"Signed in as {user_email}")
        if st.button("Sign Out", use_container_width=True):
            st.session_state.pop("google_oauth_token", None)
            st.session_state.pop("google_oauth_email", None)
            google_oauth._delete_token_file()
            st.rerun()
    else:
        google_oauth.render_connect_button()

# Ingestion Controls
# Get Drive manager once up front (returns None if not authenticated)
drive = get_drive_manager()
team_folder_id = st.secrets.get('GOOGLE_DRIVE_TEAM_FOLDER_ID', None)

def _on_files_changed():
    """Reset GPS detection and processing flag when the user changes files."""
    st.session_state.pop("gps_detected_agency", None)
    st.session_state.pop("_auto_processed", None)

# Collapse the uploader once sites have been processed
_has_sites = bool(st.session_state.get("processed_sites"))
with st.expander("📤 Upload Survey Photos", expanded=not _has_sites):
    uploaded_files = st.file_uploader(
        "Upload raw survey photos (.jpg, .jpeg, .png)",
        accept_multiple_files=True,
        type=["jpg", "jpeg", "png", "heic"],
        on_change=_on_files_changed,
        label_visibility="collapsed",
    )

    if uploaded_files:
        # Auto-detect agency from GPS
        if "gps_detected_agency" not in st.session_state:
            with st.spinner("Detecting location from photo GPS data..."):
                for uf in uploaded_files:
                    detection = _detect_agency_from_gps(uf.getvalue(), uf.name)
                    if detection and detection.get("agency_name"):
                        st.session_state.gps_detected_agency = detection
                        agency = detection["agency_name"]
                        st.session_state.customer_info["agency_name"] = agency
                        st.session_state.customer_info["agency_address"] = detection.get("address", "")
                        contacts = _lookup_contacts_from_gmail(agency, detection.get("city", ""))
                        if contacts:
                            if contacts.get("status") == "connected":
                                for key in ("poc_name", "poc_email", "it_director", "it_email"):
                                    if contacts.get(key):
                                        st.session_state.customer_info[key] = contacts[key]
                                found = contacts.get("all_contacts", [])
                                if found:
                                    st.session_state["gmail_found_contacts"] = found
                            elif contacts.get("status") == "auth_error":
                                st.session_state["gmail_auth_error"] = contacts.get("error", "")
                        break
                else:
                    st.session_state.gps_detected_agency = {}

        suggested_name = st.session_state.get("gps_detected_agency", {}).get("agency_name", "")
        client_name = st.text_input(
            "Client/Agency Name",
            value=suggested_name or "Untitled_Site_Survey",
        )
        if suggested_name:
            st.caption(f"Auto-detected from GPS: {st.session_state['gps_detected_agency'].get('address', '')}")
        if st.session_state.pop("gmail_auth_error", None):
            if google_oauth.is_authenticated():
                st.warning("Could not search Gmail for contacts. Use the 'Pull Contacts from Gmail' button below to retry.")
            else:
                st.warning("Connect your Google account to search Gmail for contacts.")

        # Upload to Drive button (remains manual)
        col_drive_btn, col_spacer = st.columns([1, 2])
        with col_drive_btn:
            if google_oauth.is_authenticated():
                upload_clicked = st.button("📤 Upload to Drive", use_container_width=True)
            else:
                upload_clicked = False
                google_oauth.render_connect_button("Connect Google to Upload")
    else:
        client_name = "Untitled_Site_Survey"
        upload_clicked = False

# Handle Upload to Drive button
uploaded_file_paths = []
if upload_clicked and uploaded_files:
    if not drive:
        st.error("Google Drive not available. Please connect your Google account.")
        st.stop()
    if not team_folder_id:
        st.error("GOOGLE_DRIVE_TEAM_FOLDER_ID not set in Streamlit secrets.")
        st.stop()

    with st.spinner("Creating folder structure and uploading images..."):
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            client_folder_name = f"{client_name}_{timestamp}"
            client_folder_id = drive.get_or_create_folder(team_folder_id, client_folder_name)

            raw_images_folder_id = drive.get_or_create_folder(client_folder_id, "01_Raw_Images")
            processed_folder_id = drive.get_or_create_folder(client_folder_id, "02_Processed_Sites")
            reports_folder_id = drive.get_or_create_folder(client_folder_id, "03_Reports")
            metadata_folder_id = drive.get_or_create_folder(client_folder_id, "04_Metadata")

            progress_bar = st.progress(0)
            for idx, uploaded_file in enumerate(uploaded_files):
                temp_path = f"/tmp/{uploaded_file.name}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                drive.upload_file(temp_path, raw_images_folder_id)
                uploaded_file_paths.append(temp_path)
                progress_bar.progress((idx + 1) / len(uploaded_files))

            st.success(f"Uploaded {len(uploaded_files)} images to Google Drive!")
            st.session_state.client_folder_id = client_folder_id
            st.session_state.raw_images_folder_id = raw_images_folder_id
            st.session_state.processed_folder_id = processed_folder_id
            st.session_state.reports_folder_id = reports_folder_id
            st.session_state.metadata_folder_id = metadata_folder_id
            st.session_state.client_name = client_name
            st.session_state.image_paths = uploaded_file_paths

        except Exception as e:
            st.error(f"Failed to upload to Google Drive: {e}")

# Auto-process on upload — runs once per file set, no manual button needed
if uploaded_files and not st.session_state.get("_auto_processed"):
    st.session_state._auto_processed = True

    progress_bar = st.progress(0)
    progress_text = st.empty()

    def _update_processing_progress(percent, message):
        progress_bar.progress(max(0, min(100, int(percent))))
        progress_text.caption(f"{int(percent)}% - {message}")

    try:
        st.session_state.processed_sites = []
        st.session_state.active_bg_image = None
        st.session_state.last_click = {}

        # Save uploaded files to disk so the processor can read them
        temp_dir = tempfile.mkdtemp(prefix="dfr_ingest_")
        image_paths_for_processing = []
        for uploaded_file in uploaded_files:
            temp_path = os.path.join(temp_dir, uploaded_file.name)
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            image_paths_for_processing.append(temp_path)
        st.session_state.image_paths = image_paths_for_processing

        # Get Drive manager for processing pipeline
        proc_drive = None
        try:
            proc_drive = get_drive_manager()
        except Exception:
            pass

        site_data = processor.process_and_organize_images(
            source_dir=temp_dir,
            output_dir=output_dir,
            radius_meters=proximity_radius,
            progress_callback=_update_processing_progress,
            image_paths=image_paths_for_processing,
            drive_manager=proc_drive,
            drive_output_folder_id=st.session_state.get('processed_folder_id')
        )

        if not site_data:
            st.warning("No images with GPS metadata were found in the uploaded files.")

        for site in site_data:
            site["analysis"] = analyzer.analyze_site(site)
            site["airfield_info"] = f"{reporter.query_nearest_airfield(site['latitude'], site['longitude'])[0]} ({reporter.query_nearest_airfield(site['latitude'], site['longitude'])[1]:.2f} miles)"
            site["airspace"] = reporter.query_airspace_class(site["latitude"], site["longitude"])
            for img in site.get("images", []):
                if "selected_for_report" not in img:
                    img["selected_for_report"] = True

        st.session_state.processed_sites = site_data

        # Auto-populate customer info from metadata
        if site_data:
            first_site = site_data[0]
            first_address = first_site.get("address", "")
            agency_name = first_site.get("agency_name") or f"{_extract_town_state_from_address(first_address)[0]} Police Department"

            existing = st.session_state.customer_info
            st.session_state.customer_info = {
                "agency_name": agency_name,
                "agency_address": first_address,
                "poc_name": existing.get("poc_name", ""),
                "poc_email": existing.get("poc_email", ""),
                "poc_phone": existing.get("poc_phone", ""),
                "it_director": existing.get("it_director", ""),
                "it_email": existing.get("it_email", ""),
                "facilities_engineer": existing.get("facilities_engineer", ""),
                "facilities_email": existing.get("facilities_email", ""),
            }
            _save_session_metadata(site_data)

        st.rerun()
    except Exception as e:
        st.error(f"Processing failed: {e}")
    finally:
        progress_bar.empty()
        progress_text.empty()

# Layout Columns
tab1, tab2, tab3 = st.tabs(["📋 Survey Pipeline", "🔗 Workflow Sync", "📈 Analytics & Logs"])

with tab1:
    # 0. Customer Info Panel at the top
    st.subheader("Customer & Agency Information")
    col_c1, col_c2 = st.columns([2, 1])
    with col_c1:
        st.session_state.customer_info["agency_name"] = st.text_input("Agency Name", value=st.session_state.customer_info["agency_name"])
        st.session_state.customer_info["agency_address"] = st.text_input("Agency Address", value=st.session_state.customer_info["agency_address"])
    with col_c2:
        st.markdown("")  # spacer to align button with inputs
        st.markdown("")
        if google_oauth.is_authenticated():
            if st.button("🔌 Pull Contacts from Gmail", use_container_width=True):
                agency = st.session_state.customer_info.get("agency_name", "")
                if not agency:
                    st.warning("Enter or detect an Agency Name first.")
                else:
                    city = st.session_state.get("gps_detected_agency", {}).get("city", "")
                    contacts = _lookup_contacts_from_gmail(agency, city)
                    status = contacts.get("status", "no_results") if contacts else "no_results"
                    if status == "auth_error":
                        err = contacts.get("error", "")
                        st.error(f"Gmail authentication error: {err}")
                        st.session_state.integration_logs.append(f"[Gmail API] Auth error: {err}")
                    elif status == "connected":
                        # Store all found contacts for the table
                        found = contacts.get("all_contacts", [])
                        if found:
                            st.session_state["gmail_found_contacts"] = found
                        # Auto-assign best guesses
                        for key in ("poc_name", "poc_email", "it_director", "it_email"):
                            if contacts.get(key):
                                st.session_state.customer_info[key] = contacts[key]
                        st.session_state.integration_logs.append(f"[Gmail API] Found {len(found)} contacts for {agency}")
                        st.rerun()
                    else:
                        st.info(f"Connected to Gmail but no matching threads or calendar invites found for \"{agency}\".")
                        st.session_state.integration_logs.append(f"[Gmail API] Connected — no contacts found for {agency}")
        else:
            google_oauth.render_connect_button("Connect Google for Gmail Lookup")

    # --- POC / Contacts Table ---
    st.markdown("**Points of Contact**")
    # Initialize editable contacts from session state
    if "poc_rows" not in st.session_state:
        st.session_state.poc_rows = []
        # Seed from existing customer_info if present
        if st.session_state.customer_info.get("poc_name") or st.session_state.customer_info.get("poc_email"):
            st.session_state.poc_rows.append({
                "role": "POC",
                "name": st.session_state.customer_info.get("poc_name", ""),
                "email": st.session_state.customer_info.get("poc_email", ""),
                "title": "",
            })
        if st.session_state.customer_info.get("it_director") or st.session_state.customer_info.get("it_email"):
            st.session_state.poc_rows.append({
                "role": "IT",
                "name": st.session_state.customer_info.get("it_director", ""),
                "email": st.session_state.customer_info.get("it_email", ""),
                "title": "",
            })

    # Merge in any new contacts pulled from Gmail (avoid duplicates)
    gmail_contacts = st.session_state.pop("gmail_found_contacts", None)
    if gmail_contacts:
        existing_emails = {r["email"].lower() for r in st.session_state.poc_rows if r.get("email")}
        for c in gmail_contacts:
            if c["email"].lower() not in existing_emails:
                st.session_state.poc_rows.append({
                    "role": "",
                    "name": c.get("name", ""),
                    "email": c["email"],
                    "title": c.get("title", ""),
                })
                existing_emails.add(c["email"].lower())

    # Render editable rows
    role_options = ["", "POC", "IT", "Facilities", "Other"]
    rows_to_remove = []
    if st.session_state.poc_rows:
        hc1, hc2, hc3, hc4, hc5 = st.columns([1, 2, 2, 2, 0.5])
        hc1.caption("Role")
        hc2.caption("Name")
        hc3.caption("Title / Rank")
        hc4.caption("Email")
        hc5.caption("")
    for i, row in enumerate(st.session_state.poc_rows):
        rc1, rc2, rc3, rc4, rc5 = st.columns([1, 2, 2, 2, 0.5])
        with rc1:
            st.session_state.poc_rows[i]["role"] = st.selectbox(
                "Role", role_options, index=role_options.index(row["role"]) if row["role"] in role_options else 0,
                key=f"poc_role_{i}", label_visibility="collapsed",
            )
        with rc2:
            st.session_state.poc_rows[i]["name"] = st.text_input(
                "Name", value=row["name"], key=f"poc_name_{i}", label_visibility="collapsed",
                placeholder="Name",
            )
        with rc3:
            st.session_state.poc_rows[i]["title"] = st.text_input(
                "Title", value=row.get("title", ""), key=f"poc_title_{i}", label_visibility="collapsed",
                placeholder="Title / Rank",
            )
        with rc4:
            st.session_state.poc_rows[i]["email"] = st.text_input(
                "Email", value=row["email"], key=f"poc_email_{i}", label_visibility="collapsed",
                placeholder="Email",
            )
        with rc5:
            if st.button("✕", key=f"poc_del_{i}"):
                rows_to_remove.append(i)

    # Process removals
    if rows_to_remove:
        st.session_state.poc_rows = [r for idx, r in enumerate(st.session_state.poc_rows) if idx not in rows_to_remove]
        st.rerun()

    if st.button("＋ Add Contact", key="add_poc_row"):
        st.session_state.poc_rows.append({"role": "", "name": "", "email": "", "title": ""})
        st.rerun()

    # Sync the POC table back to customer_info for report generation
    # Clear first so removed/changed rows take effect
    for k in ("poc_name", "poc_email", "it_director", "it_email", "facilities_engineer", "facilities_email"):
        st.session_state.customer_info[k] = ""
    for row in st.session_state.poc_rows:
        role = row.get("role", "")
        if role == "POC" and not st.session_state.customer_info["poc_name"]:
            st.session_state.customer_info["poc_name"] = row["name"]
            st.session_state.customer_info["poc_email"] = row["email"]
        elif role == "IT" and not st.session_state.customer_info["it_director"]:
            st.session_state.customer_info["it_director"] = row["name"]
            st.session_state.customer_info["it_email"] = row["email"]
        elif role == "Facilities" and not st.session_state.customer_info["facilities_engineer"]:
            st.session_state.customer_info["facilities_engineer"] = row["name"]
            st.session_state.customer_info["facilities_email"] = row["email"]

    st.divider()

    # Three column layout: Left (Sites), Middle (Map/Markup), Right (History)
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.session_state.processed_sites:
            st.subheader("Sites Detected")
            for site in st.session_state.processed_sites:
                st.markdown(f"**{site['site_id']}: {site['address'].split(',')[0]}**")
                st.caption(f"Coordinates: {site['latitude']:.4f}, {site['longitude']:.4f}")
                st.caption(f"Airspace: `{site['airspace']}`")
                
    with col2:
        st.subheader("Site Detail & Map Visualisation")
        if st.session_state.processed_sites:
            # Show map
            map_data = pd.DataFrame([
                {"lat": s['latitude'], "lon": s['longitude'], "name": s['address'].split(',')[0]}
                for s in st.session_state.processed_sites
            ])
            st.map(map_data, zoom=12)
            
            # Show detailed card for selected site
            selected_site_idx = st.selectbox("Select Site to Inspect", range(len(st.session_state.processed_sites)), format_func=lambda idx: st.session_state.processed_sites[idx]['site_id'])
            selected_site = st.session_state.processed_sites[selected_site_idx]

            # Auto-populate agency name from batch folder name
            if selected_site.get('batch_folder_path'):
                batch_folder_name = os.path.basename(selected_site['batch_folder_path'])
                # Remove timestamp suffix (last 15 chars: YYYYMMDD_HHMMSS)
                if len(batch_folder_name) > 15:
                    # Check if last 15 chars match timestamp pattern (8 digits, underscore, 6 digits)
                    potential_timestamp = batch_folder_name[-15:]
                    if potential_timestamp[8] == '_' and potential_timestamp[:8].isdigit() and potential_timestamp[9:].isdigit():
                        agency_name = batch_folder_name[:-15].replace('_', ' ')
                    else:
                        agency_name = batch_folder_name.replace('_', ' ')
                else:
                    agency_name = batch_folder_name.replace('_', ' ')

                # Remove leading numeric prefixes (e.g., "1075 Police" -> "Police")
                parts = agency_name.split()
                while parts and parts[0].isdigit():
                    parts.pop(0)
                agency_name = ' '.join(parts)

                st.session_state.customer_info["agency_name"] = agency_name

            st.markdown(f"### {selected_site['address']}")
            st.write(f"📁 **Local Folder:** `{selected_site['folder_path']}`")
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("##### Infrastructure Detection")
                st.write(f"🪜 **Roof Access:** {selected_site['analysis'].get('roof_access')}")
                st.write(f"🏠 **Roof Type:** {selected_site['analysis'].get('roof_type')}")
            with col_b:
                st.markdown("##### Mounting & Hardware")
                st.write(f"📐 **Mounts:** {', '.join(selected_site['analysis'].get('mounting_structures', [])) or 'None'}")
                st.write(f"🔌 **Hardware:** {', '.join(selected_site['analysis'].get('hardware', [])) or 'None'}")
                
            # Rooftop Engineering Annotator Panel
            st.divider()
            st.subheader("🛠️ Interactive Rooftop Layout & Annotator")
            st.write("1. Click a thumbnail below to select the background. 2. Select node type/label. 3. Click directly on the image to place the node!")
            
            # 1. Thumbnails Selection Row
            st.markdown("##### Select Background Photo:")
            images_list = selected_site.get('images', [])
            cols_per_row = 6
            for i in range(0, len(images_list), cols_per_row):
                chunk = images_list[i:i+cols_per_row]
                col_thumb = st.columns(cols_per_row)
                for idx_in_chunk, img in enumerate(chunk):
                    global_idx = i + idx_in_chunk
                    with col_thumb[idx_in_chunk]:
                        img_path = img.get('dest_path') or img.get('path')
                        thumb_path = _get_displayable_image_path(img_path)
                        if thumb_path:
                            is_active = img['filename'] == st.session_state.active_bg_image
                            st.image(thumb_path, width=60)
                            btn_label = "🎯 Active" if is_active else "Select"
                            if st.button(btn_label, key=f"sel_thumb_{selected_site['site_id']}_{global_idx}", use_container_width=True):
                                st.session_state.active_bg_image = img['filename']
                                st.session_state.last_click[selected_site['site_id']] = None
                                st.rerun()
                        else:
                            st.caption(f"Error: {img['filename'][:8]}...")
            
            # Default to first image if none selected
            if not st.session_state.active_bg_image and selected_site.get('images'):
                st.session_state.active_bg_image = selected_site['images'][0]['filename']
                
            if st.session_state.active_bg_image:
                active_img_meta = next((img for img in selected_site['images'] if img['filename'] == st.session_state.active_bg_image), None)
                if not active_img_meta and selected_site.get('images'):
                    active_img_meta = selected_site['images'][0]
                    st.session_state.active_bg_image = active_img_meta['filename']

                if active_img_meta:
                    bg_path = active_img_meta.get('dest_path') or active_img_meta.get('path')
                    bg_display_path = _get_displayable_image_path(bg_path)

                    # Markers & Image placements state init - per image
                    # Backward compatibility: convert old 'markers' format to new 'markers_by_image' format
                    if 'markers_by_image' not in selected_site:
                        selected_site['markers_by_image'] = {}
                        # If old markers exist, assign them to the first image
                        if 'markers' in selected_site and selected_site['markers']:
                            first_img = selected_site['images'][0]['filename'] if selected_site.get('images') else None
                            if first_img:
                                selected_site['markers_by_image'][first_img] = selected_site.pop('markers', [])

                    if 'image_placements_by_image' not in selected_site:
                        selected_site['image_placements_by_image'] = {}

                    if st.session_state.active_bg_image not in selected_site['markers_by_image']:
                        selected_site['markers_by_image'][st.session_state.active_bg_image] = []

                    if st.session_state.active_bg_image not in selected_site['image_placements_by_image']:
                        selected_site['image_placements_by_image'][st.session_state.active_bg_image] = []

                    # Get markers and placements for current image
                    current_markers = selected_site['markers_by_image'][st.session_state.active_bg_image]
                    current_placements = selected_site['image_placements_by_image'][st.session_state.active_bg_image]

                    if 'eng_note' not in selected_site:
                        selected_site['eng_note'] = (
                            "Responder may be installed at this time with 110V, 20A service. "
                            "If Guardian is installed in the future, it will require 208V, 30A service "
                            "with additional wiring and electrical provisions to support the higher voltage requirement."
                        )

                    # Get available images from the images directory
                    images_dir = os.path.join(os.path.dirname(__file__), "images")
                    available_images = []
                    if os.path.exists(images_dir):
                        for img_file in os.listdir(images_dir):
                            if img_file.lower().endswith(('.png', '.jpg', '.jpeg')):
                                available_images.append(img_file)
                    available_images.sort()

                    # Form to configure placement - Nodes or Images
                    st.markdown("##### Placement Customization (To place on image click)")

                    # Define dropdown options for each node type
                    node_type_options = {
                        "Electric": ["15 Amp 110V AC", "20 Amp 110V AC", "30 Amp 208V AC"],
                        "Data": ["BRINC RF Site 25 50", "BRINC Station 25 50", "BRINC Radar Site 10 10"],
                        "RF": ["10 foot pole", "20 foot pole", "30 foot pole", "microsite", "Tower"],
                        "Unistrut": ["3 Unistrut", "4 Unistrut"],
                        "Lift": ["Crane", "Fire Department"]
                    }

                    # Placement mode selection
                    placement_mode = st.radio("What to place:", ["📍 Node", "🖼️ Image"], horizontal=True, key=f"int_placement_mode_{selected_site['site_id']}")

                    m_type = None
                    m_label = None
                    placement_image = None

                    if "Node" in placement_mode:
                        col_m1, col_m2 = st.columns(2)
                        with col_m1:
                            m_type = st.selectbox("Node Type", ["Electric", "Data", "RF", "Unistrut", "Lift"], key=f"int_mtype_{selected_site['site_id']}")
                        with col_m2:
                            # Get available labels for selected node type, default to first option
                            available_labels = node_type_options.get(m_type, [""])
                            default_label = available_labels[0] if available_labels else ""
                            m_label = st.selectbox("Node Label", available_labels, key=f"int_mlabel_{selected_site['site_id']}")
                    else:  # Image mode
                        if available_images:
                            placement_image = st.selectbox("Select Image to Place", available_images, key=f"int_placement_img_{selected_site['site_id']}")
                        else:
                            st.warning("No images available in the images directory.")
                            placement_image = None

                    # 2. Interactive Image coordinate placement
                    st.markdown("🎯 **Click on the image below to place this node:**")

                    # Create unique drawing path per image
                    img_base_name = os.path.splitext(st.session_state.active_bg_image)[0]
                    output_drawing_path = os.path.join(selected_site['folder_path'], f"engineering_layout_{img_base_name}.png")
                    display_img_path = output_drawing_path if os.path.exists(output_drawing_path) else bg_display_path
                    if not display_img_path:
                        st.error(f"Cannot preview or annotate this image: {active_img_meta['filename']}")
                        st.stop()

                    # We show the image and capture click
                    # Force full refresh by including image path in key
                    canvas_key = f"canvas_{selected_site['site_id']}_{hash(st.session_state.active_bg_image)}"

                    # Check image dimensions to preserve portrait orientation
                    try:
                        with Image.open(display_img_path) as img_check:
                            img_width, img_height = img_check.size
                        # Use height for portrait images (height > width), width for landscape
                        # Constrain to max 600px to keep UI manageable
                        if img_height > img_width:
                            # Portrait orientation - use height constraint
                            display_size = min(600, img_height)
                            click = streamlit_image_coordinates(display_img_path, key=canvas_key, height=display_size)
                        else:
                            # Landscape or square - use width constraint
                            display_size = min(600, img_width)
                            click = streamlit_image_coordinates(display_img_path, key=canvas_key, width=display_size)
                    except Exception:
                        # Fallback to width-based display if dimension check fails
                        click = streamlit_image_coordinates(display_img_path, key=canvas_key, width=600)

                    if click:
                        click_key = f"{selected_site['site_id']}_{st.session_state.active_bg_image}_{click.get('x')}_{click.get('y')}"
                        if st.session_state.last_click.get(selected_site['site_id']) != click_key:
                            st.session_state.last_click[selected_site['site_id']] = click_key

                            click_x = click.get("x", 0)
                            click_y = click.get("y", 0)

                            try:
                                with Image.open(display_img_path) as temp_img:
                                    w, h = temp_img.size

                                # Scale click coordinates from 600px display to actual image dimensions
                                display_width = 600
                                scale_x = w / display_width
                                scale_y = h / (display_width * h / w)  # Maintain aspect ratio
                                click_x = click_x * scale_x
                                click_y = click_y * scale_y

                                is_drawing = os.path.exists(output_drawing_path)
                                photo_width_ratio = 0.80 if is_drawing else 1.0

                                ratio_x = click_x / w
                                ratio_y = click_y / h

                                if ratio_x <= photo_width_ratio:
                                    if "Node" in placement_mode:
                                        # Place Node
                                        node_x_pct = (ratio_x / photo_width_ratio) * 100
                                        node_y_pct = ratio_y * 100

                                        label_x_pct = max(node_x_pct - 15, 5)
                                        label_y_pct = max(node_y_pct - 8, 5)

                                        selected_site['markers_by_image'][st.session_state.active_bg_image].append({
                                            'type': m_type,
                                            'label': m_label,
                                            'node_x': node_x_pct,
                                            'node_y': node_y_pct,
                                            'label_x': label_x_pct,
                                            'label_y': label_y_pct
                                        })
                                        success_msg = f"Added {m_label} Node!"
                                    else:
                                        # Place Image
                                        img_x_pct = (ratio_x / photo_width_ratio) * 100
                                        img_y_pct = ratio_y * 100

                                        selected_site['image_placements_by_image'][st.session_state.active_bg_image].append({
                                            'image_name': placement_image,
                                            'x': img_x_pct,
                                            'y': img_y_pct
                                        })
                                        success_msg = f"Added {placement_image}!"

                                    # Auto-compile drawing in background
                                    reporter.create_engineering_drawing(
                                        bg_display_path or bg_path,
                                        output_drawing_path,
                                        selected_site['markers_by_image'][st.session_state.active_bg_image],
                                        selected_site['eng_note'],
                                        address=selected_site['address'],
                                        image_placements=selected_site['image_placements_by_image'][st.session_state.active_bg_image],
                                        images_dir=images_dir
                                    )
                                    # Save meta session
                                    _save_session_metadata(st.session_state.processed_sites)
                                    st.success(success_msg)
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error registering click: {e}")

                    # Marker list with individual delete buttons
                    current_markers = selected_site['markers_by_image'].get(st.session_state.active_bg_image, [])
                    if current_markers:
                        st.markdown("**Placed Markers:**")
                        color_emoji = {
                            'Electric': '🔴',
                            'Data': '🟠',
                            'RF': '🟣',
                            'Unistrut': '⚪',
                            'Lift': '🟡',
                        }
                        for idx, marker in enumerate(current_markers):
                            mcol1, mcol2 = st.columns([3, 1])
                            with mcol1:
                                emoji = color_emoji.get(marker.get('type', ''), '⚫')
                                st.markdown(f"{emoji} **{marker.get('type', '')}** — {marker.get('label', '')}")
                            with mcol2:
                                if st.button("✕ Remove", key=f"del_marker_{selected_site['site_id']}_{st.session_state.active_bg_image}_{idx}"):
                                    selected_site['markers_by_image'][st.session_state.active_bg_image].pop(idx)
                                    # Re-render drawing
                                    if selected_site['markers_by_image'][st.session_state.active_bg_image]:
                                        reporter.create_engineering_drawing(
                                            bg_display_path or bg_path,
                                            output_drawing_path,
                                            selected_site['markers_by_image'][st.session_state.active_bg_image],
                                            selected_site['eng_note'],
                                            address=selected_site['address'],
                                            image_placements=selected_site['image_placements_by_image'].get(st.session_state.active_bg_image, []),
                                            images_dir=images_dir
                                        )
                                    elif os.path.exists(output_drawing_path):
                                        os.remove(output_drawing_path)
                                    _save_session_metadata(st.session_state.processed_sites)
                                    st.rerun()
                    else:
                        st.caption("No markers placed yet.")

                    # Action Buttons
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        selected_site['eng_note'] = st.text_area("Engineer's Notes Text", value=selected_site['eng_note'], key=f"int_engnote_{selected_site['site_id']}")
                    with col_btn2:
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("🗑️ Clear All Placements", use_container_width=True, key=f"int_clearnode_{selected_site['site_id']}"):
                            selected_site['markers_by_image'][st.session_state.active_bg_image] = []
                            selected_site['image_placements_by_image'][st.session_state.active_bg_image] = []
                            if os.path.exists(output_drawing_path):
                                os.remove(output_drawing_path)
                            _save_session_metadata(st.session_state.processed_sites)
                            st.warning("Cleared all nodes and images for this photo.")
                            st.rerun()

                        if st.button("🔄 Refresh Rendering", use_container_width=True, key=f"int_redraw_{selected_site['site_id']}"):
                            reporter.create_engineering_drawing(
                                bg_display_path or bg_path,
                                output_drawing_path,
                                selected_site['markers_by_image'][st.session_state.active_bg_image],
                                selected_site['eng_note'],
                                address=selected_site['address'],
                                image_placements=selected_site['image_placements_by_image'][st.session_state.active_bg_image],
                                images_dir=images_dir
                            )
                            _save_session_metadata(st.session_state.processed_sites)
                            st.rerun()

                    # Show drawing preview below buttons if it exists
                    if os.path.exists(output_drawing_path):
                        st.image(output_drawing_path, caption="Active Engineering Markup Layout Preview", use_container_width=True)
            else:
                st.warning("Please upload or process images first to mark up.")
                
            # Report generation button
            st.subheader("Report Generation")
            report_name = st.text_input("Master Document Name", value="Master_DFR_Site_Survey_Report.docx")
            if st.button("📄 Build Word Document", use_container_width=True):
                try:
                    # Update metadata save
                    _save_session_metadata(st.session_state.processed_sites)

                    # Create subfolder with PD name and creation date
                    pd_name = st.session_state.customer_info.get("agency_name", "Report").replace(" ", "_")
                    creation_date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    report_subfolder = os.path.join(output_dir, f"{pd_name}_{creation_date}")
                    os.makedirs(report_subfolder, exist_ok=True)

                    # Save report in subfolder
                    report_path = os.path.join(report_subfolder, report_name)

                    # Get Drive manager for report upload
                    drive = None
                    try:
                        drive = get_drive_manager()
                    except Exception:
                        pass

                    reporter.generate_word_report(
                        st.session_state.processed_sites,
                        report_path,
                        customer_info=st.session_state.customer_info,
                        drive_manager=drive,
                        drive_reports_folder_id=st.session_state.get('reports_folder_id')
                    )
                    st.success(f"Generated Word Document at `{report_path}`!")
                    st.session_state.generated_report = report_path
                except Exception as e:
                    st.error(f"Report generation error: {e}")
        else:
            st.info("No sites loaded. Run the ingestion step first.")

    with col3:
        st.subheader("Previous Sessions")
        resolved_output_dir = _resolve_app_path(output_dir)
        if os.path.exists(resolved_output_dir):
            subdirs = [d for d in os.listdir(resolved_output_dir) if os.path.isdir(os.path.join(resolved_output_dir, d)) and d != "__pycache__" and d != "Unclassified_No_GPS"]
            if subdirs:
                for d in sorted(subdirs):
                    # Try to load the actual agency name from metadata first
                    meta_file = os.path.join(resolved_output_dir, d, "session_metadata.json")
                    display_name = None

                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, "r") as mf:
                                loaded_metadata = json.load(mf)
                            # Use the agency name from customer_info if available
                            if "customer_info" in loaded_metadata and loaded_metadata["customer_info"].get("agency_name"):
                                display_name = loaded_metadata["customer_info"]["agency_name"]
                        except Exception:
                            pass

                    # Fallback to parsing folder name if metadata lookup failed
                    if not display_name:
                        display_name = d.replace("Site_1_", "").replace("Site_2_", "").replace("Site_3_", "").replace("_", " ").replace("Site-001", "").replace("Site-002", "")
                        if "Lansing" in display_name:
                            display_name = "Lansing Illinois Police"

                    if st.button(display_name, key=f"prev_sess_btn_{d}", use_container_width=True):
                        if os.path.exists(meta_file):
                            try:
                                with open(meta_file, "r") as mf:
                                    loaded_site = json.load(mf)
                                st.session_state.processed_sites = [loaded_site]
                                if loaded_site.get("images"):
                                    st.session_state.active_bg_image = loaded_site["images"][0]["filename"]
                                if "customer_info" in loaded_site:
                                    st.session_state.customer_info = loaded_site["customer_info"]
                                st.success(f"Loaded session for {display_name}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to load session: {e}")
                        else:
                            st.warning("No session_metadata.json found.")
            else:
                st.caption("No previous sessions found.")
        else:
            st.caption("No output directory found.")

with tab2:
    st.subheader("Cloud Workflow Orchestration")
    st.write("Connect survey findings to CRM, task tracking, calendar scheduler, and communications.")
    
    col_x, col_y = st.columns(2)
    
    with col_x:
        st.markdown("#### CRM & Kickoff Scheduler")
        if st.button("🔍 Fetch Customer Purchase Info (HubSpot)", use_container_width=True, key="hs_sync_tab2"):
            st.session_state.integration_logs.append("[HubSpot API] GET /crm/v3/objects/deals - Retrieved Contact: Mike Hynek, Deal: DFR Node Deployment")
            st.info("Deal information retrieved successfully.")
            
        if st.button("📅 Schedule Kickoff Meeting (Google Calendar)", use_container_width=True, key="cal_sync_tab2"):
            st.session_state.integration_logs.append("[Google Calendar API] POST /events - Scheduled Kickoff for Lansing PD")
            st.success("Meeting Scheduled & Invites sent to stakeholders.")

        if st.button("☁️ Sync Report to Google Drive", use_container_width=True, key="drive_sync_tab2"):
            if hasattr(st.session_state, 'generated_report'):
                st.session_state.integration_logs.append(f"[Google Drive API] POST /files - Uploaded '{os.path.basename(st.session_state.generated_report)}'")
                st.success("Report synchronized to cloud storage.")
            else:
                st.warning("Generate the Word report first on the Survey Pipeline tab.")

    with col_y:
        st.markdown("#### Operations & Communication")
        if st.button("🎫 Create Deployment Tracker (Jira)", use_container_width=True, key="jira_sync_tab2"):
            st.session_state.integration_logs.append("[Jira REST API] POST /issue - Created onboarding ticket LANS-101")
            st.success("Jira Onboarding Issue Created: LANS-101")
            
        if st.button("💬 Send Project Status to Slack", use_container_width=True, key="slack_sync_tab2"):
            st.session_state.integration_logs.append("[Slack Webhook] POST /hooks - Posted Lansing PD survey status")
            st.success("Notification broadcasted to Slack channels.")

with tab3:
    st.subheader("Execution & Integration Logs")
    if st.session_state.integration_logs:
        for log in st.session_state.integration_logs:
            st.text(log)
    else:
        st.write("No integration steps executed yet.")
