"""Pure helpers for dashboard KPI calculations."""


LEGACY_CONTACT_FIELD_GROUPS = (
    ("POC", "poc_name", "poc_email", "poc_phone"),
    ("IT", "it_director", "it_email", "it_phone"),
    ("Facilities", "facilities_engineer", "facilities_email", "facilities_phone"),
    ("RTCC", "rtcc_name", "rtcc_email", "rtcc_phone"),
    ("Radio Shop", "radio_shop_name", "radio_shop_email", "radio_shop_phone"),
)


def _contact_identity(contact: dict) -> tuple:
    """Return a stable identity for deduping contacts across harvest sources."""
    email = (contact.get("email") or "").strip().lower()
    if email:
        return ("email", email)

    name = (contact.get("name") or "").strip().lower()
    phone = (contact.get("phone") or "").strip()
    if name or phone:
        return ("fallback", name, phone)

    return ("empty",)


def _legacy_contacts(customer_info: dict) -> list:
    contacts = []
    for role, name_key, email_key, phone_key in LEGACY_CONTACT_FIELD_GROUPS:
        name = (customer_info.get(name_key) or "").strip()
        email = (customer_info.get(email_key) or "").strip()
        phone = (customer_info.get(phone_key) or "").strip()
        if name or email or phone:
            contacts.append({
                "role": role,
                "name": name,
                "email": email,
                "phone": phone,
            })
    return contacts


def count_contacts(session_state: dict) -> int:
    """Count unique contacts from manual and connected harvest sources."""
    customer_info = session_state.get("customer_info", {}) or {}
    contacts = []
    contacts.extend(customer_info.get("contacts", []) or [])
    contacts.extend(session_state.get("agency_contacts", []) or [])

    if not contacts:
        contacts.extend(session_state.get("gmail_found_contacts", []) or [])
    if not contacts:
        contacts.extend(_legacy_contacts(customer_info))

    seen = set()
    total = 0
    for contact in contacts:
        identity = _contact_identity(contact)
        if identity in seen:
            continue
        seen.add(identity)
        total += 1
    return total


def count_connected_sources(session_state: dict) -> int:
    """Count connected source systems based on harvested state."""
    customer_info = session_state.get("customer_info", {}) or {}

    gmail_connected = bool(
        session_state.get("agency_contacts")
        or session_state.get("gmail_found_contacts")
        or customer_info.get("contacts")
        or _legacy_contacts(customer_info)
    )
    drive_connected = bool(
        session_state.get("drive_gemini_results", {}).get("status") == "connected"
        or session_state.get("agency_docs")
    )
    jira_connected = session_state.get("jira_results", {}).get("status") == "connected"
    hubspot_connected = session_state.get("hubspot_results", {}).get("status") == "connected"
    calendar_connected = bool(
        session_state.get("calendar_results", {}).get("status") == "connected"
        or session_state.get("agency_calendar")
    )

    return sum(
        1
        for connected in (
            gmail_connected,
            drive_connected,
            jira_connected,
            hubspot_connected,
            calendar_connected,
        )
        if connected
    )


def _has_gmail_data(session_state: dict) -> bool:
    customer_info = session_state.get("customer_info", {}) or {}
    return bool(
        session_state.get("agency_contacts")
        or session_state.get("gmail_found_contacts")
        or customer_info.get("contacts")
        or _legacy_contacts(customer_info)
    )


def _has_drive_data(session_state: dict) -> bool:
    return bool(
        session_state.get("drive_gemini_results", {}).get("status") == "connected"
        or session_state.get("agency_docs")
    )


def _has_calendar_data(session_state: dict) -> bool:
    return bool(
        session_state.get("calendar_results", {}).get("status") == "connected"
        or session_state.get("agency_calendar")
    )


def _normalize_status(raw_status: str, *, fallback: str = "Not connected") -> str:
    status_map = {
        "connected": "Connected",
        "no_results": "No results",
        "no_credentials": "Needs credentials",
        "auth_error": "Auth error",
        "error": "Error",
        "idle": fallback,
        "": fallback,
        None: fallback,
    }
    return status_map.get(raw_status, str(raw_status).replace("_", " ").title())


def get_connected_source_statuses(
    session_state: dict,
    *,
    google_authenticated: bool = False,
    slack_configured: bool = False,
) -> list[tuple[str, str]]:
    """Return user-facing per-source statuses for the dashboard."""
    calendar_raw_status = session_state.get("calendar_results", {}).get("status")
    gmail_status = "Connected" if _has_gmail_data(session_state) else (
        "Authenticated" if google_authenticated else "Not connected"
    )
    docs_status = "Connected" if _has_drive_data(session_state) else (
        "Authenticated" if google_authenticated else "Not connected"
    )
    if _has_calendar_data(session_state):
        calendar_status = "Connected"
    elif calendar_raw_status == "auth_error":
        calendar_status = "Auth error"
    elif google_authenticated:
        calendar_status = "Authenticated"
    else:
        calendar_status = _normalize_status(calendar_raw_status)
    hubspot_status = _normalize_status(
        session_state.get("hubspot_results", {}).get("status"),
    )
    jira_status = _normalize_status(
        session_state.get("jira_results", {}).get("status"),
    )
    slack_status = "Configured" if slack_configured else "Not configured"

    return [
        ("Gmail", gmail_status),
        ("Google Docs", docs_status),
        ("Calendar", calendar_status),
        ("HubSpot", hubspot_status),
        ("Jira", jira_status),
        ("Slack", slack_status),
    ]
