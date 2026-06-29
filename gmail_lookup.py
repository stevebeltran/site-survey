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
import requests


# Emails that should never appear as contacts (exact match on lowercased email)
_BLOCKED_EMAILS = {
    "calendar-notification@google.com",
    "gemini-notes@google.com",
    "drive-shares-dm-noreply@google.com",
}

# Email local-part prefixes that indicate automated/non-person senders
_BLOCKED_EMAIL_PREFIXES = re.compile(
    r'^(noreply|no-reply|donotreply|do-not-reply)@', re.IGNORECASE,
)

# Generic department/non-person local parts (exact match on lowercased local part)
_BLOCKED_EMAIL_LOCAL_PARTS = {
    "police", "fire", "sheriff", "dispatch", "records", "pio",
    "communications", "admin", "info", "support", "helpdesk",
    "publicworks", "facilities", "jail", "corrections",
}


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
    local = lower.split("@")[0]
    # Catch noreply anywhere in local part (e.g. drive-shares-dm-noreply@google.com)
    if re.search(r'noreply|no.reply|donotreply', local):
        return True
    # Catch generic department mailboxes (police@, fire@, dispatch@, etc.)
    if local in _BLOCKED_EMAIL_LOCAL_PARTS:
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
    r'City\s+Manager|Town\s+Manager|Assistant\s+Chief|Chief)\b',
    re.IGNORECASE,
)

# Common signature delimiters
_SIG_DELIMITERS = re.compile(r'^(\s*--\s*$|_{3,}|\u2014{1,}|={3,})')

# Organisation-like words — used to reject false-positive "name" extractions
# from lines such as "Lansing Police Department".
_ORG_WORDS = re.compile(
    r'\b(department|services|division|bureau|office|center|section|unit|'
    r'district|authority|commission|board|council|agency|administration|'
    r'police|fire|city|town|village|county|state|municipal)\b',
    re.IGNORECASE,
)


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
                contacts.append({"name": name, "title": title, "email": email, "phone": ""})
        i += 1

    # --- Pass 2: parse signature blocks throughout the message ---
    # In reply chains the sender's signature sits ABOVE a reply separator
    # (e.g. ________________________________ or --).  Scan the region above
    # each delimiter as well as after the last one so we capture every
    # participant's contact details (especially phone numbers).
    delimiter_indices = [idx for idx, line in enumerate(lines) if _SIG_DELIMITERS.match(line)]

    sig_segments = []
    for d_idx in delimiter_indices:
        start = max(0, d_idx - 15)
        sig_segments.append(lines[start:d_idx])
    if delimiter_indices:
        sig_segments.append(lines[delimiter_indices[-1] + 1:])
    else:
        sig_segments.append(lines[-15:])

    # Plausible person name: 2+ capitalised words, allows periods/hyphens/apostrophes
    _name_like = re.compile(r"^[A-Z][a-zA-Z.'\-]+(?:\s+[A-Z][a-zA-Z.'\-]+)+$")

    for seg_lines in sig_segments:
        sig_title = None
        sig_name = None
        sig_email = None
        sig_phone = None
        title_line_idx = None

        for idx, line in enumerate(seg_lines):
            stripped = line.strip()
            if not stripped:
                continue
            if sig_title is None:
                tm = _TITLE_KEYWORDS.search(stripped)
                if tm:
                    matched_keyword = tm.group(0)
                    # Check if line has both title and name on the same line.
                    # e.g. "Deputy Chief Mike Hynek" or "Mike Hynek, Deputy Chief"
                    after_title = stripped[tm.end():].strip().lstrip(',-|').strip()
                    before_title = stripped[:tm.start()].strip().rstrip(',-|').strip()
                    if after_title and _name_like.match(after_title) and not _ORG_WORDS.search(after_title):
                        sig_title = matched_keyword
                        sig_name = after_title
                    elif before_title and _name_like.match(before_title) and not _ORG_WORDS.search(before_title):
                        sig_title = matched_keyword
                        sig_name = before_title
                    else:
                        sig_title = stripped
                    title_line_idx = idx
            if sig_email is None:
                em = _email_re.search(stripped)
                if em:
                    sig_email = em.group(0)
            if sig_phone is None:
                pm = _phone_re.search(stripped)
                if pm:
                    sig_phone = pm.group(0)

        # Name: look backwards from the title line if the name wasn't already
        # found on the title line itself.  In typical signatures the name sits
        # directly above the title ("John Emery\nIT Manager").
        if title_line_idx is not None and sig_name is None:
            for idx in range(title_line_idx - 1, max(title_line_idx - 4, -1), -1):
                stripped = seg_lines[idx].strip()
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
            sig_email_lower = (sig_email or "").lower()
            if sig_email_lower:
                # Merge with existing contact if same email already found
                existing = next((c for c in contacts if c["email"].lower() == sig_email_lower), None)
                if existing:
                    if sig_title and not existing.get("title"):
                        existing["title"] = sig_title
                    if sig_phone and not existing.get("phone"):
                        existing["phone"] = sig_phone
                    if sig_name and not existing.get("name"):
                        existing["name"] = sig_name
                else:
                    contacts.append({
                        "name": sig_name or "",
                        "title": sig_title or "",
                        "email": sig_email,
                        "phone": sig_phone or "",
                    })
            else:
                # No email in signature — try to match by name
                matched = False
                if sig_name:
                    sig_name_lower = sig_name.lower()
                    for c in contacts:
                        c_name = c.get("name", "").lower()
                        if c_name and (sig_name_lower == c_name or sig_name_lower in c_name or c_name in sig_name_lower):
                            if sig_title and not c.get("title"):
                                c["title"] = sig_title
                            if sig_phone and not c.get("phone"):
                                c["phone"] = sig_phone
                            matched = True
                            break
                if not matched:
                    contacts.append({
                        "name": sig_name or "",
                        "title": sig_title or "",
                        "email": "",
                        "phone": sig_phone or "",
                    })

    return contacts


