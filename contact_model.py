"""Unified contact data model and migration layer for contact information.

Consolidates two contact systems:
1. Agency Information Contacts: flexible editable rows in customer_info["contacts"]
2. Points of Contact: auto-discovered role fields (poc_name, poc_email, etc.)

Provides normalization, migration, and extraction utilities for consistent contact handling.
"""

# Standard roles and their field mappings in the old flat format
STANDARD_ROLES = {
    "POC": ("poc_name", "poc_email", "poc_phone"),
    "IT": ("it_director", "it_email", "it_phone"),
    "RTCC": ("rtcc_name", "rtcc_email", "rtcc_phone"),
    "Facilities": ("facilities_engineer", "facilities_email", "facilities_phone"),
    "Radio Shop": ("radio_shop_name", "radio_shop_email", "radio_shop_phone"),
}


def normalize_contact(role="", name="", email="", phone="", title=""):
    """Normalize a contact dict with the unified schema.

    Args:
        role: Contact role (defaults to "Other" if empty)
        name: Person name (stripped)
        email: Email address (stripped)
        phone: Phone number (stripped)
        title: Job title (stripped)

    Returns:
        dict with keys: role, name, title, email, phone
    """
    return {
        "role": (role or "").strip() or "Other",
        "name": (name or "").strip(),
        "title": (title or "").strip(),
        "email": (email or "").strip(),
        "phone": (phone or "").strip(),
    }


def is_contact_empty(contact):
    """Check if a contact has no meaningful data.

    Args:
        contact: Contact dict with unified schema

    Returns:
        True if all of name, email, phone, title are empty
    """
    return not any([
        contact.get("name", "").strip(),
        contact.get("email", "").strip(),
        contact.get("phone", "").strip(),
        contact.get("title", "").strip(),
    ])


def migrate_flat_to_array(customer_info):
    """Migrate old flat role fields to unified contacts array.

    Converts individual role fields (poc_name, it_director, etc.) to customer_info["contacts"] array.

    Features:
    - Idempotent: safe to call multiple times
    - Deduplicates by email (keeps first occurrence)
    - Removes old flat fields after migration
    - Handles partial fields and already-migrated format

    Args:
        customer_info: dict with potentially old flat fields

    Returns:
        dict with migrated contacts array and old fields removed
    """
    if customer_info is None:
        customer_info = {}

    # Make a copy to avoid mutating input
    result = dict(customer_info)

    # If contacts array already exists, we're already migrated
    if "contacts" in result:
        # But clean up any old flat fields if they exist
        for role_fields in STANDARD_ROLES.values():
            for field in role_fields:
                result.pop(field, None)
        return result

    # Start with empty contacts list
    contacts = []
    seen_emails = set()

    # Iterate through standard roles in order
    for role, (name_key, email_key, phone_key) in STANDARD_ROLES.items():
        # Check if this role has any data
        name = result.get(name_key, "").strip()
        email = result.get(email_key, "").strip()
        phone = result.get(phone_key, "").strip()

        # Only create a contact if at least one field has data
        if name or email or phone:
            # Dedup by email: skip if we've already seen this email
            if email and email in seen_emails:
                continue

            if email:
                seen_emails.add(email)

            contact = normalize_contact(role, name, email, phone, "")
            contacts.append(contact)

    # Store migrated contacts
    result["contacts"] = contacts

    # Remove old flat fields
    for role_fields in STANDARD_ROLES.values():
        for field in role_fields:
            result.pop(field, None)

    return result


def extract_contact_for_report_role(contacts, role):
    """Extract contact info for a specific role for report generation.

    Args:
        contacts: list of contact dicts with unified schema
        role: role to search for

    Returns:
        tuple of (name, email, phone) for the first matching contact
        Returns ("", "", "") if role not found
    """
    if not contacts:
        return ("", "", "")

    for contact in contacts:
        if contact.get("role") == role:
            return (
                contact.get("name", ""),
                contact.get("email", ""),
                contact.get("phone", ""),
            )

    return ("", "", "")
