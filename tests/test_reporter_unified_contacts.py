"""Tests for reporter.py using unified contacts format."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import reporter


class TestReporterUnifiedContacts(unittest.TestCase):
    """Test that reporter correctly uses unified contacts array format."""

    def test_format_role_contact_uses_unified_array(self):
        """Test that _format_role_contact extracts from unified contacts array."""
        customer_info = {
            "contacts": [
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
                    "title": "IT Director"
                }
            ],
            # Old fields (should be ignored in favor of unified array)
            "poc_name": "Old John",
            "poc_email": "old@example.com"
        }

        # Test POC extraction
        result = reporter._format_role_contact(customer_info, "POC", "poc_name", "poc_email", "poc_phone")
        self.assertIn("John Doe", result)
        self.assertIn("john@example.com", result)
        self.assertIn("555-1234", result)

        # Test IT extraction
        result = reporter._format_role_contact(customer_info, "IT", "it_director", "it_email", "it_phone")
        self.assertIn("Jane Smith", result)
        self.assertIn("jane@example.com", result)
        self.assertIn("555-5678", result)

    def test_format_role_contact_fallback_to_legacy(self):
        """Test that _format_role_contact falls back to legacy fields when unified array is empty."""
        customer_info = {
            "contacts": [],
            "poc_name": "Legacy John",
            "poc_email": "legacy@example.com",
            "poc_phone": "555-9999"
        }

        result = reporter._format_role_contact(customer_info, "POC", "poc_name", "poc_email", "poc_phone")
        self.assertIn("Legacy John", result)
        self.assertIn("legacy@example.com", result)
        self.assertIn("555-9999", result)

    def test_format_role_contact_prefers_unified_over_legacy(self):
        """Test that unified contacts array takes precedence over legacy fields."""
        customer_info = {
            "contacts": [
                {
                    "role": "POC",
                    "name": "New John",
                    "email": "new@example.com",
                    "phone": "555-1111",
                    "title": ""
                }
            ],
            "poc_name": "Old John",
            "poc_email": "old@example.com",
            "poc_phone": "555-9999"
        }

        result = reporter._format_role_contact(customer_info, "POC", "poc_name", "poc_email", "poc_phone")
        # Should use new unified format, not legacy
        self.assertIn("New John", result)
        self.assertIn("new@example.com", result)
        self.assertIn("555-1111", result)
        self.assertNotIn("Old John", result)

    def test_format_role_contact_returns_dna_when_not_found(self):
        """Test that DNA default is returned when role not found."""
        customer_info = {
            "contacts": [
                {
                    "role": "POC",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "",
                    "title": ""
                }
            ]
        }

        # Try to find a role that doesn't exist
        result = reporter._format_role_contact(customer_info, "Nonexistent", "name_key", "email_key")
        self.assertEqual(result, "DNA")

    def test_normalized_contact_rows_uses_unified_array(self):
        """Test that _normalized_contact_rows returns unified contacts."""
        customer_info = {
            "contacts": [
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
        }

        rows = reporter._normalized_contact_rows(customer_info)
        self.assertEqual(len(rows), 2)

        # Check first row (POC)
        row0 = rows[0]
        self.assertEqual(row0[0], "POC")  # role
        self.assertEqual(row0[1], "John Doe")  # name
        self.assertEqual(row0[2], "Chief")  # title
        self.assertEqual(row0[3], "john@example.com")  # email
        self.assertEqual(row0[4], "555-1234")  # phone

        # Check second row (IT)
        row1 = rows[1]
        self.assertEqual(row1[0], "IT")  # role
        self.assertEqual(row1[1], "Jane Smith")  # name
        self.assertEqual(row1[2], "IT Manager")  # title

    def test_normalized_contact_rows_only_includes_non_empty_contacts(self):
        """Test that _normalized_contact_rows only includes contacts with at least some data."""
        customer_info = {
            "contacts": [
                {
                    "role": "POC",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "",
                    "title": ""
                },
                {
                    "role": "IT",
                    "name": "Jane Smith",
                    "email": "",
                    "phone": "",
                    "title": ""
                },
                {
                    "role": "Other",
                    "name": "Bob Johnson",
                    "email": "bob@example.com",
                    "phone": "555-8888",
                    "title": "Manager"
                }
            ]
        }

        rows = reporter._normalized_contact_rows(customer_info)
        # Should have 3 rows (all have some meaningful data)
        self.assertEqual(len(rows), 3)

    def test_add_poc_table_uses_unified_contacts(self):
        """Test that _add_poc_table correctly uses unified contacts format."""
        from docx import Document

        doc = Document()
        customer_info = {
            "contacts": [
                {
                    "role": "POC",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "phone": "555-1234",
                    "title": ""
                },
                {
                    "role": "IT",
                    "name": "Jane Smith",
                    "email": "jane@example.com",
                    "phone": "555-5678",
                    "title": "IT Director"
                }
            ]
        }

        # This should not raise an error
        reporter._add_poc_table(doc, customer_info)

        # Check that the document has tables (at least 2: POC table and contacts table)
        self.assertGreaterEqual(len(doc.tables), 1)

    def test_mixed_unified_and_legacy_contacts(self):
        """Test that reporter handles mix of unified array and legacy fields gracefully."""
        customer_info = {
            "contacts": [
                {
                    "role": "POC",
                    "name": "New POC",
                    "email": "newpoc@example.com",
                    "phone": "555-1111",
                    "title": ""
                }
            ],
            # Legacy fields that should be ignored if unified array exists
            "it_director": "Old IT Director",
            "it_email": "oldit@example.com",
            "it_phone": "555-9999"
        }

        # POC should come from unified array
        poc_result = reporter._format_role_contact(customer_info, "POC", "poc_name", "poc_email", "poc_phone")
        self.assertIn("New POC", poc_result)
        self.assertIn("newpoc@example.com", poc_result)

        # IT should fall back to legacy fields
        it_result = reporter._format_role_contact(customer_info, "IT", "it_director", "it_email", "it_phone")
        self.assertIn("Old IT Director", it_result)
        self.assertIn("oldit@example.com", it_result)


class TestExtractContactForReportRole(unittest.TestCase):
    """Test extraction of contacts for specific roles from unified format."""

    def test_extract_contact_for_report_role_success(self):
        """Test successful extraction of contact by role."""
        from contact_model import extract_contact_for_report_role

        contacts = [
            {"role": "POC", "name": "John Doe", "email": "john@example.com", "phone": "555-1234", "title": ""},
            {"role": "IT", "name": "Jane Smith", "email": "jane@example.com", "phone": "555-5678", "title": ""}
        ]

        name, email, phone = extract_contact_for_report_role(contacts, "POC")
        self.assertEqual(name, "John Doe")
        self.assertEqual(email, "john@example.com")
        self.assertEqual(phone, "555-1234")

    def test_extract_contact_for_report_role_not_found(self):
        """Test extraction when role doesn't exist."""
        from contact_model import extract_contact_for_report_role

        contacts = [
            {"role": "POC", "name": "John Doe", "email": "john@example.com", "phone": "555-1234", "title": ""}
        ]

        name, email, phone = extract_contact_for_report_role(contacts, "Nonexistent")
        self.assertEqual(name, "")
        self.assertEqual(email, "")
        self.assertEqual(phone, "")

    def test_extract_contact_for_report_role_empty_list(self):
        """Test extraction from empty contacts list."""
        from contact_model import extract_contact_for_report_role

        name, email, phone = extract_contact_for_report_role([], "POC")
        self.assertEqual(name, "")
        self.assertEqual(email, "")
        self.assertEqual(phone, "")


if __name__ == "__main__":
    unittest.main()