# ---------------------------------------------------------------------------
# Shared: build broadened search terms for agency + city
# ---------------------------------------------------------------------------
_AGENCY_ABBREVS = {
    "police department": "PD",
    "sheriff's office": "SO",
    "sheriffs office": "SO",
    "fire department": "FD",
    "public safety": "DPS",
    "department of public safety": "DPS",
}


def _build_search_terms(agency_name, city=None):
    """Return a list of search terms ordered broadest-match first.

    Always includes:
      1. The full agency name  ("West Memphis Police Department")
      2. An abbreviated form   ("West Memphis PD") — if a known suffix matches
      3. The city alone        ("West Memphis")    — if provided

    Duplicates are removed while preserving order.
    """
    terms = [agency_name]

    # Generate abbreviated variant (e.g. "Police Department" → "PD")
    lower = agency_name.lower()
    for suffix, abbrev in _AGENCY_ABBREVS.items():
        if lower.endswith(suffix):
            prefix = agency_name[: len(agency_name) - len(suffix)].rstrip()
            short = f"{prefix} {abbrev}"
            if short != agency_name:
                terms.append(short)
            break

    # Always include city — even when it already appears inside agency_name,
    # because searching "West Memphis" will match folders named
    # "West Memphis PD" that the full name would miss.
    if city:
        terms.append(city)

    # Deduplicate while keeping order
    seen = set()
    unique = []
    for t in terms:
        key = t.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(t)
    return unique


def _infer_city_from_agency_name(agency_name):
    """Best-effort city extraction from an agency label."""
    if not agency_name:
        return ""

    label = str(agency_name).strip()
    if not label:
        return ""

    # Prefer the left side of a comma-delimited label like "Zionsville PD, IN".
    if "," in label:
        label = label.split(",", 1)[0].strip()

    label = re.sub(
        r"\b(police department|sheriff's office|sheriffs office|fire department|public safety|department of public safety|pd|so|fd|dps)\b\.?$",
        "",
        label,
        flags=re.IGNORECASE,
    ).strip()
    label = re.sub(r"\s+", " ", label)
    return label


