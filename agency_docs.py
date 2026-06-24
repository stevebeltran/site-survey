"""Parallel orchestrator for agency document and contact lookups.

Runs Gmail, Google Drive, and Google Calendar lookups concurrently using
ThreadPoolExecutor with atomic result storage and error handling.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from gmail_lookup import extract_department_contacts, search_department_calendar_events
from google_drive import GoogleDriveManager
from matcher import assign_contact_to_role
import google_oauth


def fetch_agency_docs_parallel(dept_name: str, dept_domain: str, session_state: dict) -> dict:
    """Fetch agency documents, contacts, and events in parallel.

    Runs three independent lookups concurrently:
    1. Gmail: extract department contacts and assign POC roles
    2. Google Drive: search for department documents
    3. Google Calendar: search for department events

    Uses ThreadPoolExecutor with max_workers=3 and 5-second timeout per lookup.
    If any lookup times out or fails, error is recorded but other lookups continue.

    Args:
        dept_name: Department name (e.g., "West Memphis Police")
        dept_domain: Department domain (e.g., "memphispd.gov")
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
            # Assign poc_role to each contact using the matcher
            for contact in contacts:
                contact["poc_role"] = assign_contact_to_role(contact)
            return contacts
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
    with ThreadPoolExecutor(max_workers=3) as executor:
        # Submit all tasks
        future_gmail = executor.submit(fetch_gmail)
        future_drive = executor.submit(fetch_drive)
        future_calendar = executor.submit(fetch_calendar)

        # Collect results as they complete (with 5-second timeout per task)
        futures = {
            future_gmail: "gmail",
            future_drive: "drive",
            future_calendar: "calendar"
        }

        try:
            for future in as_completed(futures, timeout=5.0):
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
                    result["errors"][lookup_type] = "Lookup timed out after 5 seconds"
                    future.cancel()

    return result
