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


# Emails that should never appear as contacts (exact match on lowercased email)
_BLOCKED_EMAILS = {
    "calendar-notification@google.com",
}

# Email local-part prefixes that indicate automated/non-person senders
_BLOCKED_EMAIL_PREFIXES = re.compile(
    r'^(noreply|no-reply|donotreply|do-not-reply)@', re.IGNORECASE,
)


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


def _is_blocked_email(email):
    """Return True if the email address belongs to a known automated sender."""
    lower = email.lower()
    if lower in _BLOCKED_EMAILS:
        return True
    if _BLOCKED_EMAIL_PREFIXES.match(lower):
        return True
    return False


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
            # Skip known automated/non-person emails
            if _is_blocked_email(email):
                continue
            if _is_non_person_name(display_name):
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


# Title keywords to look for in email signatures
_TITLE_KEYWORDS = re.compile(
    r'\b(Chief\s+of\s+Police|Police\s+Chief|Captain|Lieutenant|Sergeant|Detective|Commander|'
    r'Deputy\s+Chief|Corporal|Officer|Sheriff|Undersheriff|Marshal|'
    r'Director|Manager|Coordinator|Administrator|Superintendent|'
    r'IT\s+Director|CIO|CTO|CISO|Systems?\s+Administrator|Network\s+Administrator|'
    r'Engineer|Analyst|Specialist|Technician|Supervisor|'
    r'City\s+Manager|Town\s+Manager|Assistant\s+Chief)\b',
    re.IGNORECASE,
)

# Common signature delimiters
_SIG_DELIMITERS = re.compile(r'^(\s*--\s*$|_{3,}|\u2014{1,}|={3,})')


def _get_plain_text_body(payload):
    """Recursively extract the text/plain body from a Gmail message payload."""
    mime = payload.get("mimeType", "")
    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        text = _get_plain_text_body(part)
        if text:
            return text
    return ""


def _name_from_email(email):
    """Best-effort name from an email local part (e.g. sastuart -> S Stuart)."""
    local = email.split("@")[0].lower()
    # Remove common prefixes/suffixes
    local = re.sub(r'[._\-]', ' ', local).strip()
    if not local:
        return ""
    # Try to split into first initial + last name patterns
    # e.g. "sastuart" -> try common patterns
    # If there are spaces from dots/underscores, title-case them
    parts = local.split()
    if len(parts) >= 2:
        return " ".join(p.capitalize() for p in parts)
    # Single word: if > 3 chars, could be first initial + last name
    # e.g. "jsamuelson" -> "J Samuelson"
    if len(local) > 3:
        return f"{local[0].upper()}. {local[1:].capitalize()}"
    return local.capitalize()