def search_gmail_for_contacts(agency_name, city=None):
    """Search Gmail for threads mentioning the agency and extract external contacts.

    Searches for kickoff calls, calendar invites, and general correspondence
    with the agency. Returns a dict with unified contacts array format.

    Args:
        agency_name: e.g. "Lansing Police Department"
        city: e.g. "Lansing" (optional, broadens search)

    Returns:
        dict with keys:
            status: "connected", "no_results", or "auth_error"
            contacts: list of unified contact dicts [{"role", "name", "email", "phone", "title"}]
            error: error string if status is auth_error
    """
    from contact_model import normalize_contact

    result = {
        "status": "no_results",  # "connected", "no_results", or "auth_error"
        "contacts": [],  # unified format: [{"role", "name", "email", "phone", "title"}]
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
    search_terms = _build_search_terms(agency_name, city)

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
                    userId="me", q=query, maxResults=20
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
                        c.setdefault("phone", "")

                    # Parse the full email body for inline contact rosters
                    # and signature blocks (name, title, email, phone)
                    body_contacts = _extract_body_contacts(gmail, msg_stub["id"])

                    # Merge body info into header contacts by email,
                    # falling back to name matching for signature blocks
                    # that have a title but no email address.
                    for bc in body_contacts:
                        bc_email = bc.get("email", "").lower()
                        bc_name = bc.get("name", "").strip()
                        bc_title = bc.get("title", "")
                        bc_phone = bc.get("phone", "")
                        if bc_email:
                            matched = False
                            for hc in header_contacts:
                                if hc["email"].lower() == bc_email:
                                    if bc_name and not hc["name"]:
                                        hc["name"] = bc_name
                                    if bc_title and not hc.get("title"):
                                        hc["title"] = bc_title
                                    if bc_phone and not hc.get("phone"):
                                        hc["phone"] = bc_phone
                                    matched = True
                                    break
                            # Body contact not in headers — add it directly
                            if not matched and not _is_blocked_email(bc_email):
                                header_contacts.append({
                                    "name": bc_name,
                                    "email": bc["email"],
                                    "title": bc_title,
                                    "phone": bc_phone,
                                })
                        elif bc_name and bc_title:
                            # No email in signature — match by name
                            bc_lower = bc_name.lower()
                            for hc in header_contacts:
                                hc_name = hc.get("name", "").lower()
                                if hc_name and (
                                    bc_lower == hc_name
                                    or bc_lower in hc_name
                                    or hc_name in bc_lower
                                ):
                                    if not hc.get("title"):
                                        hc["title"] = bc_title
                                    if bc_phone and not hc.get("phone"):
                                        hc["phone"] = bc_phone
                                    break

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
                        all_contacts.append({"name": name, "email": email, "title": "", "phone": ""})
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

    # Deduplicate by email, keeping the first name seen and best title/phone
    seen = {}
    for c in all_contacts:
        c.setdefault("title", "")
        c.setdefault("phone", "")
        email_lower = c["email"].lower()
        if email_lower not in seen:
            seen[email_lower] = c
        else:
            # Merge: keep existing name but update title/phone if we found one
            existing = seen[email_lower]
            if not existing.get("title") and c.get("title"):
                existing["title"] = c["title"]
            if not existing.get("name") and c.get("name"):
                existing["name"] = c["name"]
            if not existing.get("phone") and c.get("phone"):
                existing["phone"] = c["phone"]

    unique_contacts = list(seen.values())

    # Fill in missing names from email local part as a last resort
    for c in unique_contacts:
        if not c.get("name"):
            c["name"] = _name_from_email(c["email"])

    # Assign roles using heuristic:
    # - Any contact with IT-related keywords in name or email = IT
    # - Others = POC
    it_keywords = re.compile(r'\b(it|tech|information.technology|systems|network|infra)\b', re.IGNORECASE)

    unified_contacts = []
    for contact in unique_contacts:
        name = contact["name"]
        email = contact["email"]
        title = contact.get("title", "")
        phone = contact.get("phone", "")

        # Assign role based on heuristics
        if it_keywords.search(name) or it_keywords.search(email.split("@")[0]) or it_keywords.search(title):
            role = "IT"
        else:
            role = "POC"

        # Normalize and add to contacts array
        normalized = normalize_contact(
            role=role,
            name=name,
            email=email,
            phone=phone,
            title=title
        )
        unified_contacts.append(normalized)

    result["contacts"] = unified_contacts
    return result


# ---------------------------------------------------------------------------
# Google Drive: Gemini Notes & Folder Search
# ---------------------------------------------------------------------------

def _get_drive_service():
    """Build a Google Drive API service using the current user's OAuth credentials."""
    creds = google_oauth.get_credentials()
    if not creds:
        return None
    return build("drive", "v3", credentials=creds)


def _extract_specs_from_snippet(snippet):
    """Extract infrastructure specs from a Gemini notes content snippet.

    Parses known patterns from meeting notes: power, network, deployment,
    SSO, bandwidth, site visit dates, etc.

    Returns dict of extracted fields (only populated keys).
    """
    specs = {}
    lower = snippet.lower()

    # Power / electrical
    power_match = re.search(r'(\d{3})\s*[vV](?:olt)?\s*(?:/|and)?\s*(\d{1,2})\s*[aA](?:mp)?', snippet)
    if power_match:
        specs["power_circuit_requirements"] = f"{power_match.group(1)}V / {power_match.group(2)}A Dedicated Circuit"

    # Network / VLAN
    if "isolated vlan" in lower or "separate vlan" in lower:
        net = "DHCP on isolated VLAN"
        if "unrestricted outbound" in lower:
            net += " (unrestricted outbound)"
        specs["internet_ethernet_access"] = net
    elif "dhcp" in lower:
        specs["internet_ethernet_access"] = "DHCP"

    # Bandwidth
    bw_match = re.search(r'(\d{3,4})\s*(?:megabit|mbps|meg)', lower)
    if bw_match:
        specs["bandwidth_requirement"] = f"{bw_match.group(1)} Mbps"

    # SSO
    if "azure" in lower and "sso" in lower:
        specs["sso_provider"] = "Microsoft Azure SSO"
    elif "microsoft" in lower and ("single sign" in lower or "sso" in lower):
        specs["sso_provider"] = "Microsoft SSO"

    # Deployment count
    drone_match = re.search(r'(\d+)\s*(?:total\s*)?drones?\s*(?:and\s*)?(\d+)?\s*(?:docking\s*)?stations?', lower)
    if drone_match:
        drones = drone_match.group(1)
        stations = drone_match.group(2) or drones
        specs["deployment_config"] = f"{drones} drones / {stations} stations"

    # Rooftop
    if "rooftop" in lower and ("install" in lower or "deploy" in lower or "station" in lower):
        specs["mount_type"] = "Rooftop"

    # Part 91
    if "part 91" in lower:
        specs["waiver_type"] = "Part 91"
    elif "part 107" in lower:
        specs["waiver_type"] = "Part 107"

    # Installation / delivery date — look for "week of <date>", "install date", "installation date",
    # "delivery date", "target date", "go-live", etc.
    date_patterns = [
        r'(?:week\s+of)\s+([A-Z][a-z]+\.?\s+\d{1,2}(?:,?\s*\d{4})?)',
        r'(?:install(?:ation)?|delivery|target|go[\s-]?live|implementation)\s+(?:date|window|timeframe)?\s*[:\-–]?\s*([A-Z][a-z]+\.?\s+\d{1,2}(?:,?\s*\d{4})?)',
        r'(?:install(?:ation)?|delivery|target|go[\s-]?live|implementation)\s+(?:date|window|timeframe)?\s*[:\-–]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(?:install(?:ation)?|delivery|deploy(?:ment)?)\s+(?:is\s+)?(?:scheduled|planned|set)\s+(?:for\s+)?([A-Z][a-z]+\.?\s+\d{1,2}(?:,?\s*\d{4})?)',
    ]
    for pat in date_patterns:
        m = re.search(pat, snippet, re.IGNORECASE)
        if m:
            date_str = m.group(1).strip().rstrip(".")
            # Prefix with "Week of" if that was the pattern
            if "week of" in (m.group(0) or "").lower():
                specs["survey_delivery_target"] = f"Week of {date_str}"
            else:
                specs["survey_delivery_target"] = date_str
            break

    return specs


def search_drive_for_gemini_notes(agency_name, city=None):
    """Search Google Drive for Gemini meeting notes and related folders.

    Looks for documents titled "Notes by Gemini" mentioning the agency or city,
    plus any Drive folders matching the agency name.

    Args:
        agency_name: e.g. "Zionsville PD" or "St. Louis Metro PD"
        city: e.g. "Zionsville" (optional, broadens search)

    Returns:
        dict with keys:
            gemini_notes: list of {title, url, date, specs}
            drive_folders: list of {name, url, id}
            status: "connected", "no_results", or "auth_error"
            error: error string if auth fails
    """
    result = {
        "gemini_notes": [],
        "drive_folders": [],
        "extracted_specs": {},
        "status": "no_results",
        "error": "",
    }

    try:
        drive = _get_drive_service()
        if not drive:
            result["status"] = "auth_error"
            result["error"] = "Google credentials not available."
            return result
    except Exception as e:
        result["status"] = "auth_error"
        result["error"] = str(e)
        return result

    connected = False

    # Build search terms — always include city separately so shorter folder
    # names like "West Memphis PD" match even when the city appears inside
    # the full agency name "West Memphis Police Department".
    search_terms = _build_search_terms(agency_name, city)

    # Search for Gemini notes documents
    seen_ids = set()
    for term in search_terms:
        # Escape single quotes for the Drive API query
        escaped = term.replace("'", "\\'")
        for query in [
            f"title contains 'Notes by Gemini' and fullText contains '{escaped}' and trashed=false",
            f"title contains '{escaped}' and title contains 'DFR' and mimeType='application/vnd.google-apps.document' and trashed=false",
        ]:
            try:
                resp = drive.files().list(
                    q=query,
                    spaces="drive",
                    fields="files(id, name, webViewLink, modifiedTime, owners)",
                    pageSize=10,
                    orderBy="modifiedTime desc",
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                ).execute()
                connected = True

                for f in resp.get("files", []):
                    if f["id"] in seen_ids:
                        continue
                    seen_ids.add(f["id"])

                    # Try to extract content snippet for spec parsing
                    specs = {}
                    try:
                        content = drive.files().export(
                            fileId=f["id"], mimeType="text/plain"
                        ).execute()
                        if isinstance(content, bytes):
                            content = content.decode("utf-8", errors="replace")
                        specs = _extract_specs_from_snippet(content[:5000])
                    except Exception:
                        pass

                    result["gemini_notes"].append({
                        "title": f.get("name", ""),
                        "url": f.get("webViewLink", ""),
                        "date": f.get("modifiedTime", "")[:10],
                        "specs": specs,
                    })
            except Exception as e:
                err_str = str(e)
                if "403" in err_str or "401" in err_str:
                    result["status"] = "auth_error"
                    result["error"] = err_str
                    return result

    # Search for agency folders in Drive
    for term in search_terms:
        escaped = term.replace("'", "\\'")
        try:
            resp = drive.files().list(
                q=f"name contains '{escaped}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
                spaces="drive",
                fields="files(id, name, webViewLink)",
                pageSize=5,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            connected = True
            for f in resp.get("files", []):
                if f["id"] not in seen_ids:
                    seen_ids.add(f["id"])
                    result["drive_folders"].append({
                        "name": f.get("name", ""),
                        "url": f.get("webViewLink", ""),
                        "id": f["id"],
                    })
        except Exception:
            pass

    # Merge all extracted specs across notes
    merged_specs = {}
    for note in result["gemini_notes"]:
        for k, v in note.get("specs", {}).items():
            if k not in merged_specs:
                merged_specs[k] = v
    result["extracted_specs"] = merged_specs

    if result["gemini_notes"] or result["drive_folders"]:
        result["status"] = "connected"
    elif connected:
        result["status"] = "no_results"

    return result


# ---------------------------------------------------------------------------
# Jira: Ticket Search by Agency Name
# ---------------------------------------------------------------------------

def search_jira_for_tickets(agency_name, city=None, jira_url=None, jira_email=None, jira_token=None):
    """Search Jira for tickets mentioning the agency name.

    Uses Jira REST API v3 with Basic Auth (email + API token).
    Searches across all projects using text search.

    Args:
        agency_name: e.g. "Lansing PD"
        jira_url: Atlassian instance URL, e.g. "https://brincdrones.atlassian.net"
        jira_email: User email for Basic Auth
        jira_token: API token for Basic Auth

    Returns:
        dict with keys:
            tickets: list of {key, summary, status, url, assignee}
            status: "connected", "no_results", "no_credentials", or "error"
            error: error string if request fails
    """
    result = {
        "tickets": [],
        "search_terms": [],
        "status": "no_credentials",
        "error": "",
    }

    if not jira_url or not jira_email or not jira_token:
        return result

    # Clean URL
    jira_url = jira_url.rstrip("/")

    lookup_city = city or _infer_city_from_agency_name(agency_name)
    search_terms = _build_search_terms(agency_name, lookup_city)
    result["search_terms"] = search_terms

    seen_issue_keys = set()

    try:
        for term in search_terms:
            jql = f'text ~ "{term}" ORDER BY updated DESC'
            resp = requests.get(
                f"{jira_url}/rest/api/3/search",
                params={"jql": jql, "maxResults": 20, "fields": "summary,status,assignee"},
                auth=(jira_email, jira_token),
                timeout=15,
            )
            if resp.status_code == 401:
                result["status"] = "error"
                result["error"] = "Jira authentication failed (401). Check email/token."
                return result
            if resp.status_code == 403:
                result["status"] = "error"
                result["error"] = "Jira access denied (403). Check permissions."
                return result
            resp.raise_for_status()

            data = resp.json()
            for issue in data.get("issues", []):
                key = issue.get("key", "")
                if not key or key in seen_issue_keys:
                    continue
                seen_issue_keys.add(key)
                fields = issue.get("fields", {})
                assignee_obj = fields.get("assignee")
                result["tickets"].append({
                    "key": key,
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", ""),
                    "url": f"{jira_url}/browse/{key}",
                    "assignee": assignee_obj.get("displayName", "") if assignee_obj else "",
                })

        result["status"] = "connected" if result["tickets"] else "no_results"

    except requests.exceptions.RequestException as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# HubSpot: Company & Deal Search by Agency Name
# ---------------------------------------------------------------------------

def search_hubspot_for_records(agency_name, hubspot_token=None):
    """Search HubSpot for companies and deals matching the agency name.

    Uses HubSpot CRM v3 API with Private App access token.

    Args:
        agency_name: e.g. "Lansing PD"
        hubspot_token: Private app access token

    Returns:
        dict with keys:
            companies: list of {name, url, id}
            deals: list of {name, stage, url, id, amount, close_date}
            status: "connected", "no_results", "no_credentials", or "error"
            error: error string if request fails
    """
    import requests

    result = {
        "companies": [],
        "deals": [],
        "status": "no_credentials",
        "error": "",
    }

    if not hubspot_token:
        return result

    headers = {
        "Authorization": f"Bearer {hubspot_token}",
        "Content-Type": "application/json",
    }

    # Search companies by name
    try:
        resp = requests.post(
            "https://api.hubapi.com/crm/v3/objects/companies/search",
            headers=headers,
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "name",
                        "operator": "CONTAINS_TOKEN",
                        "value": agency_name,
                    }]
                }],
                "properties": ["name", "domain", "hs_object_id"],
                "limit": 10,
            },
            timeout=15,
        )
        if resp.status_code == 401:
            result["status"] = "error"
            result["error"] = "HubSpot authentication failed (401). Check access token."
            return result
        resp.raise_for_status()

        companies_data = resp.json()
        company_ids = []
        for co in companies_data.get("results", []):
            props = co.get("properties", {})
            co_id = co.get("id", "")
            company_ids.append(co_id)
            result["companies"].append({
                "name": props.get("name", ""),
                "url": f"https://app.hubspot.com/contacts/{co_id}/company/{co_id}" if co_id else "",
                "id": co_id,
            })

    except requests.exceptions.RequestException as e:
        result["status"] = "error"
        result["error"] = f"Company search failed: {e}"
        return result

    # For each company, get associated deals
    for co_id in company_ids[:5]:
        try:
            resp = requests.get(
                f"https://api.hubapi.com/crm/v3/objects/companies/{co_id}/associations/deals",
                headers=headers,
                timeout=15,
            )
            if resp.status_code != 200:
                continue
            assoc_data = resp.json()
            deal_ids = [r.get("id") for r in assoc_data.get("results", []) if r.get("id")]

            for deal_id in deal_ids[:10]:
                deal_resp = requests.get(
                    f"https://api.hubapi.com/crm/v3/objects/deals/{deal_id}",
                    headers=headers,
                    params={"properties": "dealname,dealstage,amount,closedate,hs_object_id"},
                    timeout=15,
                )
                if deal_resp.status_code != 200:
                    continue
                deal = deal_resp.json()
                dprops = deal.get("properties", {})
                result["deals"].append({
                    "name": dprops.get("dealname", ""),
                    "stage": dprops.get("dealstage", ""),
                    "url": f"https://app.hubspot.com/contacts/{co_id}/deal/{deal_id}" if deal_id else "",
                    "id": deal_id,
                    "amount": dprops.get("amount", ""),
                    "close_date": dprops.get("closedate", ""),
                })
        except requests.exceptions.RequestException:
            continue

    if result["companies"] or result["deals"]:
        result["status"] = "connected"
    else:
        result["status"] = "no_results"


