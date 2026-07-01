"""Parallel orchestrator for agency document and contact lookups.

Runs Gmail, Google Drive, and Google Calendar lookups concurrently using
ThreadPoolExecutor with atomic result storage and error handling.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from google_drive import GoogleDriveManager
from matcher import assign_contact_to_role
import google_oauth


def extract_department_contacts(domain: str):
    """Lazy wrapper to avoid import-time coupling with gmail_lookup."""
    from gmail_lookup import extract_department_contacts as _extract_department_contacts

    return _extract_department_contacts(domain)


def search_department_calendar_events(dept_name: str, dept_domain: str):
    """Lazy wrapper to avoid import-time coupling with gmail_lookup."""
    from gmail_lookup import search_department_calendar_events as _search_department_calendar_events

    return _search_department_calendar_events(dept_name, dept_domain)


def _contact_identity(contact: dict) -> tuple:
    email = (contact.get("email") or "").strip().lower()
    if email:
        return ("email", email)

    name = (contact.get("name") or "").strip().lower()
    phone = (contact.get("phone") or "").strip()
    if name or phone:
        return ("fallback", name, phone)

    return ("empty",)


def _merge_contacts(*contact_lists: list) -> list:
    """Merge and dedupe contacts while ensuring `poc_role` is present."""
    merged = []
    seen = set()

    for contacts in contact_lists:
        for contact in contacts or []:
            identity = _contact_identity(contact)
            if identity in seen:
                continue
            seen.add(identity)

            normalized = {
                "name": contact.get("name", ""),
                "email": contact.get("email", ""),
                "title": contact.get("title", ""),
                "phone": contact.get("phone", ""),
            }
            normalized["poc_role"] = contact.get("poc_role") or assign_contact_to_role(normalized)
            merged.append(normalized)

    return merged


def fetch_agency_docs_parallel(dept_name: str, dept_domain: str, session_state: dict, city_hint: str | None = None) -> dict:
    """Fetch agency documents, contacts, and events in parallel.

    Runs three independent lookups concurrently:
    1. Gmail: extract department contacts and assign POC roles
    2. Google Drive: search for department documents
    3. Google Calendar: search for department events

    Uses ThreadPoolExecutor with max_workers=3 and 15-second timeout per lookup.
    If any lookup times out or fails, error is recorded but other lookups continue.

    Args:
        dept_name: Department name (e.g., "West Memphis Police")
        dept_domain: Department domain (e.g., "memphispd.gov")
        city_hint: Optional city name to broaden Gmail search when no domain is known.
        session_state: Streamlit session_state dict for auth credentials

    Returns:
        dict with keys:
            - contacts: list of contact dicts with poc_role assigned
            - docs: list of document dicts (name, owner, last_modified, url)
            - events: list of event dicts (name, date, time, attendee_count, url)
            - errors: dict mapping lookup type to error message (empty if no errors)

    Example:
        >>> result = fetch_agency_docs_parallel("West Memphis Police", "memphispd.gov", st.session_state)
        >>> result["contacts"]  # list of contacts with poc_role
        >>> result["docs"]      # list of documents
        >>> result["events"]    # list of calendar events
        >>> result["errors"]    # {"gmail": "...", "drive": "..."} or {}
    """
    result = {
        "contacts": [],
        "docs": [],
        "events": [],
        "errors": {}
    }

    def fetch_gmail():
        """Extract contacts from Gmail and assign POC roles."""
        try:
            contacts = extract_department_contacts(dept_domain)
            if not contacts and not dept_domain:
                from gmail_lookup import search_gmail_for_contacts as _search_gmail_for_contacts

                contacts_result = _search_gmail_for_contacts(dept_name, city=city_hint)
                contacts = contacts_result.get("contacts", [])
            return _merge_contacts(contacts)
        except Exception as e:
            result["errors"]["gmail"] = str(e)
            return []

    def fetch_drive():
        """Search Google Drive for department documents."""
        try:
            creds = google_oauth.get_credentials()
            if not creds:
                result["errors"]["drive"] = "No Google credentials found"
                return []

            manager = GoogleDriveManager(creds)
            docs = manager.search_department_documents(dept_name, dept_domain)
            return docs
        except Exception as e:
            result["errors"]["drive"] = str(e)
            return []

    def fetch_calendar():
        """Search Google Calendar for department events."""
        try:
            events = search_department_calendar_events(dept_name, dept_domain)
            return events
        except Exception as e:
            result["errors"]["calendar"] = str(e)
            return []

    # Run lookups in parallel with ThreadPoolExecutor
    from streamlit.runtime.scriptrunner import get_script_run_ctx, add_script_run_ctx
    ctx = get_script_run_ctx()

    def _run_with_ctx(func):
        add_script_run_ctx(ctx=ctx)
        return func()

    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        future_gmail = executor.submit(_run_with_ctx, fetch_gmail)
        future_drive = executor.submit(_run_with_ctx, fetch_drive)
        future_calendar = executor.submit(_run_with_ctx, fetch_calendar)

        # Collect results as they complete (with 15-second timeout per task)
        futures = {
            future_gmail: "gmail",
            future_drive: "drive",
            future_calendar: "calendar"
        }

        try:
            for future in as_completed(futures, timeout=15.0):
                lookup_type = futures[future]
                try:
                    lookup_result = future.result()
                    # Store result atomically
                    if lookup_type == "gmail":
                        result["contacts"] = lookup_result
                    elif lookup_type == "drive":
                        result["docs"] = lookup_result
                    elif lookup_type == "calendar":
                        result["events"] = lookup_result
                except Exception as e:
                    result["errors"][lookup_type] = f"Task execution failed: {str(e)}"

        except TimeoutError as e:
            # Timeout occurred — record which lookups didn't complete
            for future, lookup_type in futures.items():
                if not future.done():
                    result["errors"][lookup_type] = "Lookup timed out after 15 seconds"
                    future.cancel()

    invite_contacts = []
    for event in result["events"]:
        invite_contacts.extend(event.get("contacts", []) or [])
    result["contacts"] = _merge_contacts(result["contacts"], invite_contacts)

    return result