def _extract_body_contacts(gmail, msg_id):
    """Fetch the full message body and extract all contacts found in it.

    Parses two patterns:
    1. Inline roster: "Name - Title\\nemail@domain" (common in kickoff/intro emails)
    2. Signature block: name, title, email, phone at the end of the message

    Returns a list of dicts: [{"name": ..., "title": ..., "email": ...}, ...]
    """
    try:
        msg = gmail.users().messages().get(
            userId="me", id=msg_id, format="full",
        ).execute()
    except Exception:
        return []

    body = _get_plain_text_body(msg.get("payload", {}))
    if not body:
        return []

    lines = body.splitlines()
    contacts = []
    _email_re = re.compile(r'[\w.+-]+@[\w.-]+\.\w+')
    _phone_re = re.compile(r'[\(]?\d{3}[\)\s.\-]?\s*\d{3}[\s.\-]?\d{4}')
    # Pattern: "Name - Title" or "Name – Title" (with dash/en-dash separator)
    _name_title_re = re.compile(r'^([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s*[-\u2013\u2014]\s*(.+)$')

    # --- Pass 1: scan for inline "Name - Title\n email" roster entries ---
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        m = _name_title_re.match(stripped)
        if m:
            name = m.group(1).strip()
            title = m.group(2).strip()
            # Look ahead for an email on the next non-empty line
            email = ""
            for j in range(i + 1, min(i + 3, len(lines))):
                next_line = lines[j].strip()
                em = _email_re.search(next_line)
                if em:
                    email = em.group(0)
                    i = j  # skip past the email line
                    break
                if next_line and not em:
                    break
            if email:
                contacts.append({"name": name, "title": title, "email": email})
        i += 1

    # --- Pass 2: parse signature block at the end of the message ---
    sig_start = None
    for idx, line in enumerate(lines):
        if _SIG_DELIMITERS.match(line):
            sig_start = idx + 1

    sig_lines = lines[sig_start:] if sig_start is not None else lines[-15:]

    sig_title = None
    sig_name = None
    sig_email = None

    for line in sig_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if sig_title is None:
            tm = _TITLE_KEYWORDS.search(stripped)
            if tm:
                sig_title = stripped
        if sig_email is None:
            em = _email_re.search(stripped)
            if em:
                sig_email = em.group(0)

    # Name: first non-empty line that isn't title/email/phone/url
    for line in sig_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if _TITLE_KEYWORDS.search(stripped):
            continue
        if '@' in stripped or 'http' in stripped.lower():
            continue
        if _phone_re.search(stripped):
            continue
        if len(stripped) > 60:
            continue
        sig_name = stripped
        break

    if sig_name or sig_title:
        # Only add if we didn't already find this email in the roster
        sig_email_lower = (sig_email or "").lower()
        already_found = any(c["email"].lower() == sig_email_lower for c in contacts) if sig_email_lower else False
        if not already_found:
            contacts.append({
                "name": sig_name or "",
                "title": sig_title or "",
                "email": sig_email or "",
            })

    return contacts


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
    seen_msg_ids = set()  # avoid processing the same message across queries

    for term in search_terms:
        for query in [
            f'"{term}"',  # broad: any email mentioning the agency/city
            f'"{term}" subject:(kickoff OR kick-off OR "kick off" OR meeting OR invite)',
            f'"{term}" (site survey OR DFR OR drone)',
        ]:
            try:
                resp = gmail.users().messages().list(
                    userId="me", q=query, maxResults=10
                ).execute()
                gmail_connected = True

                messages = resp.get("messages", [])
                # Skip messages we already processed from an earlier query
                messages = [m for m in messages if m["id"] not in seen_msg_ids]
                seen_msg_ids.update(m["id"] for m in messages)
                for msg_stub in messages:
                    msg = gmail.users().messages().get(
                        userId="me", id=msg_stub["id"], format="metadata",
                        metadataHeaders=["From", "To", "Cc", "Reply-To", "Subject"],
                    ).execute()
                    headers = msg.get("payload", {}).get("headers", [])
                    header_contacts = _extract_external_contacts(headers)
                    for c in header_contacts:
                        c.setdefault("title", "")

                    # Parse the full email body for inline contact rosters
                    # and signature blocks (name, title, email, phone)
                    body_contacts = _extract_body_contacts(gmail, msg_stub["id"])

                    # Merge body info into header contacts by email
                    for bc in body_contacts:
                        bc_email = bc.get("email", "").lower()
                        if not bc_email:
                            continue
                        matched = False
                        for hc in header_contacts:
                            if hc["email"].lower() == bc_email:
                                if bc.get("name") and not hc["name"]:
                                    hc["name"] = bc["name"]
                                if bc.get("title") and not hc["title"]:
                                    hc["title"] = bc["title"]
                                matched = True
                                break
                        # Body contact not in headers — add it directly
                        if not matched and not _is_blocked_email(bc_email):
                            header_contacts.append({
                                "name": bc.get("name", ""),
                                "email": bc["email"],
                                "title": bc.get("title", ""),
                            })

                    all_contacts.extend(header_contacts)
            except Exception as e:
                err_str = str(e)
                if "403" in err_str or "401" in err_str or "delegation" in err_str.lower():
                    result["status"] = "auth_error"
                    result["error"] = err_str
                    return result
                print(f"Gmail search error for '{query}': {e}")

    # Also check Google Calendar for events mentioning the agency or city
    # Calendar often has displayNames even when Gmail headers don't
    try:
        calendar = _get_calendar_service()
        if calendar:
            # Search with broader terms too — city name alone can find relevant meetings
            cal_terms = list(search_terms)
            if city and city not in cal_terms:
                cal_terms.append(city)
            for term in cal_terms:
                events_result = calendar.events().list(
                    calendarId="primary",
                    q=term,
                    maxResults=15,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
                for event in events_result.get("items", []):
                    for attendee in event.get("attendees", []):
                        email = attendee.get("email", "")
                        name = attendee.get("displayName", "")
                        if not email or "brincdrones.com" in email.lower():
                            continue
                        if attendee.get("resource"):
                            continue
                        if _is_blocked_email(email):
                            continue
                        if _is_non_person_name(name):
                            continue
                        all_contacts.append({"name": name, "email": email, "title": ""})
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

    # Deduplicate by email, keeping the first name seen and best title
    seen = {}
    for c in all_contacts:
        c.setdefault("title", "")
        email_lower = c["email"].lower()
        if email_lower not in seen:
            seen[email_lower] = c
        else:
            # Merge: keep existing name but update title if we found one
            existing = seen[email_lower]
            if not existing.get("title") and c.get("title"):
                existing["title"] = c["title"]
            if not existing.get("name") and c.get("name"):
                existing["name"] = c["name"]

    unique_contacts = list(seen.values())

    # Fill in missing names from email local part as a last resort
    for c in unique_contacts:
        if not c.get("name"):
            c["name"] = _name_from_email(c["email"])

    result["all_contacts"] = unique_contacts

    # Heuristic assignment:
    # - First external contact found = POC (most likely the person on the kickoff)
    # - Any contact with IT-related keywords in name or email = IT contact
    it_keywords = re.compile(r'\b(it|tech|information.technology|systems|network|infra)\b', re.IGNORECASE)

    for contact in unique_contacts:
        name = contact["name"]
        email = contact["email"]
        title = contact.get("title", "")

        if it_keywords.search(name) or it_keywords.search(email.split("@")[0]) or it_keywords.search(title):
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
