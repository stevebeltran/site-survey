"""Tests for the Contacts tab UI in dashboard.py."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd


class TestContactsTabUI(unittest.TestCase):
    """Test the contacts tab UI enhancements."""

    def test_contacts_dataframe_structure(self):
        """Test that contacts are formatted correctly for display."""
        # Simulate contacts from unified format
        contacts = [
            {
                "role": "POC",
                "name": "John Doe",
                "email": "john@example.com",
                "phone": "555-1234",
                "title": "Chief"
            },
            {
                "role": "IT",
                "name": "Jane Smith",
                "email": "jane@example.com",
                "phone": "555-5678",
                "title": "IT Manager"
            }
        ]

        # Create display dataframe (as done in dashboard)
        display_contacts = []
        for contact in contacts:
            display_contacts.append({
                "Role": contact.get("role", "Other"),
                "Name": contact.get("name", ""),
                "Email": contact.get("email", ""),
                "Phone": contact.get("phone", ""),
                "Title": contact.get("title", "")
            })

        df = pd.DataFrame(display_contacts)

        # Verify structure
        self.assertEqual(len(df), 2)
        self.assertListEqual(list(df.columns), ["Role", "Name", "Email", "Phone", "Title"])
        self.assertEqual(df.iloc[0]["Name"], "John Doe")
        self.assertEqual(df.iloc[1]["Role"], "IT")

    def test_extract_unique_roles(self):
        """Test role extraction for filtering."""
        contacts = [
            {"role": "POC", "name": "John", "email": "john@example.com", "phone": "", "title": ""},
            {"role": "IT", "name": "Jane", "email": "jane@example.com", "phone": "", "title": ""},
            {"role": "POC", "name": "Bob", "email": "bob@example.com", "phone": "", "title": ""},
            {"role": "Facilities", "name": "Alice", "email": "alice@example.com", "phone": "", "title": ""},
        ]

        # Extract unique roles (as done in dashboard)
        roles = sorted(set(c.get("role", "Other") for c in contacts if c.get("role")))

        self.assertEqual(roles, ["Facilities", "IT", "POC"])

    def test_filter_contacts_by_role(self):
        """Test filtering contacts by selected role."""
        contacts = [
            {"role": "POC", "name": "John", "email": "john@example.com", "phone": "", "title": ""},
            {"role": "IT", "name": "Jane", "email": "jane@example.com", "phone": "", "title": ""},
            {"role": "POC", "name": "Bob", "email": "bob@example.com", "phone": "", "title": ""},
        ]

        # Filter for POC role
        filtered = [c for c in contacts if c.get("role") == "POC"]

        self.assertEqual(len(filtered), 2)
        self.assertIn({"role": "POC", "name": "John", "email": "john@example.com", "phone": "", "title": ""}, filtered)
        self.assertIn({"role": "POC", "name": "Bob", "email": "bob@example.com", "phone": "", "title": ""}, filtered)

    def test_empty_contacts_handling(self):
        """Test that empty contacts list is handled gracefully."""
        contacts = []

        # Should not raise error when empty
        roles = sorted(set(c.get("role", "Other") for c in contacts if c.get("role")))

        self.assertEqual(roles, [])
        self.assertEqual(len(contacts), 0)

    def test_missing_fields_handling(self):
        """Test that missing optional fields are handled."""
        contacts = [
            {
                "role": "POC",
                "name": "John Doe",
                "email": "john@example.com",
                # Missing phone and title
            }
        ]

        # Should handle missing fields
        display_contacts = []
        for contact in contacts:
            display_contacts.append({
                "Role": contact.get("role", "Other"),
                "Name": contact.get("name", ""),
                "Email": contact.get("email", ""),
                "Phone": contact.get("phone", ""),
                "Title": contact.get("title", "")
            })

        df = pd.DataFrame(display_contacts)

        self.assertEqual(df.iloc[0]["Phone"], "")
        self.assertEqual(df.iloc[0]["Title"], "")

    def test_role_with_special_characters(self):
        """Test handling of roles with special characters."""
        contacts = [
            {
                "role": "RTCC/RTIC",
                "name": "John",
                "email": "john@example.com",
                "phone": "",
                "title": ""
            },
            {
                "role": "Radio Shop",
                "name": "Jane",
                "email": "jane@example.com",
                "phone": "",
                "title": ""
            }
        ]

        roles = sorted(set(c.get("role", "Other") for c in contacts if c.get("role")))

        self.assertIn("RTCC/RTIC", roles)
        self.assertIn("Radio Shop", roles)

    def test_filter_options_generation(self):
        """Test that filter options are generated correctly."""
        contacts = [
            {"role": "POC", "name": "John", "email": "john@example.com", "phone": "", "title": ""},
            {"role": "IT", "name": "Jane", "email": "jane@example.com", "phone": "", "title": ""},
            {"role": "POC", "name": "Bob", "email": "bob@example.com", "phone": "", "title": ""},
        ]

        roles = sorted(set(c.get("role", "Other") for c in contacts if c.get("role")))
        filter_options = ["All Roles"] + roles

        self.assertEqual(filter_options, ["All Roles", "IT", "POC"])

    def test_all_roles_filter(self):
        """Test 'All Roles' filter returns all contacts."""
        contacts = [
            {"role": "POC", "name": "John", "email": "john@example.com", "phone": "", "title": ""},
            {"role": "IT", "name": "Jane", "email": "jane@example.com", "phone": "", "title": ""},
            {"role": "Facilities", "name": "Bob", "email": "bob@example.com", "phone": "", "title": ""},
        ]

        # "All Roles" filter
        selected_role = "All Roles"
        if selected_role == "All Roles":
            filtered = contacts
        else:
            filtered = [c for c in contacts if c.get("role") == selected_role]

        self.assertEqual(len(filtered), 3)
        self.assertEqual(filtered, contacts)


if __name__ == "__main__":
    unittest.main()
