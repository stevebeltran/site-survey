"""Deprecated: helpers for initializing and syncing manual contact rows.

DEPRECATED: Use contact_model module instead. This stub is maintained for backward compatibility.
"""

# Import from new unified contact model
from contact_model import STANDARD_ROLES, normalize_contact

# Backward compatibility: expose as ROLE_FIELD_MAP
ROLE_FIELD_MAP = STANDARD_ROLES


# Deprecated: use normalize_contact() instead
def _normalize_row(role="", name="", email="", phone="", title=""):
    """DEPRECATED: use contact_model.normalize_contact() instead."""
    return normalize_contact(role, name, email, phone, title)


def build_initial_poc_rows(customer_info, next_uid):
    """Seed editable rows from structured contacts first, then legacy flat fields."""
    customer_info = customer_info or {}
    rows = []

    for contact in customer_info.get("contacts", []):
        row = _normalize_row(
            contact.get("role", "Other"),
            contact.get("name", ""),
            contact.get("email", ""),
            contact.get("phone", ""),
            contact.get("title", ""),
        )
        if any(row.values()):
            rows.append({"_uid": next_uid(), **row})
    if rows:
        return rows

    for role, (name_key, email_key, phone_key) in ROLE_FIELD_MAP.items():
        if customer_info.get(name_key) or customer_info.get(email_key) or customer_info.get(phone_key):
            rows.append({
                "_uid": next_uid(),
                **_normalize_row(
                    role,
                    customer_info.get(name_key, ""),
                    customer_info.get(email_key, ""),
                    customer_info.get(phone_key, ""),
                ),
            })

    return rows


def sync_customer_info_from_poc_rows(customer_info, poc_rows, widget_state=None):
    """Sync the current editable contact rows back into customer_info."""
    customer_info = customer_info or {}
    widget_state = widget_state or {}
    current_rows = []

    for row in poc_rows or []:
        uid = row.get("_uid")
        current = {
            "_uid": uid,
            "role": widget_state.get(f"poc_role_{uid}", row.get("role", "Other")) or "Other",
            "name": widget_state.get(f"poc_name_{uid}", row.get("name", "")) or "",
            "title": widget_state.get(f"poc_title_{uid}", row.get("title", "")) or "",
            "email": widget_state.get(f"poc_email_{uid}", row.get("email", "")) or "",
            "phone": widget_state.get(f"poc_phone_{uid}", row.get("phone", "")) or "",
        }
        current_rows.append(current)

    for name_key, email_key, phone_key in ROLE_FIELD_MAP.values():
        customer_info[name_key] = ""
        customer_info[email_key] = ""
        customer_info[phone_key] = ""

    contacts = []
    for row in current_rows:
        normalized = _normalize_row(
            row.get("role", "Other"),
            row.get("name", ""),
            row.get("email", ""),
            row.get("phone", ""),
            row.get("title", ""),
        )
        if normalized["name"] or normalized["title"] or normalized["email"] or normalized["phone"]:
            contacts.append(normalized)

        mapped = ROLE_FIELD_MAP.get(normalized["role"])
        if mapped and not customer_info[mapped[0]]:
            customer_info[mapped[0]] = normalized["name"]
            customer_info[mapped[1]] = normalized["email"]
            customer_info[mapped[2]] = normalized["phone"]

    customer_info["contacts"] = contacts
    return current_rows