# ---------------------------------------------------------------------------
# Google Calendar: Events Search by Agency Name
# ---------------------------------------------------------------------------

def search_calendar_for_events(agency_name, city=None):
    """Search Google Calendar for events/meetings related to the agency.

    Returns:
        {
            "status": "connected" | "no_results" | "auth_error",
            "events": [{"title", "date", "url", "attendees_count"}],
            "error": str (on auth_error only),
        }
    """
    result = {"status": "no_results", "events": []}

    try:
        calendar = _get_calendar_service()
        if not calendar:
            result["status"] = "auth_error"
            result["error"] = "Could not connect to Google Calendar."
            return result

        search_terms = _build_search_terms(agency_name, city)

        seen_ids = set()
        events_out = []

        for term in search_terms:
            try:
                resp = calendar.events().list(
                    calendarId="primary",
                    q=term,
                    maxResults=20,
                    singleEvents=True,
                    orderBy="startTime",
                ).execute()
                for event in resp.get("items", []):
                    eid = event.get("id", "")
                    if eid in seen_ids:
                        continue
                    seen_ids.add(eid)
                    title = event.get("summary", "(No title)")
                    start = event.get("start", {})
                    date_str = start.get("dateTime", start.get("date", ""))
                    url = event.get("htmlLink", "")
                    attendees = event.get("attendees", [])
                    external = [
                        a for a in attendees
                        if not a.get("resource")
                        and "brincdrones.com" not in a.get("email", "").lower()
                    ]
                    events_out.append({
                        "title": title,
                        "date": date_str,
                        "url": url,
                        "attendees_count": len(external),
                    })
            except Exception as e:
                print(f"Calendar event search error for '{term}': {e}")

        # Sort descending by date so most recent first
        events_out.sort(key=lambda e: e["date"], reverse=True)

        if events_out:
            result["status"] = "connected"
            result["events"] = events_out
        else:
            result["status"] = "no_results"

    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "401" in err_str:
            result["status"] = "auth_error"
            result["error"] = err_str
        else:
            print(f"Calendar search_calendar_for_events error: {e}")

    return result


