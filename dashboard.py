import os
import json
import re
import subprocess
import tempfile
from html import escape
import streamlit as st
import pandas as pd
from PIL import Image
import datetime
import time
from zoneinfo import ZoneInfo
from google_drive import get_drive_manager
from gmail_lookup import search_gmail_for_contacts
from agency_docs import fetch_agency_docs_parallel
from dashboard_metrics import (
    count_connected_sources,
    count_contacts,
    get_connected_source_statuses,
)
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
import folium
from streamlit_folium import st_folium
import processor
import analyzer
import reporter
from contact_rows import build_initial_poc_rows, sync_customer_info_from_poc_rows
from site_model import CandidateSite, export_sites_json, export_sites_csv
from processor import cluster_images, split_clusters_by_time_gap, cluster_to_candidate_sites, MIN_SITE_PHOTOS
from analyzer import enrich_gis

# Import the image coordinates package
try:
    from streamlit_image_coordinates import streamlit_image_coordinates
except ImportError:
    st.error("Please ensure streamlit-image-coordinates is installed.")

# Page config
st.set_page_config(
    page_title="DFR Site Survey & Deployment Suite",
    page_icon="D",
    layout="wide",
    initial_sidebar_state="collapsed"
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
    section.main > div.block-container {
        max-width: 1480px;
        padding-top: 0.75rem;
        padding-bottom: 1.5rem;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
    }
    section[data-testid="stSidebar"] {
        width: 18rem;
    }
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
        display: none;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 0.75rem;
        padding-bottom: 0.75rem;
        padding-left: 0.75rem;
        padding-right: 0.75rem;
    }
    section[data-testid="stSidebar"] img {
        max-width: 120px;
    }
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        margin-top: 0.25rem;
        margin-bottom: 0.35rem;
    }
    section[data-testid="stSidebar"] button {
        padding-top: 0.35rem;
        padding-bottom: 0.35rem;
        min-height: 2.2rem;
        font-size: 0.88rem;
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
    .mission-strip {
        display: flex;
        flex-wrap: wrap;
        gap: 10px 14px;
        align-items: center;
        margin: 8px 0 12px 0;
        padding: 12px 14px;
        border: 1px solid #DBEAFE;
        border-radius: 14px;
        background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
    }
    .mission-chip {
        display: inline-flex;
        align-items: baseline;
        gap: 6px;
        padding-right: 10px;
        border-right: 1px solid rgba(148, 163, 184, 0.35);
        color: #0F172A;
        font-size: 0.92rem;
        font-weight: 600;
        white-space: nowrap;
    }
    .mission-chip:last-child {
        border-right: none;
        padding-right: 0;
    }
    .mission-chip .label {
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-size: 0.68rem;
        font-weight: 700;
    }
    .workflow-roadmap {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 4px 0 16px 0;
    }
    .workflow-step {
        border-radius: 999px;
        border: 1px solid #CBD5E1;
        padding: 6px 12px;
        background: #FFFFFF;
        color: #475569;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .workflow-step.current {
        background: linear-gradient(135deg, #DBEAFE 0%, #EFF6FF 100%);
        border-color: #60A5FA;
        color: #1D4ED8;
    }
    .workflow-step.complete {
        background: #ECFDF5;
        border-color: #34D399;
        color: #047857;
    }
    .enterprise-section {
        border: 1px solid #DBEAFE;
        border-radius: 18px;
        background: #FFFFFF;
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.05);
        padding: 1rem 1rem 0.9rem 1rem;
        margin-bottom: 1rem;
    }
    .enterprise-section h2,
    .enterprise-section h3 {
        margin-top: 0;
    }
    .stage-callout {
        border-radius: 14px;
        background: linear-gradient(135deg, #EFF6FF 0%, #FFFFFF 100%);
        border: 1px solid #BFDBFE;
        padding: 0.9rem 1rem;
        color: #1E3A8A;
        font-weight: 600;
        margin-top: 0.65rem;
    }
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 15px;
    }
    .sidebar-activity {
        border-radius: 14px;
        padding: 0.8rem 0.9rem;
        margin-bottom: 0.85rem;
        border: 1px solid #CBD5E1;
        background: #F8FAFC;
        color: #0F172A;
    }
    .sidebar-activity.running {
        border-color: #93C5FD;
        background: linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 100%);
    }
    .sidebar-activity.complete {
        border-color: #86EFAC;
        background: linear-gradient(135deg, #ECFDF5 0%, #F8FAFC 100%);
    }
    .sidebar-activity.error {
        border-color: #FCA5A5;
        background: linear-gradient(135deg, #FEF2F2 0%, #F8FAFC 100%);
    }
    .sidebar-activity .eyebrow {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748B;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    .sidebar-activity .title {
        font-size: 0.95rem;
        font-weight: 700;
        line-height: 1.25;
        margin-bottom: 0.2rem;
    }
    .sidebar-activity .detail {
        font-size: 0.8rem;
        color: #475569;
        line-height: 1.35;
    }
</style>
""", unsafe_allow_html=True)

def _set_phase(name: str, status: str = "active"):
    """Update current processing phase in session state."""
    st.session_state._processing_phase = {
        "name": name,
        "start_time": time.time(),
        "status": status,
    }

def _render_phase_indicator():
    """Render persistent phase tracker showing current phase and elapsed time."""
    phase = st.session_state.get("_processing_phase", {})
    if not phase or not phase.get("name"):
        return

    name = phase.get("name", "Idle")
    status = phase.get("status", "active")
    start_time = phase.get("start_time")

    # Calculate elapsed time
    if start_time:
        elapsed_seconds = int(time.time() - start_time)
        minutes = elapsed_seconds // 60
        seconds = elapsed_seconds % 60
        elapsed_str = f"({minutes}m {seconds:02d}s)"
    else:
        elapsed_str = ""

    # Status emoji
    emoji_map = {
        "active": "🔵",
        "waiting": "⚪",
        "pending": "🟡",
        "complete": "✅",
    }
    emoji = emoji_map.get(status, "🔵")

    # Render phase indicator
    st.markdown(f"**{emoji} {name} {elapsed_str}**", unsafe_allow_html=False)

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
        "it_phone": "",
        "facilities_engineer": "",
        "facilities_email": "",
        "facilities_phone": "",
        "rtcc_name": "",
        "rtcc_email": "",
        "rtcc_phone": "",
        "radio_shop_name": "",
        "radio_shop_email": "",
        "radio_shop_phone": "",
        "crane_contractor": "",
        "tower_climber_contractor": "",
        "brinc_pm": "",
        "contacts": [],
        "survey_delivery_target": "",
        "power_circuit_requirements": "",
        "internet_ethernet_access": "",
        "follow_up_requirements": "",
        "action_items": "",
        "surveyor": "",
        "survey_date": "",
        "report_date": "",
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
if "drive_folder_url" not in st.session_state:
    st.session_state.drive_folder_url = None
if "candidate_sites" not in st.session_state:
    st.session_state.candidate_sites = []
if "_last_doc_search_agency" not in st.session_state:
    st.session_state._last_doc_search_agency = ""
if "jira_results" not in st.session_state:
    st.session_state.jira_results = {}
if "hubspot_results" not in st.session_state:
    st.session_state.hubspot_results = {}
if "agency_contacts" not in st.session_state:
    st.session_state.agency_contacts = []
if "agency_docs" not in st.session_state:
    st.session_state.agency_docs = []
if "agency_calendar" not in st.session_state:
    st.session_state.agency_calendar = []
if "agency_docs_loading" not in st.session_state:
    st.session_state.agency_docs_loading = False
if "agency_docs_errors" not in st.session_state:
    st.session_state.agency_docs_errors = {}
if "sidebar_activity" not in st.session_state:
    st.session_state.sidebar_activity = {
        "state": "idle",
        "label": "Idle",
        "detail": "Waiting for the next task.",
    }

SUPPORTED_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tiff", ".webp", ".heic", ".heif")
APP_DIR = os.path.dirname(os.path.abspath(__file__))
_sidebar_activity_placeholder = None

def _resolve_app_path(path):
    """Resolve relative paths against the dashboard file location."""
    cleaned_path = path.strip().replace('"', '').replace("'", "")
    if os.path.isabs(cleaned_path):
        return os.path.abspath(cleaned_path)
    return os.path.abspath(os.path.join(APP_DIR, cleaned_path))


def _safe_filename_part(text):
    """Return a filename-safe text fragment while preserving readable spacing."""
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", str(text).strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ._")


def _default_master_document_name():
    """Build the default report filename from the agency name and survey date."""
    agency = st.session_state.customer_info.get("agency_name", "").strip()
    survey_date = ""
    if st.session_state.candidate_sites:
        survey_date = st.session_state.candidate_sites[0].identity.survey_date or ""
    if not survey_date and st.session_state.processed_sites:
        survey_date = st.session_state.processed_sites[0].get("survey_date", "") or ""
    if not survey_date:
        survey_date = datetime.date.today().isoformat()

    parts = [part for part in (_safe_filename_part(agency), survey_date) if part]
    if parts:
        return f"{' '.join(parts)}.docx"
    return f"Master DFR Site Survey {survey_date}.docx"


def _report_contact_preview_rows():
    """Build the same contact rows used by the report generator for on-screen review."""
    customer_info = st.session_state.get("customer_info", {})
    rows = [
        ("Agency Name / Address", reporter._format_contact_block(
            customer_info.get("agency_name", ""),
            customer_info.get("agency_address", ""),
        )),
        ("Point of Contact", reporter._format_contact_block(
            customer_info.get("poc_name", ""),
            customer_info.get("poc_email", ""),
            customer_info.get("poc_phone", ""),
        )),
        ("RTCC/RTIC", reporter._format_role_contact(customer_info, "RTCC", "rtcc_name", "rtcc_email", "rtcc_phone")),
        ("Information Technology", reporter._format_role_contact(customer_info, "IT", "it_director", "it_email", "it_phone")),
        ("Facilities Engineer", reporter._format_role_contact(customer_info, "Facilities", "facilities_engineer", "facilities_email", "facilities_phone")),
        ("Radio Shop Engineer", reporter._format_role_contact(customer_info, "Radio Shop", "radio_shop_name", "radio_shop_email", "radio_shop_phone")),
        ("Crane Contractor", reporter._format_scalar_contact(customer_info, "crane_contractor", "DNA")),
        ("Tower Climber Contractor", reporter._format_scalar_contact(customer_info, "tower_climber_contractor", "DNA")),
        ("BRINC Project Manager", reporter._format_scalar_contact(customer_info, "brinc_pm", "DNA")),
    ]
    return rows


def _derive_survey_date_from_sites(site_data_list):
    """Return the most common EXIF capture date from processed site images."""
    date_counts = {}
    for site in site_data_list or []:
        for img in site.get("images", []):
            capture_time = img.get("time")
            if isinstance(capture_time, datetime.datetime):
                date_str = capture_time.date().isoformat()
            elif isinstance(capture_time, datetime.date):
                date_str = capture_time.isoformat()
            elif capture_time:
                date_str = ""
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        date_str = datetime.datetime.strptime(str(capture_time), fmt).date().isoformat()
                        break
                    except ValueError:
                        continue
            else:
                date_str = ""
            if date_str:
                date_counts[date_str] = date_counts.get(date_str, 0) + 1

    if not date_counts:
        return ""
    return sorted(date_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]


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
        # Preserve the derived connected contacts list so it survives reloads.
        site["agency_contacts"] = st.session_state.get("agency_contacts", [])
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


def _append_integration_log(message):
    """Store integration activity as timestamped tuples for later grouping/filtering."""
    timestamp = datetime.datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M:%S")
    st.session_state.integration_logs.append((timestamp, message))


def _format_integration_log(entry):
    """Render legacy string logs and new timestamped tuples consistently."""
    if isinstance(entry, tuple) and len(entry) == 2:
        timestamp, message = entry
        return f"[{timestamp}] {message}"
    return str(entry)


def _render_sidebar_activity():
    """Render the current task activity card at the top of the sidebar."""
    if _sidebar_activity_placeholder is None:
        return

    activity = st.session_state.get("sidebar_activity", {})
    state = activity.get("state", "idle")
    label = escape(str(activity.get("label", "Idle")))
    detail = escape(str(activity.get("detail", "Waiting for the next task.")))
    badge = {
        "idle": "Status",
        "running": "In Progress",
        "complete": "Completed",
        "error": "Attention",
    }.get(state, "Status")

    _sidebar_activity_placeholder.markdown(
        f"""
        <div class="sidebar-activity {state}">
            <div class="eyebrow">{badge}</div>
            <div class="title">{label}</div>
            <div class="detail">{detail}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _set_sidebar_activity(label, detail="", state="running"):
    """Persist and render the current long-running activity for the sidebar."""
    st.session_state.sidebar_activity = {
        "state": state,
        "label": label,
        "detail": detail or "",
    }
    _render_sidebar_activity()


def _set_upload_processing_state(state, *, site_count=None, file_count=None):
    """Track whether upload processing is still computing, finalizing UI, or done."""
    st.session_state["_upload_processing_state"] = state
    summary = dict(st.session_state.get("_upload_processing_summary", {}))
    if site_count is not None:
        summary["site_count"] = site_count
    if file_count is not None:
        summary["file_count"] = file_count
    st.session_state["_upload_processing_summary"] = summary
    st.session_state["_upload_processing_complete"] = state == "complete"


def _finalize_upload_processing_if_ready():
    """Mark upload processing complete only after the full UI render pass succeeds."""
    if st.session_state.get("_upload_processing_state") != "finalizing":
        return

    summary = st.session_state.get("_upload_processing_summary", {})
    site_count = summary.get("site_count", len(st.session_state.get("processed_sites", [])))
    file_count = summary.get("file_count", st.session_state.get("_last_uploaded_file_count", 0))
    _set_sidebar_activity(
        "Processing complete",
        f"Processed {site_count} site(s) from {file_count} uploaded file(s).",
        state="complete",
    )
    _set_upload_processing_state("complete", site_count=site_count, file_count=file_count)
    st.rerun()


def _get_displayable_image_path(image_path, site_folder=None):
    """Return a browser-safe image path for Streamlit display, or None if unreadable.

    Args:
        image_path: Primary absolute path to try (dest_path or path from metadata).
        site_folder: Optional fallback directory. When image_path is stale (e.g. a
            temp-dir path from a previous session), the function will look for the
            file by its basename inside site_folder before giving up.
    """
    if image_path:
        image_path = _resolve_app_path(image_path)

    # If the stored path doesn't exist, try resolving by filename inside site_folder
    if (not image_path or not os.path.exists(image_path)) and site_folder:
        if image_path:
            candidate = _resolve_app_path(os.path.join(site_folder, os.path.basename(image_path)))
            if os.path.exists(candidate):
                image_path = candidate
    if not image_path or not os.path.exists(image_path):
        return None

    safe_extensions = (".jpg", ".jpeg", ".png", ".webp")
    ext = os.path.splitext(image_path)[1].lower()

    # Browser-safe formats can be served directly
    if ext in safe_extensions:
        return image_path

    # Non-safe formats (HEIC, TIFF, etc.) need conversion to PNG
    preview_dir = os.path.join(os.path.dirname(image_path), ".previews")
    os.makedirs(preview_dir, exist_ok=True)
    preview_name = f"{os.path.splitext(os.path.basename(image_path))[0]}.png"
    preview_path = os.path.join(preview_dir, preview_name)

    if os.path.exists(preview_path):
        return preview_path

    try:
        img = Image.open(image_path)
        img.convert("RGB").save(preview_path, "PNG")
        img.close()
        return preview_path
    except Exception as e:
        print(f"Image preview unavailable for {image_path}: {e}")
        return None


@st.cache_data(show_spinner=False)
def _list_available_images(images_dir):
    """Return the reusable image assets available for image placement."""
    if not os.path.exists(images_dir):
        return []

    return sorted(
        img_file
        for img_file in os.listdir(images_dir)
        if img_file.lower().endswith(('.png', '.jpg', '.jpeg'))
    )


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
        # Use extract_city_from_address to validate Nominatim city against amenity/street keywords
        city = processor.extract_city_from_address(full_address)
        state = getattr(full_address, 'state', None)
        agency_name = f"{city} Police Department" if city else None
        return {
            "lat": lat,
            "lon": lon,
            "address": full_address,
            "city": city,
            "state": state,
            "agency_name": agency_name,
        }
    except Exception as e:
        print(f"GPS detection error: {e}")
        return None


@st.cache_data(ttl=600, show_spinner="Searching Gmail for agency contacts...")
def _lookup_contacts_from_gmail(agency_name, city=None):
    """Search Gmail and Calendar for kickoff calls / invites with this agency."""
    return search_gmail_for_contacts(agency_name, city)


def _render_jira_ticket_results(jira_results):
    """Render Jira search results as a compact ticket table."""
    tickets = jira_results.get("tickets", [])
    if not tickets:
        return

    search_terms = jira_results.get("search_terms", [])
    with st.expander("Jira tickets found", expanded=True):
        if search_terms:
            st.caption("Search terms: " + ", ".join(search_terms))
        df = pd.DataFrame(tickets)
        display_cols = [col for col in ["key", "summary", "status", "assignee", "url"] if col in df.columns]
        st.dataframe(df[display_cols], width="stretch", hide_index=True)


def _run_connected_docs_search(agency, city=""):
    """Run Gmail + Drive + Jira + HubSpot search and store results in session state.

    Returns True if any search produced results.
    """
    from gmail_lookup import search_drive_for_gemini_notes, search_jira_for_tickets, search_hubspot_for_records, search_calendar_for_events

    found_any = False
    _set_sidebar_activity(
        "Looking up connected docs",
        f"Searching Gmail, Drive, Jira, HubSpot, and Calendar for {agency}.",
    )

    # Gmail contacts
    _set_sidebar_activity("Looking up connected docs", f"Searching Gmail contacts for {agency}.")
    contacts = _lookup_contacts_from_gmail(agency, city)
    contact_status = contacts.get("status", "no_results") if contacts else "no_results"
    if contact_status == "connected":
        found = contacts.get("all_contacts", [])
        if found:
            st.session_state["gmail_found_contacts"] = found
            st.session_state["agency_contacts"] = found
        for key in ("poc_name", "poc_email", "poc_phone", "it_director", "it_email"):
            if contacts.get(key):
                st.session_state.customer_info[key] = contacts[key]
        _append_integration_log(f"[Gmail API] Found {len(found)} contacts for {agency}")
        found_any = True
    elif contact_status == "auth_error":
        _append_integration_log(f"[Gmail API] Auth error: {contacts.get('error', '')}")
    else:
        _append_integration_log(f"[Gmail API] No contacts found for {agency}")

    # Drive: Gemini notes & folders
    _set_sidebar_activity("Looking up connected docs", f"Searching Google Drive for {agency}.")
    drive_results = search_drive_for_gemini_notes(agency, city)
    drive_status = drive_results.get("status", "no_results")
    if drive_status == "connected":
        st.session_state["drive_gemini_results"] = drive_results
        notes_count = len(drive_results.get("gemini_notes", []))
        folders_count = len(drive_results.get("drive_folders", []))
        _append_integration_log(
            f"[Drive API] Found {notes_count} Gemini notes, {folders_count} folders for {agency}"
        )
        specs = drive_results.get("extracted_specs", {})
        for spec_key in ("power_circuit_requirements", "internet_ethernet_access", "survey_delivery_target"):
            if specs.get(spec_key) and not st.session_state.customer_info.get(spec_key):
                st.session_state.customer_info[spec_key] = specs[spec_key]
        found_any = True
    elif drive_status == "auth_error":
        _append_integration_log(f"[Drive API] Auth error: {drive_results.get('error', '')}")

    # Jira tickets
    _set_sidebar_activity("Looking up connected docs", f"Searching Jira for {agency}.")
    jira_results = search_jira_for_tickets(
        agency,
        city=city or None,
        jira_url=st.session_state.get("_jira_url", ""),
        jira_email=st.session_state.get("_jira_email", ""),
        jira_token=st.session_state.get("_jira_token", ""),
    )
    st.session_state["jira_results"] = jira_results
    if jira_results["status"] == "connected":
        _append_integration_log(
            f"[Jira API] Found {len(jira_results['tickets'])} tickets for {agency}"
        )
        _render_jira_ticket_results(jira_results)
        found_any = True
    elif jira_results["status"] == "error":
        _append_integration_log(f"[Jira API] Error: {jira_results['error']}")

    # HubSpot records
    _set_sidebar_activity("Looking up connected docs", f"Searching HubSpot for {agency}.")
    hubspot_results = search_hubspot_for_records(
        agency,
        hubspot_token=st.session_state.get("_hubspot_token", ""),
    )
    st.session_state["hubspot_results"] = hubspot_results
    if hubspot_results["status"] == "connected":
        co_count = len(hubspot_results["companies"])
        deal_count = len(hubspot_results["deals"])
        _append_integration_log(
            f"[HubSpot API] Found {co_count} companies, {deal_count} deals for {agency}"
        )
        found_any = True
    elif hubspot_results["status"] == "error":
        _append_integration_log(f"[HubSpot API] Error: {hubspot_results['error']}")

    # Calendar events
    _set_sidebar_activity("Looking up connected docs", f"Searching Calendar events for {agency}.")
    calendar_results = search_calendar_for_events(agency, city)
    st.session_state["calendar_results"] = calendar_results
    if calendar_results["status"] == "connected":
        _append_integration_log(
            f"[Calendar API] Found {len(calendar_results['events'])} events for {agency}"
        )
        found_any = True
    elif calendar_results["status"] == "auth_error":
        _append_integration_log(f"[Calendar API] Auth error: {calendar_results.get('error', '')}")

    # Department-level docs, events, and invite contacts
    _set_sidebar_activity(
        "Looking up connected docs",
        f"Searching department docs and calendar invites for {agency}.",
    )
    parallel_result = fetch_agency_docs_parallel(
        agency,
        "",
        st.session_state,
        city_hint=city or None,
    )
    parallel_contacts = parallel_result.get("contacts", [])
    if parallel_contacts:
        st.session_state["agency_contacts"] = parallel_contacts
        found_any = True
    st.session_state["agency_docs"] = parallel_result.get("docs", [])
    if st.session_state["agency_docs"]:
        found_any = True
    st.session_state["agency_calendar"] = parallel_result.get("events", [])
    if not st.session_state["agency_calendar"] and calendar_results.get("status") == "connected":
        st.session_state["agency_calendar"] = [
            {
                "name": event.get("title", "Unknown"),
                "date": event.get("date", "Unknown"),
                "time": event.get("time", ""),
                "attendee_count": event.get("attendees_count", 0),
                "url": event.get("url", ""),
            }
            for event in calendar_results.get("events", [])
        ]
    if st.session_state["agency_calendar"]:
        st.session_state["calendar_results"] = {
            "status": "connected",
            "events": st.session_state["agency_calendar"],
        }
        found_any = True
    st.session_state["agency_docs_errors"] = parallel_result.get("errors", {})

    st.session_state._last_doc_search_agency = agency
    _set_sidebar_activity(
        "Connected docs lookup complete",
        f"Finished searching connected systems for {agency}.",
        state="complete",
    )
    return found_any


def _mission_overview():
    """Return lightweight status data for the top-of-page mission summary."""
    processed_sites = st.session_state.get("processed_sites", [])
    customer_info = st.session_state.get("customer_info", {})
    uploaded_count = int(st.session_state.get("_last_uploaded_file_count", 0) or 0)
    agency_name = customer_info.get("agency_name", "").strip()
    connected_sources = count_connected_sources(st.session_state)

    if processed_sites:
        stage = "Review"
        stage_note = f"{len(processed_sites)} site(s) detected"
    elif uploaded_count:
        stage = "Ingesting"
        stage_note = f"{uploaded_count} file(s) queued"
    else:
        stage = "Intake"
        stage_note = "Ready for first upload"

    if connected_sources and processed_sites:
        stage = "Sync"
        stage_note = f"{connected_sources} connected source(s)"

    return {
        "agency": agency_name or "Not set",
        "sites": len(processed_sites),
        "files": uploaded_count,
        "stage": stage,
        "stage_note": stage_note,
        "last_sync": _last_updated,
    }


def _current_stage_next_action():
    """Return the next action the operator should take based on current state."""
    processed_sites = st.session_state.get("processed_sites", [])
    uploaded_count = int(st.session_state.get("_last_uploaded_file_count", 0) or 0)

    if not uploaded_count:
        return "Upload survey photos to start intake."
    if not processed_sites:
        return "Wait for EXIF clustering and site detection to complete."
    if not st.session_state.get("agency_name") and not st.session_state.customer_info.get("agency_name"):
        return "Confirm the agency name and address."
    if not st.session_state.get("drive_folder_url"):
        return "Review sites and generate the deployment report."
    return "Sync the final report package to Drive."


def render_poc_table(contacts: list):
    """
    Render a POC table organized by role.

    Takes a list of contacts with poc_role assigned and displays them in a table
    with one row per POC role. Shows "DNA" if no contact matches a role.

    Args:
        contacts: List of contact dicts with keys: name, email, title, phone, poc_role
    """
    poc_roles = [
        "Information Technology",
        "Facilities Engineer",
        "Radio Shop Engineer",
        "RTCC/RTIC",
        "Crane Contractor",
        "Tower Climber Contractor",
        "BRINC Project Manager",
        "Other"
    ]

    rows = []
    for role in poc_roles:
        # Find first contact matching this role
        matching = [c for c in contacts if c.get("poc_role") == role]
        if matching:
            contact = matching[0]
            rows.append({
                "Role": role,
                "Name": contact.get("name", "DNA"),
                "Phone": contact.get("phone", "DNA"),
                "Email": contact.get("email", "DNA"),
                "Title": contact.get("title", "DNA")
            })
        else:
            rows.append({
                "Role": role,
                "Name": "DNA",
                "Phone": "DNA",
                "Email": "DNA",
                "Title": "DNA"
            })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


def render_drive_docs_table(docs: list):
    """
    Render a Drive documents table.

    Shows document name, owner, and last modified date. If no documents,
    displays an info message.

    Args:
        docs: List of document dicts with keys: name, owner, last_modified, url
    """
    if not docs:
        st.info("No documents found for this department.")
        return

    rows = []
    for doc in docs:
        rows.append({
            "Document Name": doc.get("name", "Unknown"),
            "Owner": doc.get("owner", "Unknown"),
            "Last Modified": doc.get("last_modified", "Unknown")
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


def render_link_list(items: list, *, title_key: str, url_key: str, empty_message: str, detail_keys: list[str] | None = None):
    """Render a compact list of clickable links with optional detail text."""
    linked_items = [item for item in (items or []) if item.get(url_key)]
    if not linked_items:
        st.caption(empty_message)
        return

    for item in linked_items:
        title = escape(str(item.get(title_key, "Unknown")))
        url = item.get(url_key, "")
        st.markdown(f"- [{title}]({url})")
        details = [str(item.get(key, "")).strip() for key in (detail_keys or []) if str(item.get(key, "")).strip()]
        if details:
            st.caption(" | ".join(details))


def render_calendar_events_table(events: list):
    """
    Render a calendar events table.

    Shows event name, date, time, and attendee count. If no events,
    displays an info message.

    Args:
        events: List of event dicts with keys: name, date, time, attendee_count
    """
    if not events:
        st.info("No calendar events found for this department.")
        return

    rows = []
    for event in events:
        rows.append({
            "Event Name": event.get("name", "Unknown"),
            "Date": event.get("date", "Unknown"),
            "Time": event.get("time", "Unknown"),
            "Attendees": event.get("attendee_count", 0)
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, width="stretch", hide_index=True)


def _render_kpi_cards():
    """Render the top-level mission KPIs."""
    overview = _mission_overview()
    connected_sources = count_connected_sources(st.session_state)
    contacts_count = count_contacts(st.session_state)
    source_statuses = get_connected_source_statuses(
        st.session_state,
        google_authenticated=google_oauth.is_authenticated(),
        slack_configured=bool(st.session_state.get("_slack_webhook")),
    )
    cols = st.columns(4)
    metrics = [
        ("Loaded Sites", overview["sites"], None),
        ("Input Files", overview["files"], None),
        ("Contacts", contacts_count, None),
        ("Connected Sources", connected_sources, None),
    ]
    for col, (label, value, delta) in zip(cols, metrics):
        with col:
            st.metric(label, value, delta=delta)
    st.caption(
        "Connected source details: "
        + " | ".join(f"{name}: {status}" for name, status in source_statuses)
    )


def _render_workflow_tracker():
    """Render the mission progress tracker and next required action."""
    overview = _mission_overview()
    stage_order = ["Intake", "Ingest", "Review", "Sync", "Deploy"]
    completed = []
    for step in stage_order:
        if step == "Intake":
            completed.append(overview["files"] > 0 or overview["sites"] > 0)
        elif step == "Ingest":
            completed.append(overview["files"] > 0 and overview["sites"] > 0)
        elif step == "Review":
            completed.append(overview["sites"] > 0)
        elif step == "Sync":
            completed.append(overview["sites"] > 0 and overview["stage"] in ("Sync", "Deploy"))
        elif step == "Deploy":
            completed.append(overview["stage"] == "Deploy")

    pills = []
    for step, done in zip(stage_order, completed):
        cls = "workflow-step"
        if step == overview["stage"]:
            cls += " current"
        elif done:
            cls += " complete"
        pills.append(f'<span class="{cls}">{step}</span>')

    st.markdown(
        f"""
        <div class="enterprise-section">
            <h3>Mission Workflow</h3>
            <div class="workflow-roadmap">{''.join(pills)}</div>
            <div class="stage-callout">
                Current stage: {overview["stage"]} · Next action: {_current_stage_next_action()}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_primary_map_section():
    """Render the primary map and site summary block."""
    with st.container(border=True):
        st.subheader("Site Map")
        st.caption("Primary operational map for clustered survey sites and deployment readiness.")
        if st.session_state.processed_sites:
            sites = st.session_state.processed_sites
            center_lat = sum(s['latitude'] for s in sites) / len(sites)
            center_lon = sum(s['longitude'] for s in sites) / len(sites)

            m = folium.Map(location=[center_lat, center_lon], zoom_start=13, tiles="CartoDB positron")

            if "city_boundary_geojson" not in st.session_state:
                detected = st.session_state.get("gps_detected_agency", {})
                city = detected.get("city", "")
                state = detected.get("state", "")
                geojson = reporter.query_city_boundary(city, state) if city else None
                st.session_state.city_boundary_geojson = geojson

            boundary = st.session_state.city_boundary_geojson
            if boundary:
                folium.GeoJson(
                    boundary,
                    name="City Boundary",
                    style_function=lambda _: {
                        "fillColor": "#3b82f6",
                        "color": "#1e40af",
                        "weight": 2.5,
                        "dashArray": "6 4",
                        "fillOpacity": 0.06,
                    },
                ).add_to(m)

            TWO_MILES_M = 3218.69

            def _make_circle_polygon(center_lat, center_lon, radius_m, num_points=36):
                """Create geographic circle using geodesic calculations."""
                from geopy.distance import geodesic
                points = []
                for bearing in range(0, 360, 360 // num_points):
                    edge = geodesic(meters=radius_m).destination((center_lat, center_lon), bearing)
                    points.append([edge.latitude, edge.longitude])
                points.append(points[0])
                return points

            for site in sites:
                lat, lon = site['latitude'], site['longitude']
                _parts = [p.strip() for p in site['address'].split(',')]
                label = ', '.join(_parts[:2]) if len(_parts) >= 2 else site['address']

                circle_coords = _make_circle_polygon(lat, lon, TWO_MILES_M)
                folium.PolyLine(
                    locations=circle_coords,
                    color="#ef4444",
                    weight=1.5,
                    opacity=0.8,
                    tooltip=f"2-mile radius — {label}",
                ).add_to(m)
                folium.Marker(
                    location=[lat, lon],
                    tooltip=label,
                    popup=f"<b>{site['site_id']}</b><br>{label}<br>Airspace: {site.get('airspace', 'N/A')}",
                    icon=folium.Icon(color="red", icon="tower-broadcast", prefix="fa"),
                ).add_to(m)

            st_folium(m, width=None, height=600, returned_objects=[])

            summary_cols = st.columns(3)
            with summary_cols[0]:
                st.metric("Sites Detected", len(sites))
            with summary_cols[1]:
                st.metric("Candidate Sites", len(st.session_state.get("candidate_sites", [])))
            with summary_cols[2]:
                st.metric("Agency", st.session_state.customer_info.get("agency_name", "Not set") or "Not set")
        else:
            st.info("No sites loaded. Upload survey photos to generate clustered sites and the mission map.")
            st.markdown(
                """
                <div style="
                    min-height: 600px;
                    border: 1px dashed #BFDBFE;
                    border-radius: 16px;
                    background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    color: #475569;
                    font-weight: 600;
                    text-align: center;
                    padding: 1rem;
                ">
                    Map will appear here after EXIF clustering completes.
                </div>
                """,
                unsafe_allow_html=True,
            )


# Header - compact banner with BRINC logo
import base64 as _b64

def _logo_b64():
    logo_path = os.path.join(APP_DIR, "images", "BRINC_Logo_White.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            return _b64.b64encode(f.read()).decode()
    return None

_logo_data = _logo_b64()
_logo_tag = f'<img src="data:image/png;base64,{_logo_data}" />' if _logo_data else ""

def _get_last_push_timestamp():
    """Get the last commit timestamp on main, formatted in CST."""
    try:
        ts = subprocess.check_output(
            ["git", "log", "-1", "--format=%ci", "main"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Parse the git timestamp (e.g. "2026-06-19 14:32:01 -0500")
        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S %z")
        return dt.astimezone(ZoneInfo("America/Chicago")).strftime("%m/%d/%Y %I:%M %p CST")
    except Exception:
        return "N/A"

_last_updated = _get_last_push_timestamp()

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

# Phase indicator
col_logo, col_phase = st.columns([1, 3])
with col_logo:
    pass  # Logo already renders above
with col_phase:
    st.markdown("---")
    _render_phase_indicator()

_overview = _mission_overview()
st.markdown(
    f"""
    <div class="mission-strip">
        <div class="mission-chip"><span class="label">Mission</span><span>{_overview["agency"]}</span></div>
        <div class="mission-chip"><span class="label">Sites</span><span>{_overview["sites"]}</span></div>
        <div class="mission-chip"><span class="label">Files</span><span>{_overview["files"]}</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar - Settings & Integration Configs
with st.sidebar:
    _sidebar_activity_placeholder = st.empty()
    _render_sidebar_activity()
    st.image(os.path.join(APP_DIR, "images", "BRINC_Logo_White.png"), width=120)
    output_dir = _resolve_app_path("./processed_sites")
    proximity_radius = 90

    with st.expander("Advanced Integrations / API Configurations", expanded=False):
        hubspot_api = st.text_input("HubSpot Access Token", type="password",
                                     value=st.secrets.get("HUBSPOT_ACCESS_TOKEN", ""))
        jira_url = st.text_input("Jira Server URL",
                                  value=st.secrets.get("JIRA_URL", "https://brincdrones.atlassian.net"))
        jira_email = st.text_input("Jira Email",
                                    value=st.secrets.get("JIRA_EMAIL", ""))
        jira_token = st.text_input("Jira API Token", type="password",
                                    value=st.secrets.get("JIRA_API_TOKEN", ""))
        slack_webhook = st.text_input("Slack Webhook URL", type="password")
        gdrive_folder = st.text_input("Google Drive Folder ID")
        # Store in session state so search functions can access them
        st.session_state["_hubspot_token"] = hubspot_api
        st.session_state["_jira_url"] = jira_url
        st.session_state["_jira_email"] = jira_email
        st.session_state["_jira_token"] = jira_token
        st.session_state["_slack_webhook"] = slack_webhook

    st.info("💡 Mocks are enabled automatically for unset credentials.")

    st.divider()
    st.subheader("Google Account")
    user_email = google_oauth.get_user_email()
    if user_email:
        st.success(f"Signed in as {user_email}")
        if st.button("Sign Out", width="stretch"):
            st.session_state.pop("google_oauth_token", None)
            st.session_state.pop("google_oauth_email", None)
            google_oauth._delete_token_file()
            st.rerun()
    else:
        google_oauth.render_connect_button()

    st.divider()
    with st.expander("Previous Sessions", expanded=False):
        resolved_output_dir = _resolve_app_path(output_dir)
        if os.path.exists(resolved_output_dir):
            subdirs = [
                d for d in os.listdir(resolved_output_dir)
                if os.path.isdir(os.path.join(resolved_output_dir, d))
                and d != "__pycache__"
                and d != "Unclassified_No_GPS"
            ]

            def _session_created_at(folder_name):
                timestamp_match = re.search(r"(\d{8}_\d{6})$", folder_name)
                if timestamp_match:
                    try:
                        return datetime.datetime.strptime(timestamp_match.group(1), "%Y%m%d_%H%M%S")
                    except ValueError:
                        pass
                try:
                    return datetime.datetime.fromtimestamp(os.path.getctime(os.path.join(resolved_output_dir, folder_name)))
                except Exception:
                    return datetime.datetime.min

            if subdirs:
                for d in sorted(subdirs, key=_session_created_at, reverse=True):
                    meta_file = os.path.join(resolved_output_dir, d, "session_metadata.json")
                    display_name = None

                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, "r") as mf:
                                loaded_metadata = json.load(mf)
                            if "customer_info" in loaded_metadata and loaded_metadata["customer_info"].get("agency_name"):
                                display_name = loaded_metadata["customer_info"]["agency_name"]
                        except Exception:
                            pass

                    if not display_name:
                        display_name = d.replace("Site_1_", "").replace("Site_2_", "").replace("Site_3_", "").replace("_", " ").replace("Site-001", "").replace("Site-002", "")
                        if "Lansing" in display_name:
                            display_name = "Lansing Illinois Police"

                    if st.button(display_name, key=f"sidebar_prev_sess_btn_{d}", width="stretch"):
                        if os.path.exists(meta_file):
                            try:
                                with open(meta_file, "r") as mf:
                                    loaded_site = json.load(mf)
                                st.session_state.processed_sites = [loaded_site]
                                if loaded_site.get("images"):
                                    st.session_state.active_bg_image = loaded_site["images"][0]["filename"]
                                if "customer_info" in loaded_site:
                                    st.session_state.customer_info = loaded_site["customer_info"]
                                loaded_contacts = loaded_site.get("agency_contacts", [])
                                if not loaded_contacts:
                                    loaded_contacts = st.session_state.customer_info.get("contacts", [])
                                st.session_state.agency_contacts = loaded_contacts
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

# Ingestion Controls
# Get Drive manager once up front (returns None if not authenticated)
drive = get_drive_manager()
team_folder_id = st.secrets.get('GOOGLE_DRIVE_TEAM_FOLDER_ID', None)

def _on_files_changed():
    """Reset GPS detection and processing flag when the user changes files."""
    st.session_state.pop("gps_detected_agency", None)
    st.session_state.pop("_auto_processed", None)
    st.session_state.pop("_upload_processing_complete", None)
    st.session_state.pop("_upload_processing_state", None)
    st.session_state.pop("_upload_processing_summary", None)
    st.session_state.pop("city_boundary_geojson", None)
    st.session_state.pop("candidate_sites", None)

def _render_survey_upload_block(current_proximity_radius: int, compact: bool = False, upload_complete: bool = False):
    """Render the survey upload controls in either full or compact form."""
    expander_label = "Upload Survey Photos (Complete)" if compact and upload_complete else "Upload Survey Photos"
    container = st.expander(expander_label, expanded=False) if compact else st.container(border=True)
    with container:
        if compact:
            st.caption("Uploads finished. Expand to add more photos." if upload_complete else "Collapsed intake panel")
        else:
            st.subheader("Upload Survey Photos")
            st.caption("Drag raw survey photos to start GPS detection, EXIF clustering, and site ingestion.")

        proximity_radius = st.slider(
            "🛰️ Clustering Proximity (Meters)",
            min_value=10,
            max_value=500,
            value=current_proximity_radius,
            help="Controls how tightly photos must cluster before they are treated as the same site.",
        )
        uploaded_files = st.file_uploader(
            "Upload raw survey photos (.jpg, .jpeg, .png)",
            accept_multiple_files=True,
            type=["jpg", "jpeg", "png", "heic"],
            on_change=_on_files_changed,
            key="survey_photo_upload",
            label_visibility="collapsed" if compact else "visible",
        )
        st.session_state["_last_uploaded_file_count"] = len(uploaded_files) if uploaded_files else 0

        if uploaded_files:
            if "gps_detected_agency" not in st.session_state:
                with st.spinner("Detecting location from photo GPS data..."):
                    for uf in uploaded_files:
                        detection = _detect_agency_from_gps(uf.getvalue(), uf.name)
                        if detection and detection.get("agency_name"):
                            st.session_state.gps_detected_agency = detection
                            agency = detection["agency_name"]
                            st.session_state.customer_info["agency_name"] = agency
                            st.session_state.customer_info["agency_address"] = reporter._format_short_address(detection.get("address", ""))
                            st.session_state["_pending_agency_widget_sync"] = {
                                "agency_name": agency,
                                "agency_address": st.session_state.customer_info["agency_address"],
                            }
                            break
                    else:
                        st.session_state.gps_detected_agency = {}

            # Trigger parallel agency docs lookup once per agency name.
            agency_name = st.session_state.customer_info.get("agency_name", "").strip()
            last_doc_search_agency = st.session_state.get("_last_doc_search_agency", "")
            if agency_name and agency_name != last_doc_search_agency and not st.session_state.agency_docs_loading:
                st.session_state.agency_docs_loading = True
                try:
                    _set_sidebar_activity(
                        "Looking up connected docs",
                        f"Preparing searches for {agency_name}.",
                    )
                    # Extract domain from agency address or leave empty
                    agency_address = st.session_state.customer_info.get("agency_address", "")
                    city_hint = processor.extract_city_from_address(agency_address) if agency_address else ""
                    dept_domain = ""  # Domain is not reliably derivable from the address alone

                    # Run Gmail lookup first so contacts are available even if the
                    # slower multi-source harvest times out later.
                    _set_sidebar_activity(
                        "Looking up connected docs",
                        f"Searching Gmail contacts for {agency_name}.",
                    )
                    gmail_result = _lookup_contacts_from_gmail(agency_name, city_hint or None)
                    if gmail_result and gmail_result.get("status") == "connected":
                        found_contacts = gmail_result.get("all_contacts", [])
                        if found_contacts:
                            st.session_state["gmail_found_contacts"] = found_contacts
                            st.session_state.agency_contacts = found_contacts
                        for key in ("poc_name", "poc_email", "poc_phone", "it_director", "it_email"):
                            if gmail_result.get(key):
                                st.session_state.customer_info[key] = gmail_result[key]

                    # Call parallel fetch in blocking context (will complete before rerun)
                    _set_sidebar_activity(
                        "Looking up connected docs",
                        f"Searching Drive, Calendar, and department contacts for {agency_name}.",
                    )
                    result = fetch_agency_docs_parallel(
                        agency_name,
                        dept_domain,
                        st.session_state,
                        city_hint=city_hint,
                    )

                    # Store results atomically
                    parallel_contacts = result.get("contacts", [])
                    if parallel_contacts:
                        st.session_state.agency_contacts = parallel_contacts
                    st.session_state.agency_docs = result.get("docs", [])
                    st.session_state.agency_calendar = result.get("events", [])
                    st.session_state.agency_docs_errors = result.get("errors", {})
                    _set_sidebar_activity(
                        "Connected docs lookup complete",
                        f"Finished searching connected systems for {agency_name}.",
                        state="complete",
                    )
                except Exception as e:
                    st.session_state.agency_docs_errors["fetch"] = str(e)
                    _set_sidebar_activity(
                        "Connected docs lookup failed",
                        str(e),
                        state="error",
                    )
                finally:
                    st.session_state.agency_docs_loading = False
                    st.session_state._last_doc_search_agency = agency_name

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
        else:
            client_name = "Untitled_Site_Survey"

        if uploaded_files:
            st.info(f"{len(uploaded_files)} file(s) queued for ingestion.")
        else:
            st.info("Upload survey photos to unlock contact and deployment fields.")

    return uploaded_files, client_name, proximity_radius

uploaded_files = st.session_state.get("survey_photo_upload")
client_name = "Untitled_Site_Survey"

# Always render upload block to show widget and get proximity_radius
# (compact mode when files already exist)
compact_mode = uploaded_files is not None
upload_complete = st.session_state.get("_upload_processing_complete", False)
uploaded_files, client_name, proximity_radius = _render_survey_upload_block(
    proximity_radius,
    compact=compact_mode,
    upload_complete=upload_complete
)

# Start ingestion immediately so the app does not render the rest of the
# dashboard in a stale pre-processing state.
if uploaded_files and not st.session_state.get("_auto_processed"):
    st.session_state._auto_processed = True
    _set_upload_processing_state("processing", file_count=len(uploaded_files))
    _set_phase("Processing photos", status="active")
    _set_sidebar_activity(
        "Processing survey photos",
        f"Preparing {len(uploaded_files)} uploaded file(s).",
    )

    with st.container(border=True):
        st.subheader("Processing Status")
        with st.status("Processing survey photos...", expanded=True) as status:
            _step_placeholder = status.empty()
            _detail_placeholder = status.empty()

            def _update_processing_progress(percent, message):
                status.update(label=f"Processing - {int(percent)}%")
                _detail_placeholder.write(f"⏳ {message}")
                _set_sidebar_activity(
                    f"Processing survey photos ({int(percent)}%)",
                    message,
                )

            try:
                st.session_state.processed_sites = []
                st.session_state.active_bg_image = None
                st.session_state.last_click = {}

                _step_placeholder.write(f"📂 Saving {len(uploaded_files)} uploaded file(s) to disk...")
                _set_sidebar_activity(
                    "Processing survey photos",
                    f"Saving {len(uploaded_files)} uploaded file(s) to disk.",
                )
                temp_dir = tempfile.mkdtemp(prefix="dfr_ingest_")
                image_paths_for_processing = []
                for uploaded_file in uploaded_files:
                    temp_path = os.path.join(temp_dir, uploaded_file.name)
                    with open(temp_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    image_paths_for_processing.append(temp_path)
                st.session_state.image_paths = image_paths_for_processing

                proc_drive = None
                try:
                    proc_drive = get_drive_manager()
                except Exception:
                    pass

                _set_phase("Processing photos", status="active")
                _step_placeholder.write("🔍 Extracting EXIF metadata and clustering by GPS...")
                _set_sidebar_activity(
                    "Processing survey photos",
                    "Extracting EXIF metadata and clustering images by GPS.",
                )
                site_data = processor.process_and_organize_images(
                    source_dir=temp_dir,
                    output_dir=output_dir,
                    radius_meters=proximity_radius,
                    progress_callback=_update_processing_progress,
                    image_paths=image_paths_for_processing,
                    drive_manager=proc_drive,
                    drive_output_folder_id=st.session_state.get('processed_folder_id'),
                    agency_name=st.session_state.customer_info.get("agency_name"),
                )

                if not site_data:
                    st.warning("No images with GPS metadata were found in the uploaded files.")

                _step_placeholder.write(f"🏗️ Analyzing infrastructure for {len(site_data)} site(s)...")
                _set_sidebar_activity(
                    "Analyzing detected sites",
                    f"Running infrastructure analysis for {len(site_data)} site(s).",
                )
                for i, site in enumerate(site_data):
                    status.update(label=f"Analyzing site {i+1}/{len(site_data)}")
                    _step_placeholder.write(f"🔎 Site {i+1}: Running infrastructure detection...")
                    _set_sidebar_activity(
                        f"Analyzing site {i+1}/{len(site_data)}",
                        "Running infrastructure detection.",
                    )
                    site["analysis"] = analyzer.analyze_site(site)
                    _step_placeholder.write(f"✈️ Site {i+1}: Querying airspace & airfield data...")
                    _set_sidebar_activity(
                        f"Analyzing site {i+1}/{len(site_data)}",
                        "Querying airspace and nearest airfield data.",
                    )
                    airfield = reporter.query_nearest_airfield(site['latitude'], site['longitude'])
                    site["airfield_info"] = f"{airfield[0]} ({airfield[1]:.2f} miles)" if airfield else "Lookup failed"
                    airspace = reporter.query_airspace_class(site["latitude"], site["longitude"])
                    site["airspace"] = airspace if airspace else "Lookup failed"
                    for img in site.get("images", []):
                        if "selected_for_report" not in img:
                            img["selected_for_report"] = True

                st.session_state.processed_sites = site_data

                survey_date = _derive_survey_date_from_sites(site_data)
                surveyor = google_oauth.get_user_email() or st.session_state.customer_info.get("surveyor", "")

                if site_data:
                    first_site = site_data[0]
                    first_address = first_site.get("address", "")
                    agency_name = first_site.get("agency_name") or f"{_extract_town_state_from_address(first_address)[0]} Police Department"

                    existing = st.session_state.customer_info
                    st.session_state.customer_info = {
                        "agency_name": agency_name,
                        "agency_address": reporter._format_short_address(first_address),
                        "poc_name": existing.get("poc_name", ""),
                        "poc_email": existing.get("poc_email", ""),
                        "poc_phone": existing.get("poc_phone", ""),
                        "it_director": existing.get("it_director", ""),
                        "it_email": existing.get("it_email", ""),
                        "facilities_engineer": existing.get("facilities_engineer", ""),
                        "facilities_email": existing.get("facilities_email", ""),
                        "rtcc_name": existing.get("rtcc_name", ""),
                        "rtcc_email": existing.get("rtcc_email", ""),
                        "radio_shop_name": existing.get("radio_shop_name", ""),
                        "radio_shop_email": existing.get("radio_shop_email", ""),
                        "crane_contractor": existing.get("crane_contractor", ""),
                        "tower_climber_contractor": existing.get("tower_climber_contractor", ""),
                        "brinc_pm": existing.get("brinc_pm", ""),
                        "contacts": existing.get("contacts", []),
                        "survey_delivery_target": existing.get("survey_delivery_target", ""),
                        "power_circuit_requirements": existing.get("power_circuit_requirements", ""),
                        "internet_ethernet_access": existing.get("internet_ethernet_access", ""),
                        "follow_up_requirements": existing.get("follow_up_requirements", ""),
                        "action_items": existing.get("action_items", ""),
                        "survey_date": survey_date,
                        "report_date": datetime.datetime.strptime(survey_date, "%Y-%m-%d").strftime("%B %d, %Y") if survey_date else existing.get("report_date", ""),
                        "surveyor": surveyor,
                    }
                    st.session_state["_pending_agency_widget_sync"] = {
                        "agency_name": agency_name,
                        "agency_address": st.session_state.customer_info["agency_address"],
                    }
                    city = processor.extract_city_from_address(first_address) if first_address else ""
                    st.session_state.gps_detected_agency = {
                        **st.session_state.get("gps_detected_agency", {}),
                        "agency_name": agency_name,
                        "city": city,
                    }
                    _save_session_metadata(site_data)

                st.session_state.candidate_sites = []
                if site_data:
                    status.update(label="Building candidate sites...")
                    _set_sidebar_activity(
                        "Building candidate sites",
                        "Creating candidate-site models from processed survey sites.",
                    )
                    st.session_state.candidate_sites = [
                        CandidateSite.from_site_dict(s) for s in site_data
                        if len(s.get("images", [])) >= MIN_SITE_PHOTOS
                    ]

                    total_cs = len(st.session_state.candidate_sites)
                    for cs_idx, cs in enumerate(st.session_state.candidate_sites, start=1):
                        status.update(label=f"Enriching site {cs_idx}/{total_cs} with GIS data...")
                        _set_sidebar_activity(
                            f"Enriching site {cs_idx}/{total_cs}",
                            "Pulling GIS context and infrastructure overlays.",
                        )

                        def _gis_progress(step, _idx=cs_idx, _total=total_cs):
                            _step_placeholder.write(f"🌐 Site {_idx}/{_total}: {step}")
                            _set_sidebar_activity(
                                f"Enriching site {_idx}/{_total}",
                                step,
                            )

                        enrich_gis(cs, progress_callback=_gis_progress)

                status.update(label="Finalizing map and dashboard...", expanded=True)
                _set_sidebar_activity(
                    "Finalizing survey workspace",
                    "Rendering the site map and post-processing workspace.",
                )
                _set_upload_processing_state(
                    "finalizing",
                    site_count=len(site_data),
                    file_count=len(uploaded_files),
                )
                st.rerun()
            except Exception as e:
                status.update(label="Processing failed", state="error")
                _set_upload_processing_state("error", file_count=len(uploaded_files))
                _set_sidebar_activity("Processing failed", str(e), state="error")
                st.error(f"Processing failed: {e}")

if st.session_state.processed_sites:
    if "_poc_uid_counter" not in st.session_state:
        st.session_state._poc_uid_counter = 0

    def _next_poc_uid():
        st.session_state._poc_uid_counter += 1
        return st.session_state._poc_uid_counter

    if "poc_rows" not in st.session_state:
        st.session_state.poc_rows = build_initial_poc_rows(
            st.session_state.customer_info,
            _next_poc_uid,
        )

    st.session_state.poc_rows = sync_customer_info_from_poc_rows(
        st.session_state.customer_info,
        st.session_state.poc_rows,
        widget_state=st.session_state,
    )

# Mission workspace
_overview = _mission_overview()
_render_kpi_cards()
_render_workflow_tracker()
_render_primary_map_section()

with st.container(border=True):
    st.subheader("Agency Information")
    agency_tabs = st.tabs(["Agency", "Contacts", "Deployment", "Documents"])

    with agency_tabs[0]:
        col_a1, col_a2 = st.columns([2, 1])
        with col_a1:
            pending_agency_sync = st.session_state.pop("_pending_agency_widget_sync", None)
            if pending_agency_sync:
                st.session_state["_widget_agency_name"] = pending_agency_sync.get(
                    "agency_name", st.session_state.customer_info.get("agency_name", "")
                )
                st.session_state["_widget_agency_address"] = pending_agency_sync.get(
                    "agency_address", st.session_state.customer_info.get("agency_address", "")
                )
            elif "_widget_agency_name" not in st.session_state:
                st.session_state["_widget_agency_name"] = st.session_state.customer_info.get("agency_name", "")
            if "_widget_agency_address" not in st.session_state:
                st.session_state["_widget_agency_address"] = st.session_state.customer_info.get("agency_address", "")
            st.session_state.customer_info["agency_name"] = st.text_input("Agency Name", key="_widget_agency_name")
            st.session_state.customer_info["agency_address"] = st.text_input("Agency Address", key="_widget_agency_address")
        with col_a2:
            st.markdown("**Connected Docs**")
            if google_oauth.is_authenticated():
                agency = st.session_state.customer_info.get("agency_name", "")
                if st.button("🔄 Refresh Connected Docs", width="stretch"):
                    if not agency:
                        st.warning("Enter or detect an Agency Name first.")
                    else:
                        city_hint = ""
                        agency_address = st.session_state.customer_info.get("agency_address", "")
                        if agency_address:
                            city_hint = processor.extract_city_from_address(agency_address) or ""
                        with st.spinner("Refreshing connected docs..."):
                            _run_connected_docs_search(agency, city_hint)
                        st.rerun()
            else:
                google_oauth.render_connect_button("Connect Google for Gmail & Drive Lookup")

        summary_cols = st.columns(3)
        with summary_cols[0]:
            st.metric("Mission", st.session_state.customer_info.get("agency_name", "Not set") or "Not set")
        with summary_cols[1]:
            st.metric("Address", st.session_state.customer_info.get("agency_address", "Not set") or "Not set")
        with summary_cols[2]:
            st.metric("Contacts", len(st.session_state.customer_info.get("contacts", [])))

    with agency_tabs[1]:
        st.markdown("**Connected POCs**")
        agency_contacts = st.session_state.get("agency_contacts", [])
        if agency_contacts:
            render_poc_table(agency_contacts)
            st.markdown("**Connected Contact Feed**")
            connected_contacts_df = pd.DataFrame(agency_contacts)
            if not connected_contacts_df.empty:
                st.dataframe(connected_contacts_df, width="stretch", hide_index=True)
        elif st.session_state.get("agency_docs_loading"):
            st.info("Connected docs lookup in progress.")
        else:
            st.info("No connected contacts found yet.")

        st.markdown("**Manual Contacts**")
        contacts_df = pd.DataFrame(st.session_state.customer_info.get("contacts", []))
        if not contacts_df.empty:
            st.dataframe(contacts_df, width="stretch", hide_index=True)
        else:
            st.info("No manual contacts loaded yet. Use the Survey Pipeline tab or Gmail lookup to populate contacts.")
        st.caption("Contact editing remains available in the Survey Pipeline for compatibility.")

    with agency_tabs[2]:
        dep_cols = st.columns(3)
        with dep_cols[0]:
            st.session_state.customer_info["survey_delivery_target"] = st.text_input(
                "Survey / Delivery Target",
                value=st.session_state.customer_info.get("survey_delivery_target", ""),
                placeholder="e.g. Week of September 28, 2026",
                key="agency_tab_survey_delivery_target",
            )
        with dep_cols[1]:
            st.session_state.customer_info["power_circuit_requirements"] = st.text_input(
                "Power Circuit Requirements",
                value=st.session_state.customer_info.get("power_circuit_requirements", ""),
                placeholder="e.g. 120V / 20A Dedicated Circuit",
                key="agency_tab_power_circuit_requirements",
            )
        with dep_cols[2]:
            st.session_state.customer_info["internet_ethernet_access"] = st.text_input(
                "Internet / Ethernet Access",
                value=st.session_state.customer_info.get("internet_ethernet_access", ""),
                placeholder="e.g. DHCP on isolated VLAN",
                key="agency_tab_internet_ethernet_access",
            )

        dep_cols2 = st.columns(3)
        with dep_cols2[0]:
            st.session_state.customer_info["crane_contractor"] = st.text_input(
                "Crane Contractor",
                value=st.session_state.customer_info.get("crane_contractor", ""),
                placeholder="e.g. Pending crane company",
                key="agency_tab_crane_contractor",
            )
        with dep_cols2[1]:
            st.session_state.customer_info["tower_climber_contractor"] = st.text_input(
                "Tower Climber Contractor",
                value=st.session_state.customer_info.get("tower_climber_contractor", ""),
                placeholder="e.g. DNA",
                key="agency_tab_tower_climber_contractor",
            )
        with dep_cols2[2]:
            st.session_state.customer_info["brinc_pm"] = st.text_input(
                "BRINC Project Manager",
                value=st.session_state.customer_info.get("brinc_pm", ""),
                placeholder="e.g. steven.beltran@brincdrones.com",
                key="agency_tab_brinc_pm",
            )

        dep_cols3 = st.columns(2)
        with dep_cols3[0]:
            st.session_state.customer_info["follow_up_requirements"] = st.text_input(
                "Follow-up Requirements",
                value=st.session_state.customer_info.get("follow_up_requirements", ""),
                placeholder="e.g. Infrastructure for site needs to be completed",
                key="agency_tab_follow_up_requirements",
            )
        with dep_cols3[1]:
            st.session_state.customer_info["action_items"] = st.text_input(
                "Action Items",
                value=st.session_state.customer_info.get("action_items", ""),
                placeholder="e.g. Confirm ethernet and power 30 days before install",
                key="agency_tab_action_items",
            )

    with agency_tabs[3]:
        docs_cols = st.columns(2)
        with docs_cols[0]:
            st.markdown("**Drive / Notes**")
            drive_data = st.session_state.get("drive_gemini_results")
            if drive_data and drive_data.get("status") == "connected":
                for note in drive_data.get("gemini_notes", [])[:5]:
                    title = note.get("title", "Untitled")
                    url = note.get("url", "")
                    if url:
                        st.markdown(f"- [{title}]({url})")
                    else:
                        st.caption(f"- {title}")
            else:
                st.caption("No connected documents yet.")
            st.markdown("**Document Links**")
            render_link_list(
                st.session_state.get("agency_docs", []),
                title_key="name",
                url_key="url",
                empty_message="No linked documents yet.",
                detail_keys=["owner", "last_modified"],
            )
            st.markdown("**Drive Search Results**")
            render_drive_docs_table(st.session_state.get("agency_docs", []))
        with docs_cols[1]:
            st.markdown("**Connected Sources**")
            source_statuses = get_connected_source_statuses(
                st.session_state,
                google_authenticated=google_oauth.is_authenticated(),
                slack_configured=bool(st.session_state.get("_slack_webhook")),
            )
            source_cols = st.columns(2)
            for index, (name, status) in enumerate(source_statuses):
                with source_cols[index % 2]:
                    st.metric(name, status)
            st.markdown("**Calendar Event Links**")
            render_link_list(
                st.session_state.get("agency_calendar", []),
                title_key="name",
                url_key="url",
                empty_message="No linked calendar events yet.",
                detail_keys=["date", "time"],
            )
            st.markdown("**Calendar Events**")
            render_calendar_events_table(st.session_state.get("agency_calendar", []))
            if st.session_state.get("agency_docs_errors"):
                st.caption(f"Lookup issues: {st.session_state.agency_docs_errors}")

# Auto-process on upload - runs once per file set, no manual button needed
if uploaded_files and not st.session_state.get("_auto_processed"):
    st.session_state._auto_processed = True
    _set_upload_processing_state("processing", file_count=len(uploaded_files))

    with st.container(border=True):
        st.subheader("Processing Status")
        with st.status("Processing survey photos...", expanded=True) as status:
            _step_placeholder = status.empty()
            _detail_placeholder = status.empty()
            def _update_processing_progress(percent, message):
                status.update(label=f"Processing - {int(percent)}%")
                _detail_placeholder.write(f"⏳ {message}")

            try:
                st.session_state.processed_sites = []
                st.session_state.active_bg_image = None
                st.session_state.last_click = {}

                # Save uploaded files to disk so the processor can read them
                _step_placeholder.write(f"📂 Saving {len(uploaded_files)} uploaded file(s) to disk...")
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

                _step_placeholder.write("🔍 Extracting EXIF metadata and clustering by GPS...")
                site_data = processor.process_and_organize_images(
                    source_dir=temp_dir,
                    output_dir=output_dir,
                    radius_meters=proximity_radius,
                    progress_callback=_update_processing_progress,
                    image_paths=image_paths_for_processing,
                    drive_manager=proc_drive,
                    drive_output_folder_id=st.session_state.get('processed_folder_id'),
                    agency_name=st.session_state.customer_info.get("agency_name"),
                )

                if not site_data:
                    st.warning("No images with GPS metadata were found in the uploaded files.")

                _step_placeholder.write(f"🏗️ Analyzing infrastructure for {len(site_data)} site(s)...")
                for i, site in enumerate(site_data):
                    status.update(label=f"Analyzing site {i+1}/{len(site_data)}")
                    _step_placeholder.write(f"🔎 Site {i+1}: Running infrastructure detection...")
                    site["analysis"] = analyzer.analyze_site(site)
                    _step_placeholder.write(f"✈️ Site {i+1}: Querying airspace & airfield data...")
                    airfield = reporter.query_nearest_airfield(site['latitude'], site['longitude'])
                    site["airfield_info"] = f"{airfield[0]} ({airfield[1]:.2f} miles)" if airfield else "Lookup failed"
                    airspace = reporter.query_airspace_class(site["latitude"], site["longitude"])
                    site["airspace"] = airspace if airspace else "Lookup failed"
                    for img in site.get("images", []):
                        if "selected_for_report" not in img:
                            img["selected_for_report"] = True

                st.session_state.processed_sites = site_data

                survey_date = _derive_survey_date_from_sites(site_data)
                surveyor = google_oauth.get_user_email() or st.session_state.customer_info.get("surveyor", "")

                # Auto-populate customer info from metadata
                if site_data:
                    first_site = site_data[0]
                    first_address = first_site.get("address", "")
                    agency_name = first_site.get("agency_name") or f"{_extract_town_state_from_address(first_address)[0]} Police Department"

                    existing = st.session_state.customer_info
                    st.session_state.customer_info = {
                        "agency_name": agency_name,
                        "agency_address": reporter._format_short_address(first_address),
                        "poc_name": existing.get("poc_name", ""),
                        "poc_email": existing.get("poc_email", ""),
                        "poc_phone": existing.get("poc_phone", ""),
                        "it_director": existing.get("it_director", ""),
                        "it_email": existing.get("it_email", ""),
                        "facilities_engineer": existing.get("facilities_engineer", ""),
                        "facilities_email": existing.get("facilities_email", ""),
                        "rtcc_name": existing.get("rtcc_name", ""),
                        "rtcc_email": existing.get("rtcc_email", ""),
                        "radio_shop_name": existing.get("radio_shop_name", ""),
                        "radio_shop_email": existing.get("radio_shop_email", ""),
                        "crane_contractor": existing.get("crane_contractor", ""),
                        "tower_climber_contractor": existing.get("tower_climber_contractor", ""),
                        "brinc_pm": existing.get("brinc_pm", ""),
                        "contacts": existing.get("contacts", []),
                        "survey_delivery_target": existing.get("survey_delivery_target", ""),
                        "power_circuit_requirements": existing.get("power_circuit_requirements", ""),
                        "internet_ethernet_access": existing.get("internet_ethernet_access", ""),
                        "follow_up_requirements": existing.get("follow_up_requirements", ""),
                        "action_items": existing.get("action_items", ""),
                        "survey_date": survey_date,
                        "report_date": datetime.datetime.strptime(survey_date, "%Y-%m-%d").strftime("%B %d, %Y") if survey_date else existing.get("report_date", ""),
                        "surveyor": surveyor,
                    }
                    # Defer widget sync until the next rerun, before the inputs are instantiated.
                    st.session_state["_pending_agency_widget_sync"] = {
                        "agency_name": agency_name,
                        "agency_address": st.session_state.customer_info["agency_address"],
                    }
                    # Update gps_detected_agency to match the final resolved name
                    city = processor.extract_city_from_address(first_address) if first_address else ""
                    st.session_state.gps_detected_agency = {
                        **st.session_state.get("gps_detected_agency", {}),
                        "agency_name": agency_name,
                        "city": city,
                    }
                    _save_session_metadata(site_data)

                    # Connected docs search is handled by the auto-trigger after rerun
                    # (see col_c2 auto-trigger block that fires when agency name changes)

                # Convert to CandidateSite objects
                st.session_state.candidate_sites = []
                if site_data:
                    status.update(label="Building candidate sites...")
                    st.session_state.candidate_sites = [
                        CandidateSite.from_site_dict(s) for s in site_data
                        if len(s.get("images", [])) >= MIN_SITE_PHOTOS
                    ]

                    total_cs = len(st.session_state.candidate_sites)
                    for cs_idx, cs in enumerate(st.session_state.candidate_sites, start=1):
                        status.update(label=f"Enriching site {cs_idx}/{total_cs} with GIS data...")
                        def _gis_progress(step, _idx=cs_idx, _total=total_cs):
                            _step_placeholder.write(f"🌐 Site {_idx}/{_total}: {step}")
                        enrich_gis(cs, progress_callback=_gis_progress)

                status.update(label="Finalizing map and dashboard...", expanded=True)
                _set_sidebar_activity(
                    "Finalizing survey workspace",
                    "Rendering the site map and post-processing workspace.",
                )
                _set_upload_processing_state(
                    "finalizing",
                    site_count=len(site_data),
                    file_count=len(uploaded_files),
                )
                st.rerun()
            except Exception as e:
                status.update(label="Processing failed", state="error")
                _set_upload_processing_state("error", file_count=len(uploaded_files))
                st.error(f"Processing failed: {e}")

def _render_site_checklist(site, site_idx):
    """Render a unified checklist card for a CandidateSite."""
    prov = site.checklist_provenance

    def _indicator(field_id):
        if prov.get(field_id) == "auto":
            return "✅"
        return "⚠️"

    with st.expander(f"📋 Site {site_idx}: {site.identity.site_name} — {site.identity.site_address}", expanded=False):
        st.markdown(f"**Site ID:** {site.identity.site_id}")
        st.markdown(f"**Coordinates:** {site.identity.site_latitude:.6f}, {site.identity.site_longitude:.6f}")
        if site.identity.site_elevation:
            st.markdown(f"**Elevation:** {site.identity.site_elevation:.1f} ft {_indicator('SITE_ELEVATION')}")

        st.markdown("---")

        # Access
        st.markdown("#### Access")
        col1, col2 = st.columns(2)
        with col1:
            site.access.access_type = st.selectbox(
                "Access Type", ["", "Stairs", "Ladder", "Elevator", "Roof Hatch"],
                index=0, key=f"access_type_{site_idx}")
            site.access.escort_required = st.checkbox(
                "Escort Required", value=bool(site.access.escort_required),
                key=f"escort_{site_idx}")
            site.access.key_required = st.checkbox(
                "Key Required", value=bool(site.access.key_required),
                key=f"key_{site_idx}")
        with col2:
            site.access.roof_access = st.selectbox(
                "Roof Access", ["", "Roof Hatch", "Exterior Ladder", "Interior Stairs", "Elevator"],
                index=0, key=f"roof_access_{site_idx}")
            site.access.after_hours_access = st.checkbox(
                "After Hours Access", value=bool(site.access.after_hours_access),
                key=f"after_hours_{site_idx}")
            site.access.parking_available = st.checkbox(
                "Parking Available", value=bool(site.access.parking_available),
                key=f"parking_{site_idx}")

        st.markdown("---")

        # Structural
        st.markdown("#### Structural")
        col1, col2 = st.columns(2)
        with col1:
            site.structure.building_height = st.number_input(
                f"Building Height (ft) {_indicator('BUILDING_HEIGHT')}",
                value=float(site.structure.building_height or 0),
                min_value=0.0, step=1.0, key=f"bldg_height_{site_idx}")
            site.structure.roof_type = st.selectbox(
                "Roof Type",
                ["", "Flat Concrete", "EPDM / Rubber Membrane", "TPO / Single-ply Vinyl",
                 "Standing Seam Metal", "Tar and Gravel", "Pitched / Shingle"],
                index=0, key=f"roof_type_{site_idx}")
        with col2:
            site.structure.parapet_height = st.number_input(
                "Parapet Height (ft)", value=float(site.structure.parapet_height or 0),
                min_value=0.0, step=0.5, key=f"parapet_{site_idx}")
            site.structure.roof_condition = st.selectbox(
                "Roof Condition", ["", "Good", "Fair", "Poor"],
                index=0, key=f"roof_cond_{site_idx}")

        st.markdown("---")

        # Electrical
        st.markdown("#### Electrical")
        col1, col2 = st.columns(2)
        with col1:
            site.electrical.power_available = st.checkbox(
                "Power Available", value=bool(site.electrical.power_available),
                key=f"power_{site_idx}")
            site.electrical.voltage_available = st.selectbox(
                "Voltage", ["", "120V", "208V", "240V", "480V"],
                index=0, key=f"voltage_{site_idx}")
            site.electrical.dedicated_circuit = st.checkbox(
                "Dedicated Circuit", value=bool(site.electrical.dedicated_circuit),
                key=f"ded_circuit_{site_idx}")
        with col2:
            site.electrical.breaker_available = st.checkbox(
                "Breaker Available", value=bool(site.electrical.breaker_available),
                key=f"breaker_{site_idx}")
            site.electrical.panel_location = st.text_input(
                "Panel Location", value=site.electrical.panel_location or "",
                key=f"panel_loc_{site_idx}")
            site.electrical.distance_to_power = st.number_input(
                "Distance to Power (ft)", value=float(site.electrical.distance_to_power or 0),
                min_value=0.0, step=1.0, key=f"dist_power_{site_idx}")

        st.markdown("---")

        # Network
        st.markdown("#### Network")
        col1, col2 = st.columns(2)
        with col1:
            site.network.isp_provider = st.text_input(
                "ISP Provider", value=site.network.isp_provider or "",
                key=f"isp_{site_idx}")
            site.network.download_speed = st.text_input(
                "Download Speed", value=site.network.download_speed or "",
                key=f"dl_speed_{site_idx}")
            site.network.static_ip_available = st.checkbox(
                "Static IP Available", value=bool(site.network.static_ip_available),
                key=f"static_ip_{site_idx}")
        with col2:
            site.network.connection_type = st.selectbox(
                "Connection Type", ["", "Fiber", "Cable", "DSL", "Cellular", "Satellite"],
                index=0, key=f"conn_type_{site_idx}")
            site.network.upload_speed = st.text_input(
                "Upload Speed", value=site.network.upload_speed or "",
                key=f"ul_speed_{site_idx}")
            site.network.switch_location = st.text_input(
                "Switch Location", value=site.network.switch_location or "",
                key=f"switch_loc_{site_idx}")

        st.markdown("---")

        # RF
        st.markdown("#### RF")
        col1, col2 = st.columns(2)
        with col1:
            site.rf.line_of_sight_status = st.selectbox(
                "Line of Sight", ["", "Clear", "Partial", "Obstructed"],
                index=0, key=f"los_{site_idx}")
            site.rf.obstruction_trees = st.checkbox("Trees", key=f"obs_trees_{site_idx}")
            site.rf.obstruction_buildings = st.checkbox("Buildings", key=f"obs_bldg_{site_idx}")
        with col2:
            site.rf.coverage_direction = st.text_input(
                "Coverage Direction", value=site.rf.coverage_direction or "",
                key=f"coverage_dir_{site_idx}")
            site.rf.obstruction_water_towers = st.checkbox("Water Towers", key=f"obs_water_{site_idx}")
            site.rf.obstruction_cell_towers = st.checkbox("Cell Towers", key=f"obs_cell_{site_idx}")

        st.markdown("---")

        # Flight / Airspace
        st.markdown(f"#### Airspace {_indicator('AIRSPACE_CLASS')}")
        col1, col2 = st.columns(2)
        with col1:
            site.flight.airspace_class = st.text_input(
                "Airspace Class", value=site.flight.airspace_class or "",
                key=f"airspace_{site_idx}")
            st.text(f"Nearby Airports: {site.flight.nearby_airports or '—'}")
            st.text(f"Nearby Heliports: {site.flight.nearby_heliports or '—'}")
        with col2:
            site.flight.launch_direction = st.text_input(
                "Launch Direction", value=site.flight.launch_direction or "",
                key=f"launch_dir_{site_idx}")
            site.flight.emergency_landing_zone = st.text_input(
                "Emergency Landing Zone", value=site.flight.emergency_landing_zone or "",
                key=f"elz_{site_idx}")

        # Photo Category Assignment
        if site.photos:
            st.markdown("---")
            st.markdown("#### Photo Categories")
            for photo in site.photos:
                photo.category = st.selectbox(
                    f"{photo.photo_id}",
                    ["Site", "Installation", "Infrastructure", "RF", "Access"],
                    index=["Site", "Installation", "Infrastructure", "RF", "Access"].index(photo.category) if photo.category in ["Site", "Installation", "Infrastructure", "RF", "Access"] else 0,
                    key=f"photo_cat_{site_idx}_{photo.photo_id}",
                )


def _render_annotator_workspace(selected_site):
    """Render the full-width image annotation workspace for one site."""
    st.markdown(f"### {reporter._format_short_address(selected_site['address'])}")
    st.write(f"📁 **Local Folder:** `{os.path.basename(selected_site['folder_path'])}`")
    st.caption(selected_site['folder_path'])

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("##### Infrastructure Detection")
        st.write(f"🪜 **Roof Access:** {selected_site['analysis'].get('roof_access')}")
        st.write(f"🏠 **Roof Type:** {selected_site['analysis'].get('roof_type')}")
    with col_b:
        st.markdown("##### Mounting & Hardware")
        st.write(f"📐 **Mounts:** {', '.join(selected_site['analysis'].get('mounting_structures', [])) or 'None'}")
        st.write(f"🔌 **Hardware:** {', '.join(selected_site['analysis'].get('hardware', [])) or 'None'}")

    st.divider()
    st.subheader("🛠️ Interactive Rooftop Layout & Annotator")
    st.write("1. Click a thumbnail below to select the background. 2. Select node type/label. 3. Click directly on the image to place the node!")

    st.markdown("##### Select Background Photo:")
    images_list = selected_site.get('images', [])
    if images_list and st.session_state.active_bg_image not in {img.get('filename') for img in images_list}:
        st.session_state.active_bg_image = images_list[0]['filename']
    cols_per_row = 6
    for i in range(0, len(images_list), cols_per_row):
        chunk = images_list[i:i+cols_per_row]
        col_thumb = st.columns(cols_per_row)
        for idx_in_chunk, img in enumerate(chunk):
            global_idx = i + idx_in_chunk
            with col_thumb[idx_in_chunk]:
                img_path = img.get('dest_path') or img.get('path')
                thumb_path = _get_displayable_image_path(img_path, site_folder=selected_site.get('folder_path'))
                if thumb_path:
                    is_active = img['filename'] == st.session_state.active_bg_image
                    st.image(thumb_path, width=120)
                    btn_label = "🎯 Active" if is_active else "Select"
                    if st.button(btn_label, key=f"sel_thumb_{selected_site['site_id']}_{global_idx}", width="stretch"):
                        st.session_state.active_bg_image = img['filename']
                        st.session_state.last_click[selected_site['site_id']] = None
                else:
                    st.caption(f"Error: {img['filename'][:8]}...")

    if not st.session_state.active_bg_image:
        st.warning("Please upload or process images first to mark up.")
        return

    active_img_meta = next((img for img in selected_site['images'] if img['filename'] == st.session_state.active_bg_image), None)
    if not active_img_meta and selected_site.get('images'):
        active_img_meta = selected_site['images'][0]
        st.session_state.active_bg_image = active_img_meta['filename']

    if not active_img_meta:
        st.warning("Please upload or process images first to mark up.")
        return

    bg_path = active_img_meta.get('dest_path') or active_img_meta.get('path')
    bg_display_path = _get_displayable_image_path(bg_path, site_folder=selected_site.get('folder_path'))

    if 'markers_by_image' not in selected_site:
        selected_site['markers_by_image'] = {}
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

    current_markers = selected_site['markers_by_image'][st.session_state.active_bg_image]
    current_placements = selected_site['image_placements_by_image'][st.session_state.active_bg_image]

    if 'eng_note' not in selected_site:
        selected_site['eng_note'] = (
            "Responder may be installed at this time with 110V, 20A service. "
            "If Guardian is installed in the future, it will require 208V, 30A service "
            "with additional wiring and electrical provisions to support the higher voltage requirement."
        )

    images_dir = os.path.join(os.path.dirname(__file__), "images")
    available_images = _list_available_images(images_dir)

    st.markdown("##### Placement Customization (To place on image click)")
    node_type_options = {
        "Electric": ["15 Amp 110V AC", "20 Amp 110V AC", "30 Amp 208V AC"],
        "Data": ["BRINC RF Site 25 50", "BRINC Station 25 50", "BRINC Radar Site 10 10"],
        "RF": ["10 foot pole", "20 foot pole", "30 foot pole", "microsite", "Tower"],
        "Unistrut": ["3 Unistrut", "4 Unistrut"],
        "Lift": ["Crane", "Fire Department"]
    }

    placement_mode = st.radio("What to place:", ["📍 Node", "🖼️ Image"], horizontal=True, key=f"int_placement_mode_{selected_site['site_id']}")
    m_type = None
    m_label = None
    placement_image = None

    if "Node" in placement_mode:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            m_type = st.selectbox("Node Type", ["Electric", "Data", "RF", "Unistrut", "Lift"], key=f"int_mtype_{selected_site['site_id']}")
        with col_m2:
            available_labels = node_type_options.get(m_type, [""])
            m_label = st.selectbox("Node Label", available_labels, key=f"int_mlabel_{selected_site['site_id']}")
    else:
        if available_images:
            placement_image = st.selectbox("Select Image to Place", available_images, key=f"int_placement_img_{selected_site['site_id']}")
        else:
            st.warning("No images available in the images directory.")

    st.markdown("🎯 **Click on the image below to place this node:**")
    img_base_name = os.path.splitext(st.session_state.active_bg_image)[0]
    output_drawing_path = os.path.join(selected_site['folder_path'], f"engineering_layout_{img_base_name}.png")
    display_img_path = output_drawing_path if os.path.exists(output_drawing_path) else bg_display_path
    if not display_img_path:
        st.error(f"Cannot preview or annotate this image: {active_img_meta['filename']}")
        return

    canvas_key = f"canvas_{selected_site['site_id']}_{hash(st.session_state.active_bg_image)}"
    try:
        with Image.open(display_img_path) as img_check:
            img_width, img_height = img_check.size
        if img_height > img_width:
            display_size = min(600, img_height)
            click = streamlit_image_coordinates(display_img_path, key=canvas_key, height=display_size)
        else:
            display_size = min(600, img_width)
            click = streamlit_image_coordinates(display_img_path, key=canvas_key, width=display_size)
    except Exception:
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
                if h > w:
                    display_h = min(600, h)
                    display_w = display_h * w / h
                else:
                    display_w = min(600, w)
                    display_h = display_w * h / w
                ratio_x = click_x / display_w
                ratio_y = click_y / display_h
                is_drawing = os.path.exists(output_drawing_path)
                photo_width_ratio = 0.80 if is_drawing else 1.0

                if ratio_x <= photo_width_ratio:
                    if "Node" in placement_mode:
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
                        img_x_pct = (ratio_x / photo_width_ratio) * 100
                        img_y_pct = ratio_y * 100
                        selected_site['image_placements_by_image'][st.session_state.active_bg_image].append({
                            'image_name': placement_image,
                            'x': img_x_pct,
                            'y': img_y_pct
                        })
                        success_msg = f"Added {placement_image}!"

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
                    st.success(success_msg)
            except Exception as e:
                st.error(f"Error registering click: {e}")

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
    else:
        st.caption("No markers placed yet.")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        selected_site['eng_note'] = st.text_area("Engineer's Notes Text", value=selected_site['eng_note'], key=f"int_engnote_{selected_site['site_id']}")
    with col_btn2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️ Clear All Placements", key=f"int_clearnode_{selected_site['site_id']}", width="stretch"):
            selected_site['markers_by_image'][st.session_state.active_bg_image] = []
            selected_site['image_placements_by_image'][st.session_state.active_bg_image] = []
            if os.path.exists(output_drawing_path):
                os.remove(output_drawing_path)
            _save_session_metadata(st.session_state.processed_sites)
            st.warning("Cleared all nodes and images for this photo.")

        if st.button("🔄 Refresh Rendering", key=f"int_redraw_{selected_site['site_id']}", width="stretch"):
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

    if os.path.exists(output_drawing_path):
        st.image(output_drawing_path, caption="Active Engineering Markup Layout Preview", width="stretch")


# Layout Columns
tab1, tab2, tab3, tab4 = st.tabs(["Survey Pipeline", "Annotate", "Workflow Sync", "Analytics & Logs"])

with tab1:
    if st.session_state.processed_sites:
        # --- POC / Contacts Table ---
        st.markdown("**Points of Contact**")
        gmail_contacts = st.session_state.pop("gmail_found_contacts", None)
        if gmail_contacts:
            existing_emails = {r["email"].lower() for r in st.session_state.poc_rows if r.get("email")}
            for c in gmail_contacts:
                c_email_lower = c["email"].lower()
                if c_email_lower not in existing_emails:
                    st.session_state.poc_rows.append({
                        "_uid": _next_poc_uid(),
                        "role": "Other",
                        "name": c.get("name", ""),
                        "email": c["email"],
                        "title": c.get("title", ""),
                        "phone": c.get("phone", ""),
                    })
                    existing_emails.add(c_email_lower)
                else:
                    for row in st.session_state.poc_rows:
                        if row.get("email", "").lower() == c_email_lower:
                            if c.get("title") and not row.get("title"):
                                row["title"] = c["title"]
                            if c.get("phone") and not row.get("phone"):
                                row["phone"] = c["phone"]
                            break

        role_options = ["Other", "POC", "IT", "Facilities", "RTCC", "Radio Shop"]
        rows_to_remove = []
        for row in st.session_state.poc_rows:
            if "_uid" not in row:
                row["_uid"] = _next_poc_uid()
            if row.get("role") not in role_options:
                row["role"] = "Other"
        if st.session_state.poc_rows:
            hc1, hc2, hc3, hc4, hc5, hc6 = st.columns([1, 1.8, 1.8, 1.8, 1.5, 0.5])
            hc1.caption("Role")
            hc2.caption("Name")
            hc3.caption("Title / Rank")
            hc4.caption("Email")
            hc5.caption("Phone")
            hc6.caption("")
        for i, row in enumerate(st.session_state.poc_rows):
            uid = row["_uid"]
            rc1, rc2, rc3, rc4, rc5, rc6 = st.columns([1, 1.8, 1.8, 1.8, 1.5, 0.5])
            with rc1:
                st.session_state.poc_rows[i]["role"] = st.selectbox(
                    "Role", role_options, index=role_options.index(row["role"]) if row["role"] in role_options else 0,
                    key=f"poc_role_{uid}", label_visibility="collapsed",
                )
            with rc2:
                st.session_state.poc_rows[i]["name"] = st.text_input(
                    "Name", value=row["name"], key=f"poc_name_{uid}", label_visibility="collapsed",
                    placeholder="Name",
                )
            with rc3:
                st.session_state.poc_rows[i]["title"] = st.text_input(
                    "Title", value=row.get("title", ""), key=f"poc_title_{uid}", label_visibility="collapsed",
                    placeholder="Title / Rank",
                )
            with rc4:
                st.session_state.poc_rows[i]["email"] = st.text_input(
                    "Email", value=row["email"], key=f"poc_email_{uid}", label_visibility="collapsed",
                    placeholder="Email",
                )
            with rc5:
                st.session_state.poc_rows[i]["phone"] = st.text_input(
                    "Phone", value=row.get("phone", ""), key=f"poc_phone_{uid}", label_visibility="collapsed",
                    placeholder="Phone",
                )
            with rc6:
                if st.button("✕", key=f"poc_del_{uid}"):
                    rows_to_remove.append(i)

        if rows_to_remove:
            for idx in sorted(rows_to_remove, reverse=True):
                removed_uid = st.session_state.poc_rows[idx]["_uid"]
                for prefix in ("poc_role_", "poc_name_", "poc_title_", "poc_email_", "poc_phone_", "poc_del_"):
                    st.session_state.pop(f"{prefix}{removed_uid}", None)
                st.session_state.poc_rows.pop(idx)
            st.rerun()

        if st.button("＋ Add Contact", key="add_poc_row"):
            st.session_state.poc_rows.append({"_uid": _next_poc_uid(), "role": "Other", "name": "", "email": "", "title": "", "phone": ""})
            st.rerun()

        st.session_state.poc_rows = sync_customer_info_from_poc_rows(
            st.session_state.customer_info,
            st.session_state.poc_rows,
            widget_state=st.session_state,
        )

        # --- Deployment Specifications ---
        st.markdown("**Deployment Specifications**")
        ds1, ds2, ds3 = st.columns(3)
        with ds1:
            st.session_state.customer_info["survey_delivery_target"] = st.text_input(
                "Survey / Delivery Target",
                value=st.session_state.customer_info.get("survey_delivery_target", ""),
                placeholder="e.g. Week of September 28, 2026",
            )
        with ds2:
            st.session_state.customer_info["power_circuit_requirements"] = st.text_input(
                "Power Circuit Requirements",
                value=st.session_state.customer_info.get("power_circuit_requirements", ""),
                placeholder="e.g. 120V / 20A Dedicated Circuit",
            )
        with ds3:
            st.session_state.customer_info["internet_ethernet_access"] = st.text_input(
                "Internet / Ethernet Access",
                value=st.session_state.customer_info.get("internet_ethernet_access", ""),
                placeholder="e.g. DHCP on isolated VLAN",
            )

        ds4, ds5, ds6 = st.columns(3)
        with ds4:
            st.session_state.customer_info["crane_contractor"] = st.text_input(
                "Crane Contractor",
                value=st.session_state.customer_info.get("crane_contractor", ""),
                placeholder="e.g. Pending crane company",
            )
        with ds5:
            st.session_state.customer_info["tower_climber_contractor"] = st.text_input(
                "Tower Climber Contractor",
                value=st.session_state.customer_info.get("tower_climber_contractor", ""),
                placeholder="e.g. DNA",
            )
        with ds6:
            st.session_state.customer_info["brinc_pm"] = st.text_input(
                "BRINC Project Manager",
                value=st.session_state.customer_info.get("brinc_pm", ""),
                placeholder="e.g. steven.beltran@brincdrones.com",
            )

        ds7, ds8 = st.columns(2)
        with ds7:
            st.session_state.customer_info["follow_up_requirements"] = st.text_input(
                "Follow-up Requirements",
                value=st.session_state.customer_info.get("follow_up_requirements", ""),
                placeholder="e.g. Infrastructure for site needs to be completed",
            )
        with ds8:
            st.session_state.customer_info["action_items"] = st.text_input(
                "Action Items",
                value=st.session_state.customer_info.get("action_items", ""),
                placeholder="e.g. Confirm ethernet and power 30 days before install",
            )
    else:
        st.info("Upload survey photos to unlock contact and deployment fields.")

    st.divider()

    # Two column layout: Left (Sites), Middle (Map/Markup)
    col1, col2 = st.columns([1, 2])
    
    with col1:
        if st.session_state.processed_sites:
            st.subheader("Sites Detected")
            for site in st.session_state.processed_sites:
                # Build a readable street address from the first two comma parts
                _parts = [p.strip() for p in site['address'].split(',')]
                _label = ', '.join(_parts[:2]) if len(_parts) >= 2 else site['address']
                st.markdown(f"**{site['site_id']}: {_label}**")
                st.caption(f"Photos: {len(site.get('images', []))} · Coordinates: {site['latitude']:.4f}, {site['longitude']:.4f}")
                st.caption(f"Airspace: `{site['airspace']}`")

            # Clickable link to the Google Drive working directory
            if st.session_state.get("drive_folder_url"):
                st.divider()
                st.markdown(f"[📂 Open in Google Drive]({st.session_state.drive_folder_url})")

    with col2:
        st.subheader("Site Detail & Analysis")
        if st.session_state.processed_sites:
            st.info("Map displayed in Mission Workspace above. Select a site below for detailed inspection.")
            
            # Show detailed card for selected site
            def _site_label(idx):
                s = st.session_state.processed_sites[idx]
                return f"{s['site_id']}: {reporter._format_short_address(s['address'])}"
            selected_site_idx = st.selectbox("Select Site to Inspect", range(len(st.session_state.processed_sites)), format_func=_site_label)
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

            st.markdown(f"### {reporter._format_short_address(selected_site['address'])}")
            st.write(f"📁 **Local Folder:** `{os.path.basename(selected_site['folder_path'])}`")
            st.caption(selected_site['folder_path'])
            
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("##### Infrastructure Detection")
                st.write(f"🪜 **Roof Access:** {selected_site['analysis'].get('roof_access')}")
                st.write(f"🏠 **Roof Type:** {selected_site['analysis'].get('roof_type')}")
            with col_b:
                st.markdown("##### Mounting & Hardware")
                st.write(f"📐 **Mounts:** {', '.join(selected_site['analysis'].get('mounting_structures', [])) or 'None'}")
                st.write(f"🔌 **Hardware:** {', '.join(selected_site['analysis'].get('hardware', [])) or 'None'}")
                
            if st.session_state.candidate_sites:
                st.markdown("---")
                st.subheader("Site Assessment Checklists")
                for i, csite in enumerate(st.session_state.candidate_sites, start=1):
                    _render_site_checklist(csite, i)
            # Report generation and Drive upload are separate actions.
            st.subheader("Report Generation & Upload")
            with st.expander("Report Contact Preview", expanded=False):
                preview_rows = _report_contact_preview_rows()
                preview_df = pd.DataFrame(preview_rows, columns=["Field", "Value"])
                st.dataframe(preview_df, width="stretch", hide_index=True)
                st.caption("This preview mirrors the report import fields before export.")
            report_name = st.text_input("Master Document Name", value=_default_master_document_name())
            use_new_report = st.checkbox(
                "Use enhanced multi-site report format",
                value=True,
                key="use_new_report",
            )
            if st.button("📄 Build Survey Document", width="stretch"):
                _set_sidebar_activity(
                    "Building survey document",
                    "Preparing report inputs and saving session metadata.",
                )
                with st.status("Building report...", expanded=True) as report_status:
                    try:
                        survey_date = _derive_survey_date_from_sites(st.session_state.processed_sites)
                        surveyor = google_oauth.get_user_email() or st.session_state.customer_info.get("surveyor", "")
                        if survey_date:
                            st.session_state.customer_info["survey_date"] = survey_date
                            st.session_state.customer_info["report_date"] = datetime.datetime.strptime(survey_date, "%Y-%m-%d").strftime("%B %d, %Y")
                        if surveyor:
                            st.session_state.customer_info["surveyor"] = surveyor

                        # Update metadata save
                        report_status.write("💾 Saving session metadata...")
                        _set_sidebar_activity(
                            "Building survey document",
                            "Saving session metadata before document generation.",
                        )
                        _save_session_metadata(st.session_state.processed_sites)

                        # Create subfolder with PD name and creation date
                        pd_name = st.session_state.customer_info.get("agency_name", "Report").replace(" ", "_")
                        creation_date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        report_subfolder = os.path.join(output_dir, f"{pd_name}_{creation_date}")
                        os.makedirs(report_subfolder, exist_ok=True)

                        # Save report in subfolder
                        report_path = os.path.join(report_subfolder, report_name)

                        report_status.update(label="Generating report document...")
                        def _report_progress(step):
                            report_status.write(f"📝 {step}")
                            _set_sidebar_activity("Building survey document", step)

                        report_sites = st.session_state.candidate_sites if use_new_report and st.session_state.candidate_sites else st.session_state.processed_sites
                        if use_new_report and st.session_state.candidate_sites:
                            from reporter import generate_candidate_site_report
                            generate_candidate_site_report(
                                st.session_state.candidate_sites,
                                report_path,
                                customer_info=st.session_state.customer_info,
                                progress_callback=_report_progress,
                            )
                        else:
                            reporter.generate_word_report(
                                st.session_state.processed_sites,
                                report_path,
                                customer_info=st.session_state.customer_info,
                                progress_callback=_report_progress,
                            )
                        st.session_state.generated_report = report_path

                        kmz_path = os.path.splitext(report_path)[0] + ".kmz"
                        reporter.export_sites_kmz(
                            report_sites,
                            kmz_path,
                            candidate_sites=st.session_state.candidate_sites if st.session_state.candidate_sites else None,
                        )

                        report_status.update(label="Report generated successfully!", state="complete", expanded=False)
                        _set_sidebar_activity(
                            "Survey document ready",
                            os.path.basename(report_path),
                            state="complete",
                        )
                    except Exception as e:
                        report_status.update(label="Report generation failed", state="error")
                        _set_sidebar_activity("Survey document failed", str(e), state="error")
                        st.error(f"Report generation error: {e}")

                if st.session_state.get("generated_report"):
                    st.success(f"Generated report: `{st.session_state.generated_report}`")

            if st.session_state.get("generated_report") and st.session_state.candidate_sites:
                if st.button("☁️ Upload Generated Report to Drive", width="stretch"):
                    _set_sidebar_activity(
                        "Uploading report to Google Drive",
                        "Preparing Drive upload workflow.",
                    )
                    with st.status("Uploading report to Google Drive...", expanded=True) as upload_status:
                        try:
                            report_path = st.session_state.generated_report
                            if not os.path.exists(report_path):
                                raise FileNotFoundError(f"Generated report not found: {report_path}")

                            report_subfolder = os.path.dirname(report_path)
                            report_drive = get_drive_manager()
                            if not report_drive:
                                raise RuntimeError("Google Drive is not connected.")

                            if uploaded_files and not st.session_state.get("client_folder_id"):
                                upload_status.update(label="Preparing Drive folder structure...")
                                _set_sidebar_activity(
                                    "Uploading report to Google Drive",
                                    "Preparing Drive folder structure.",
                                )
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                agency = st.session_state.customer_info.get("agency_name", client_name)
                                client_folder_name = f"{agency.replace(' ', '_')}_{timestamp}"
                                client_fid = report_drive.get_or_create_folder(team_folder_id, client_folder_name)

                                raw_fid = report_drive.get_or_create_folder(client_fid, "01_Raw_Images")
                                proc_fid = report_drive.get_or_create_folder(client_fid, "02_Processed_Sites")

                                raw_image_folder_ids = {}
                                for site in st.session_state.processed_sites:
                                    site_folder_name = processor._drive_site_folder_name(
                                        site.get("address"),
                                        site.get("site_id"),
                                    )
                                    site_raw_fid = report_drive.get_or_create_folder(raw_fid, site_folder_name)
                                    for img in site.get("images", []):
                                        filename = img.get("filename")
                                        if filename and filename not in raw_image_folder_ids:
                                            raw_image_folder_ids[filename] = site_raw_fid

                                total_upload = len(uploaded_files)
                                upload_line = st.empty()
                                for idx, uploaded_file in enumerate(uploaded_files):
                                    upload_line.write(f"☁️ Uploading image {idx+1}/{total_upload}: {uploaded_file.name}")
                                    _set_sidebar_activity(
                                        "Uploading report to Google Drive",
                                        f"Uploading image {idx+1}/{total_upload}: {uploaded_file.name}",
                                    )
                                    temp_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)
                                    with open(temp_path, "wb") as f:
                                        f.write(uploaded_file.getbuffer())
                                    target_raw_folder = raw_image_folder_ids.get(uploaded_file.name, raw_fid)
                                    report_drive.upload_file(temp_path, target_raw_folder)

                                st.session_state.client_folder_id = client_fid
                                st.session_state.raw_images_folder_id = raw_fid
                                st.session_state.processed_folder_id = proc_fid
                                st.session_state.reports_folder_id = client_fid
                                st.session_state.metadata_folder_id = client_fid
                                st.session_state.client_name = agency
                                st.session_state.drive_folder_url = f"https://drive.google.com/drive/folders/{client_fid}"
                                upload_status.write(f"✅ Uploaded {total_upload} images to Drive")

                            upload_status.write("📤 Uploading report and exports to Drive...")
                            _set_sidebar_activity(
                                "Uploading report to Google Drive",
                                "Uploading generated report and export files.",
                            )
                            report_drive.upload_file(
                                report_path,
                                st.session_state.get("reports_folder_id") or st.session_state.get("client_folder_id"),
                                file_name=os.path.basename(report_path),
                            )
                            try:
                                kmz_path = os.path.splitext(report_path)[0] + ".kmz"
                                if os.path.exists(kmz_path):
                                    report_drive.upload_file(
                                        kmz_path,
                                        st.session_state.get("reports_folder_id") or st.session_state.get("client_folder_id"),
                                        file_name=os.path.basename(kmz_path),
                                    )
                            except Exception:
                                pass

                            if st.session_state.candidate_sites and st.session_state.get("metadata_folder_id"):
                                try:
                                    _json_path = os.path.join(report_subfolder, "survey_export.json")
                                    export_sites_json(st.session_state.candidate_sites, _json_path)
                                    report_drive.upload_file(_json_path, st.session_state.metadata_folder_id)
                                except Exception:
                                    pass
                                try:
                                    _csv_path = os.path.join(report_subfolder, "survey_export.csv")
                                    export_sites_csv(st.session_state.candidate_sites, _csv_path)
                                    report_drive.upload_file(_csv_path, st.session_state.metadata_folder_id)
                                except Exception:
                                    pass

                            if st.session_state.get("client_folder_id"):
                                st.session_state.drive_folder_url = f"https://drive.google.com/drive/folders/{st.session_state.client_folder_id}"

                            upload_status.update(label="Report uploaded successfully!", state="complete", expanded=False)
                            _set_sidebar_activity(
                                "Drive upload complete",
                                os.path.basename(report_path),
                                state="complete",
                            )
                        except Exception as e:
                            upload_status.update(label="Upload failed", state="error")
                            _set_sidebar_activity("Drive upload failed", str(e), state="error")
                            st.error(f"Drive upload error: {e}")

            # Persistent export buttons — survive reruns
            if st.session_state.get("generated_report") and st.session_state.candidate_sites:
                report_path = st.session_state.generated_report
                if os.path.exists(report_path):
                    report_subfolder = os.path.dirname(report_path)
                    exp_col1, exp_col2, exp_col3 = st.columns(3)
                    with exp_col1:
                        json_path = os.path.join(report_subfolder, "survey_export.json")
                        export_sites_json(st.session_state.candidate_sites, json_path)
                        with open(json_path, "r") as jf:
                            st.download_button("📥 Download JSON", jf.read(),
                                "survey_export.json", mime="application/json", key="json_save_persist")
                    with exp_col2:
                        csv_path = os.path.join(report_subfolder, "survey_export.csv")
                        export_sites_csv(st.session_state.candidate_sites, csv_path)
                        with open(csv_path, "r") as cf:
                            st.download_button("📥 Download CSV", cf.read(),
                                "survey_export.csv", mime="text/csv", key="csv_save_persist")
                    with exp_col3:
                        with open(report_path, "rb") as rf:
                            st.download_button("📥 Download DOCX", rf.read(),
                                os.path.basename(report_path),
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key="docx_save_persist")
                        kmz_path = os.path.splitext(report_path)[0] + ".kmz"
                        if os.path.exists(kmz_path):
                            with open(kmz_path, "rb") as kf:
                                st.download_button("📥 Download KMZ", kf.read(),
                                    os.path.basename(kmz_path),
                                    mime="application/vnd.google-earth.kmz",
                                    key="kmz_save_persist")
        else:
            st.info("No sites loaded. Run the ingestion step first.")

with tab2:
    st.subheader("Annotator Workspace")
    st.write("Use this tab for full-width photo markup.")
    if st.session_state.processed_sites:
        def _annotator_site_label(idx):
            site = st.session_state.processed_sites[idx]
            return f"{site['site_id']}: {reporter._format_short_address(site['address'])}"

        selected_idx = st.selectbox(
            "Select Site to Annotate",
            range(len(st.session_state.processed_sites)),
            format_func=_annotator_site_label,
            key="annotator_site_select",
        )
        st.session_state["selected_site_idx"] = selected_idx
        selected_site = st.session_state.processed_sites[selected_idx]
        _render_annotator_workspace(selected_site)
    else:
        st.info("No sites loaded. Run the ingestion step first.")

with tab3:
    st.subheader("Cloud Workflow Orchestration")
    st.write("Connect survey findings to CRM, task tracking, calendar scheduler, and communications.")
    
    col_x, col_y = st.columns(2)
    
    with col_x:
        st.markdown("#### CRM & Kickoff Scheduler")
        if st.button("Fetch Customer Purchase Info (HubSpot)", key="hs_sync_tab2", width="stretch"):
            agency = st.session_state.customer_info.get("agency_name", "")
            if not agency:
                st.warning("Enter an Agency Name on the Survey Pipeline tab first.")
            else:
                from gmail_lookup import search_hubspot_for_records
                _set_sidebar_activity(
                    "Searching HubSpot",
                    f"Looking up CRM records for {agency}.",
                )
                with st.spinner("Searching HubSpot..."):
                    hs_results = search_hubspot_for_records(
                        agency,
                        hubspot_token=st.session_state.get("_hubspot_token", ""),
                    )
                    st.session_state["hubspot_results"] = hs_results
                if hs_results["status"] == "connected":
                    co_count = len(hs_results["companies"])
                    deal_count = len(hs_results["deals"])
                    _append_integration_log(
                        f"[HubSpot API] Found {co_count} companies, {deal_count} deals for {agency}"
                    )
                    _set_sidebar_activity(
                        "HubSpot search complete",
                        f"Found {co_count} companies and {deal_count} deals for {agency}.",
                        state="complete",
                    )
                    st.success(f"Found {co_count} companies and {deal_count} deals.")
                elif hs_results["status"] == "no_credentials":
                    _set_sidebar_activity(
                        "HubSpot search blocked",
                        "No HubSpot token is configured.",
                        state="error",
                    )
                    st.warning("HubSpot access token not configured. Add it in Settings > API Configurations.")
                elif hs_results["status"] == "error":
                    _set_sidebar_activity("HubSpot search failed", hs_results["error"], state="error")
                    st.error(f"HubSpot error: {hs_results['error']}")
                else:
                    _set_sidebar_activity(
                        "HubSpot search complete",
                        f"No HubSpot records were found for {agency}.",
                        state="complete",
                    )
                    st.info("No HubSpot records found for this agency.")
            
        if st.button("Schedule Kickoff Meeting (Google Calendar)", key="cal_sync_tab2", width="stretch"):
            _append_integration_log("[Google Calendar API] POST /events - Scheduled Kickoff for Lansing PD")
            st.success("Meeting Scheduled & Invites sent to stakeholders.")

        if st.button("Sync Report to Google Drive", key="drive_sync_tab2", width="stretch"):
            if hasattr(st.session_state, 'generated_report'):
                _append_integration_log(f"[Google Drive API] POST /files - Uploaded '{os.path.basename(st.session_state.generated_report)}'")
                st.success("Report synchronized to cloud storage.")
            else:
                st.warning("Generate the Word report first on the Survey Pipeline tab.")

    with col_y:
        st.markdown("#### Operations & Communication")
        if st.button("Search Jira Tickets", key="jira_sync_tab2", width="stretch"):
            agency = st.session_state.customer_info.get("agency_name", "")
            if not agency:
                st.warning("Enter an Agency Name on the Survey Pipeline tab first.")
            else:
                from gmail_lookup import search_jira_for_tickets
                _set_sidebar_activity(
                    "Searching Jira",
                    f"Looking up Jira tickets for {agency}.",
                )
                with st.spinner("Searching Jira..."):
                    jira_results = search_jira_for_tickets(
                        agency,
                        city=st.session_state.get("customer_info", {}).get("city", "") or None,
                        jira_url=st.session_state.get("_jira_url", ""),
                        jira_email=st.session_state.get("_jira_email", ""),
                        jira_token=st.session_state.get("_jira_token", ""),
                    )
                    st.session_state["jira_results"] = jira_results
                if jira_results["status"] == "connected":
                    count = len(jira_results["tickets"])
                    _append_integration_log(
                        f"[Jira API] Found {count} tickets for {agency}"
                    )
                    _set_sidebar_activity(
                        "Jira search complete",
                        f"Found {count} Jira tickets for {agency}.",
                        state="complete",
                    )
                    st.success(f"Found {count} Jira tickets.")
                    _render_jira_ticket_results(jira_results)
                elif jira_results["status"] == "no_credentials":
                    _set_sidebar_activity(
                        "Jira search blocked",
                        "Jira credentials are not configured.",
                        state="error",
                    )
                    st.warning("Jira credentials not configured. Add email + API token in Settings > API Configurations.")
                elif jira_results["status"] == "error":
                    _set_sidebar_activity("Jira search failed", jira_results["error"], state="error")
                    st.error(f"Jira error: {jira_results['error']}")
                else:
                    _set_sidebar_activity(
                        "Jira search complete",
                        f"No Jira tickets were found for {agency}.",
                        state="complete",
                    )
                    st.info("No Jira tickets found for this agency.")
            
        if st.button("Send Project Status to Slack", key="slack_sync_tab2", width="stretch"):
            _append_integration_log("[Slack Webhook] POST /hooks - Posted Lansing PD survey status")
            st.success("Notification broadcasted to Slack channels.")

with tab4:
    st.subheader("Execution & Integration Logs")
    if st.session_state.integration_logs:
        for log in st.session_state.integration_logs:
            st.text(_format_integration_log(log))
    else:
        st.write("No integration steps executed yet.")

_finalize_upload_processing_if_ready()

