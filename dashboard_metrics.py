"""Pure helpers for dashboard KPI calculations."""


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


def count_contacts(session_state: dict) -> int:
    """Count unique contacts from manual and connected harvest sources."""
    customer_info = session_state.get("customer_info", {}) or {}
    contacts = []
    contacts.extend(customer_info.get("contacts", []) or [])
    contacts.extend(session_state.get("agency_contacts", []) or [])

    if not contacts:
        contacts.extend(session_state.get("gmail_found_contacts", []) or [])

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