# ---------------------------------------------------------------------------
# Department Calendar Events Search
# ---------------------------------------------------------------------------

def search_department_calendar_events(dept_name: str, dept_domain: str) -> list:
    """Search Google Calendar for events matching department name and attendees.

    Finds events where BOTH conditions are true:
    1. Department/location name in event title or description (fuzzy match ≥80% similarity)
    2. At least one attendee from the department domain

    Args:
        dept_name: Department name, e.g., "West Memphis Police"
        dept_domain: Department domain, e.g., "memphispd.gov"

    Returns:
        List of event dicts with keys:
            - name: Event title
            - date: Formatted as "Mon DD, YYYY" (e.g., "Jun 20, 2026")
            - time: Formatted as "HH:MM AM/PM" (e.g., "2:34 PM") or "All day"
            - attendee_count: Number of accepted/pending attendees (excluded declined)
            - url: Event URL (htmlLink)

        Returns empty list on auth errors or if no matching events found.

    Example:
        >>> events = search_department_calendar_events("West Memphis Police", "memphispd.gov")
        >>> len(events) > 0
        True
        >>> events[0]["name"]
        'West Memphis Police Deployment Meeting'
    """
    from datetime import datetime
    from fuzzywuzzy import fuzz

    result = []

    try:
        calendar = _get_calendar_service()
        if not calendar:
            print(f"Calendar service unavailable for search_department_calendar_events")
            return []
    except Exception as e:
        print(f"Error initializing Calendar service: {e}")
        return []

    try:
        # Search using dept_name as query term
        events_resp = calendar.events().list(
            calendarId="primary",
            q=dept_name,
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = events_resp.get("items", [])
        if not events:
            return []

        for event in events:
            # Check condition 1: dept_name match in title or description
            summary = event.get("summary", "").strip()
            description = event.get("description", "").strip()

            # Use token_set_ratio for flexible matching (ignores word order)
            title_match = fuzz.token_set_ratio(dept_name.lower(), summary.lower())
            desc_match = fuzz.token_set_ratio(dept_name.lower(), description.lower())
            has_name_match = title_match >= 80 or desc_match >= 80

            if not has_name_match:
                continue

            # Check condition 2: at least one attendee from dept_domain
            attendees = event.get("attendees", [])
            has_dept_attendee = any(
                dept_domain.lower() in attendee.get("email", "").lower()
                for attendee in attendees
            )

            if not has_dept_attendee:
                continue

            # Both conditions met — extract event details
            # Format date
            start = event.get("start", {})
            start_datetime = start.get("dateTime")
            start_date = start.get("date")

            date_str = ""
            time_str = "All day"

            if start_datetime:
                # Parse ISO 8601 datetime
                try:
                    dt = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
                    # Format date as "Mon DD, YYYY"
                    date_str = dt.strftime("%a %d, %Y")
                    # Format time as "HH:MM AM/PM"
                    time_str = dt.strftime("%I:%M %p").lstrip("0")
                except Exception:
                    date_str = start_datetime[:10] if start_datetime else ""
                    time_str = "All day"
            elif start_date:
                # All-day event
                try:
                    d = datetime.strptime(start_date, "%Y-%m-%d")
                    date_str = d.strftime("%a %d, %Y")
                    time_str = "All day"
                except Exception:
                    date_str = start_date
                    time_str = "All day"

            # Count attendees: accepted/pending (exclude declined)
            attendee_count = 0
            for attendee in attendees:
                response_status = attendee.get("responseStatus", "needsAction")
                # Count accepted, tentativelyAccepted, and needsAction
                # Exclude only explicitly declined and resources
                if response_status != "declined" and not attendee.get("resource"):
                    attendee_count += 1

            invite_contacts = _extract_invite_contacts(attendees, dept_domain)

            result.append({
                "name": summary,
                "date": date_str,
                "time": time_str,
                "attendee_count": attendee_count,
                "url": event.get("htmlLink", ""),
                "contacts": invite_contacts,
            })

    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "401" in err_str or "delegation" in err_str.lower():
            print(f"Calendar authentication error for search_department_calendar_events: {e}")
        else:
            print(f"Error searching calendar for department events: {e}")

    return result


def _extract_invite_contacts(attendees: list, dept_domain: str) -> list:
    """Return contact rows derived from relevant calendar invite attendees."""
    dept_domain = (dept_domain or "").strip().lower()
    contacts = []
    seen = set()

    for attendee in attendees or []:
        email = (attendee.get("email") or "").strip()
        email_lower = email.lower()
        if not email_lower:
            continue
        if attendee.get("resource"):
            continue
        if "brincdrones.com" in email_lower:
            continue
        if dept_domain and dept_domain not in email_lower:
            continue
        if _is_blocked_email(email):
            continue

        name = (attendee.get("displayName") or "").strip()
        if name and _is_non_person_name(name):
            continue
        if not name:
            name = email.split("@", 1)[0]

        if email_lower in seen:
            continue
        seen.add(email_lower)
        contacts.append({
            "name": name,
            "email": email,
            "title": "",
            "phone": "",
        })

    return contacts


# ---------------------------------------------------------------------------
# Department Contact Extraction from Gmail
# ---------------------------------------------------------------------------

def extract_department_contacts(domain: str) -> list:
    """Extract unique contacts from emails originating from a specific domain.

    Searches Gmail for all emails from the specified domain (e.g., "memphispd.gov")
    and extracts sender contact information (name, email, title, phone) from the
    From headers. Deduplicates by email address.

    Args:
        domain: Email domain to search for, e.g., "memphispd.gov"

    Returns:
        List of contact dicts with keys:
            - name: Display name extracted from From header (or empty string)
            - email: Email address
            - title: Empty string (not extracted from domain emails)
            - phone: Empty string (not extracted from domain emails)

        Returns empty list on auth errors or if no emails found.

    Example:
        >>> contacts = extract_department_contacts("memphispd.gov")
        >>> len(contacts) > 0
        True
        >>> contacts[0]["email"]
        'officer@memphispd.gov'
    """
    try:
        gmail = _get_gmail_service()
        if not gmail:
            print(f"Gmail service unavailable for extract_department_contacts({domain})")
            return []
    except Exception as e:
        print(f"Error initializing Gmail service for domain {domain}: {e}")
        return []

    try:
        # Search for emails from the specified domain
        query = f"from:{domain}"
        resp = gmail.users().messages().list(
            userId="me",
            q=query,
            maxResults=50,
        ).execute()

        messages = resp.get("messages", [])
        if not messages:
            return []

        seen_emails = {}  # email_lower -> contact_dict

        for msg_stub in messages:
            try:
                # Fetch the message metadata to get From header
                msg = gmail.users().messages().get(
                    userId="me",
                    id=msg_stub["id"],
                    format="metadata",
                    metadataHeaders=["From"],
                ).execute()

                headers = msg.get("payload", {}).get("headers", [])
                for header in headers:
                    if header.get("name", "").lower() == "from":
                        from_value = header.get("value", "")
                        # Parse "Name <email@domain>" format
                        display_name, email = parseaddr(from_value)
                        if not email:
                            continue

                        email_lower = email.lower()

                        # Skip if already seen
                        if email_lower in seen_emails:
                            continue

                        # Skip if from internal domain (brincdrones.com)
                        if "brincdrones.com" in email_lower:
                            continue

                        # Skip blocked emails
                        if _is_blocked_email(email):
                            continue

                        # Add to seen_emails
                        seen_emails[email_lower] = {
                            "name": display_name or "",
                            "email": email,
                            "title": "",
                            "phone": "",
                        }
                        break  # Only process first From header per message

            except Exception as e:
                print(f"Error processing message {msg_stub.get('id')}: {e}")
                continue

        return list(seen_emails.values())

    except Exception as e:
        err_str = str(e)
        if "403" in err_str or "401" in err_str or "delegation" in err_str.lower():
            print(f"Gmail authentication error for domain {domain}: {e}")
        else:
            print(f"Error extracting contacts from domain {domain}: {e}")
        return []
