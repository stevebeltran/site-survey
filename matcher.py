"""Contact-to-POC role matching module.

Provides functionality to match contact information (name, title, email, phone)
to predefined POC (Point of Contact) roles using fuzzy string matching.
"""

from fuzzywuzzy import fuzz


# Role keyword mappings for POC classification
ROLE_KEYWORDS = {
    "Information Technology": ["it", "tech", "technology", "director", "it director"],
    "Facilities Engineer": ["facilities", "building", "maintenance", "facilities manager"],
    "Radio Shop Engineer": ["radio", "communications", "communications engineer"],
    "RTCC/RTIC": ["rtcc", "rtic"],
    "Crane Contractor": ["crane", "contractor"],
    "Tower Climber Contractor": ["tower", "climber"],
    "BRINC Project Manager": ["brinc", "project manager"],
}

# Fuzzy matching similarity threshold (0-100)
MATCH_THRESHOLD = 80


def assign_contact_to_role(contact: dict) -> str:
    """Assign a POC role to a contact based on fuzzy matching of keywords.

    Takes a contact dictionary with name, title, email, and phone fields.
    Performs case-insensitive fuzzy matching against predefined role keywords
    using token_set_ratio with an 80% similarity threshold.

    Args:
        contact: Dictionary with keys 'name', 'title', 'email', 'phone'

    Returns:
        A role name string (e.g., "Information Technology", "Facilities Engineer")
        or "Other" if no keyword match meets the threshold.

    Example:
        >>> contact = {"name": "John Smith", "title": "IT Director",
        ...            "email": "john@example.com", "phone": "555-1234"}
        >>> assign_contact_to_role(contact)
        'Information Technology'
    """
    # Extract title and convert to lowercase for case-insensitive matching
    title = contact.get("title", "").lower()

    if not title:
        return "Other"

    # Check each role's keyword list
    for role, keywords in ROLE_KEYWORDS.items():
        for keyword in keywords:
            # Use token_set_ratio for fuzzy matching
            similarity = fuzz.token_set_ratio(title, keyword)

            if similarity >= MATCH_THRESHOLD:
                return role

    # Fallback for unmatched contacts
    return "Other"
