"""Gmail API wrapper for searching threads and extracting contact info.

Uses OAuth credentials from google_oauth.py to access the authenticated
user's Gmail and Calendar. Searches for kickoff call threads and calendar
invites for a given agency name.
"""

import json
import re
import base64
from email.utils import parseaddr
from googleapiclient.discovery import build
import streamlit as st
import google_oauth


def _get_gmail_service():
    """Build a Gmail API service using the current user's OAuth credentials."""
    creds = google_oauth.get_credentials()
    if not creds:
        return None
    return build("gmail", "v1", credentials=creds)


def _get_calendar_service():
    """Build a Google Calendar API service using the current user's OAuth credentials."""
    creds = google_oauth.get_credentials()
    if not creds:
        return None
    return build("calendar", "v3", credentials=creds)


def _extract_external_contacts(headers, my_domain="brincdrones.com"):
    """Extract non-internal email addresses and names from message headers.

    Returns list of dicts: [{"name": "...", "email": "..."}, ...]
    """
    contacts = []
    seen_emails = set()

    for header in headers:
        name = header.get("name", "")
        if name.lower() not in ("to", "cc", "from", "reply-to"):
            continue
        value = header.get("value", "")
        # Can contain multiple addresses separated by commas
        for part in value.split(","):
            display_name, email = parseaddr(part.strip())
            if not email:
                continue
            email_lower = email.lower()
            # Skip internal emails and duplicates
            if my_domain in email_lower:
                continue
            if email_lower in seen_emails:
                continue
            seen_emails.add(email_lower)
            contacts.append({"name": display_name or "", "email": email})

    return contacts


_NON_PERSON_PATTERNS = re.compile(
    r'^(google\s*calendar|no[\s-]?reply|noreply|donotreply|do[\s-]?not[\s-]?reply|'
    r'calendar-notification|mailer-daemon|postmaster|notification|automated|'
    r'system|admin@|support@|info@|helpdesk@)$',
    re.IGNORECASE,
)


def _is_non_person_name(name):
    """Return True if the display name looks like a service/resource, not a person."""
    if not name:
        return False
    return bool(_NON_PERSON_PATTERNS.search(name.strip()))


def search_gmail_for_contacts(agency_name, city=None):
    """Search Gmail for threads mentioning the agency and extract external contacts.

    Searches for kickoff calls, calendar invites, and general correspondence
    with the agency. Returns a dict with best-effort POC and IT contact info.

    Args:
        agency_name: e.g. "Lansing Police Department"
        city: e.g. "Lansing" (optional, broadens search)

    Returns:
        dict with keys: poc_name, poc_email, it_director, it_email
        (empty strings if not found)
    """
    result = {
        "poc_name": "",
        "poc_email": "",
        "it_director": "",
        "it_email": "",
        "all_contacts": [],  # every unique external contact found
        "status": "no_results",  # "connected", "no_results", or "auth_error"
        "error": "",
    }

    try:
        gmail = _get_gmail_service()
        if not gmail:
            result["status"] = "auth_error"
            result["error"] = "Google credentials not found in Streamlit secrets."
            return result
    except Exception as e:
        result["status"] = "auth_error"
        result["error"] = str(e)
        return result

    # Build search queries — look for kickoff calls, invites, and general mentions
    search_terms = [agency_name]
    if city and city.lower() not in agency_name.lower():
        search_terms.append(city)

    all_contacts = []
    gmail_connected = False

    for term in search_terms:
        for query in [
            f'"{term}" subject:(kickoff OR kick-off OR "kick off" OR meeting OR invite)',
            f'"{term}" (site survey OR DFR OR drone)',
        ]:
            try:
                resp = gmail.users().messages().list(
                    userId="me", q=query, maxResults=10
                ).execute()
                gmail_connected = True

                messages = resp.get("messages", [])
                for msg_stub in messages:
                    msg = gmail.users().messages().get(
                        userId="me", id=msg_stub["id"], format="metadata",
                        metadataHeaders=["From", "To", "Cc", "Reply-To", "Subject"],
                    ).execute()
                    headers = msg.get("payload", {}).get("headers", [])
                    contacts = _extract_external_contacts(headers)
                    all_contacts.extend(contacts)
            except Exception as e:
                err_str = str(e)
                if "403" in err_str or "401" in err_str or "delegation" in err_str.lower():
                    result["status"] = "auth_error"
                    result["error"] = err_str
                    return result
                print(f"Gmail search error for '{query}': {e}")

    # Also check Google Calendar for events mentioning the agency
    try:
        calendar = _get_calendar_service()
        if calendar:
            for term in search_terms:
                events_result = calendar.events().list(
                    calendarId="primary",
                    q=term,
                    maxResults=10,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
                for event in events_result.get("items", []):
                    for attendee in event.get("attendees", []):
                        email = attendee.get("email", "")
                        name = attendee.get("displayName", "")
                        if not email or "brincdrones.com" in email.lower():
                            continue
                        # Skip resource calendars and non-person entries
                        if attendee.get("resource"):
                            continue
                        if _is_non_person_name(name):
                            continue
                        all_contacts.append({"name": name, "email": email})
    except Exception as e:
        print(f"Calendar search error: {e}")

    if not all_contacts:
        if gmail_connected:
            result["status"] = "no_results"
        else:
            result["status"] = "auth_error"
            result["error"] = "Could not connect to Gmail. Domain-wide delegation may not be configured."
        return result

    result["status"] = "connected"

    # Deduplicate by email, keeping the first name seen
    seen = {}
    for c in all_contacts:
        email_lower = c["email"].lower()
        if email_lower not in seen:
            seen[email_lower] = c

    unique_contacts = list(seen.values())
    result["all_contacts"] = unique_contacts

    # Heuristic assignment:
    # - First external contact found = POC (most likely the person on the kickoff)
    # - Any contact with IT-related keywords in name or email = IT contact
    it_keywords = re.compile(r'\b(it|tech|information.technology|systems|network|infra)\b', re.IGNORECASE)

    for contact in unique_contacts:
        name = contact["name"]
        email = contact["email"]

        if it_keywords.search(name) or it_keywords.search(email.split("@")[0]):
            if not result["it_director"]:
                result["it_director"] = name
                result["it_email"] = email
        else:
            if not result["poc_name"]:
                result["poc_name"] = name
                result["poc_email"] = email

    # If we found contacts but none matched IT keywords, still populate POC
    if not result["poc_name"] and unique_contacts:
        first = unique_contacts[0]
        result["poc_name"] = first["name"]
        result["poc_email"] = first["email"]

    return result
