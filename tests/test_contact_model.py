"""Tests for unified contact model and migration layer."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import contact_model


class TestNormalizeContact(unittest.TestCase):
    """Test contact normalization."""

    def test_normalize_contact_basic(self):
        """Normalize with all fields provided."""
        result = contact_model.normalize_contact(
            role="POC",
            name="John Doe",
            email="john@test.com",
            phone="555-1234",
            title="Chief"
        )
        self.assertEqual(result["role"], "POC")
        self.assertEqual(result["name"], "John Doe")
        self.assertEqual(result["email"], "john@test.com")
        self.assertEqual(result["phone"], "555-1234")
        self.assertEqual(result["title"], "Chief")

    def test_normalize_contact_defaults(self):
        """Role defaults to 'Other' when empty."""
        result = contact_model.normalize_contact()
        self.assertEqual(result["role"], "Other")
        self.assertEqual(result["name"], "")
        self.assertEqual(result["email"], "")
        self.assertEqual(result["phone"], "")
        self.assertEqual(result["title"], "")

    def test_normalize_contact_strips_whitespace(self):
        """Normalize strips whitespace from all string fields."""
        result = contact_model.normalize_contact(
            role="  POC  ",
            name="  John Doe  ",
            email="  john@test.com  ",
            phone="  555-1234  ",
            title="  Chief  "
        )
        self.assertEqual(result["role"], "POC")
        self.assertEqual(result["name"], "John Doe")
        self.assertEqual(result["email"], "john@test.com")
        self.assertEqual(result["phone"], "555-1234")
        self.assertEqual(result["title"], "Chief")


class TestIsContactEmpty(unittest.TestCase):
    """Test contact emptiness detection."""

    def test_is_contact_empty_when_all_blank(self):
        """Detect empty contact with all blank fields."""
        contact = {
            "role": "Other",
            "name": "",
            "title": "",
            "email": "",
            "phone": ""
        }
        self.assertTrue(contact_model.is_contact_empty(contact))

    def test_is_contact_empty_when_has_name(self):
        """Detect non-empty contact with name."""
        contact = {
            "role": "POC",
            "name": "John Doe",
            "title": "",
            "email": "",
            "phone": ""
        }
        self.assertFalse(contact_model.is_contact_empty(contact))

    def test_is_contact_empty_when_has_email(self):
        """Detect non-empty contact with email."""
        contact = {
            "role": "POC",
            "name": "",
            "title": "",
            "email": "john@test.com",
            "phone": ""
        }
        self.assertFalse(contact_model.is_contact_empty(contact))

    def test_is_contact_empty_when_has_phone(self):
        """Detect non-empty contact with phone."""
        contact = {
            "role": "POC",
            "name": "",
            "title": "",
            "email": "",
            "phone": "555-1234"
        }
        self.assertFalse(contact_model.is_contact_empty(contact))

    def test_is_contact_empty_when_has_title(self):
        """Detect non-empty contact with title."""
        contact = {
            "role": "POC",
            "name": "",
            "title": "Chief",
            "email": "",
            "phone": ""
        }
        self.assertFalse(contact_model.is_contact_empty(contact))


class TestMigrateFlatToArray(unittest.TestCase):
    """Test migration from flat fields to array format."""

    def test_migrate_flat_to_array_empty(self):
        """Migrate with no old fields present."""
        customer_info = {"agency": "Test Agency"}
        result = contact_model.migrate_flat_to_array(customer_info)

        self.assertIn("contacts", result)
        self.assertEqual(result["contacts"], [])
        self.assertEqual(result["agency"], "Test Agency")

    def test_migrate_flat_to_array_with_poc(self):
        """Migrate one role (POC)."""
        customer_info = {
            "agency": "Test Agency",
            "poc_name": "John Doe",
            "poc_email": "john@test.com",
            "poc_phone": "555-1234"
        }
        result = contact_model.migrate_flat_to_array(customer_info)

        self.assertEqual(len(result["contacts"]), 1)
        contact = result["contacts"][0]
        self.assertEqual(contact["role"], "POC")
        self.assertEqual(contact["name"], "John Doe")
        self.assertEqual(contact["email"], "john@test.com")
        self.assertEqual(contact["phone"], "555-1234")

        # Old fields should be removed
        self.assertNotIn("poc_name", result)
        self.assertNotIn("poc_email", result)
        self.assertNotIn("poc_phone", result)

    def test_migrate_flat_to_array_with_multiple_roles(self):
        """Migrate multiple roles."""
        customer_info = {
            "agency": "Test Agency",
            "poc_name": "John Doe",
            "poc_email": "john@test.com",
            "it_director": "Jane Smith",
            "it_email": "jane@test.com"
        }
        result = contact_model.migrate_flat_to_array(customer_info)

        self.assertEqual(len(result["contacts"]), 2)

        # Check POC
        poc = next((c for c in result["contacts"] if c["role"] == "POC"), None)
        self.assertIsNotNone(poc)
        self.assertEqual(poc["name"], "John Doe")
        self.assertEqual(poc["email"], "john@test.com")

        # Check IT
        it = next((c for c in result["contacts"] if c["role"] == "IT"), None)
        self.assertIsNotNone(it)
        self.assertEqual(it["name"], "Jane Smith")
        self.assertEqual(it["email"], "jane@test.com")

    def test_migrate_flat_to_array_dedup_by_email(self):
        """Dedup duplicate emails (keeps first occurrence)."""
        customer_info = {
            "agency": "Test Agency",
            "poc_name": "John Doe",
            "poc_email": "john@test.com",
            "it_director": "John Again",
            "it_email": "john@test.com"  # Duplicate email
        }
        result = contact_model.migrate_flat_to_array(customer_info)

        # Should have only one contact (POC, since it comes first)
        self.assertEqual(len(result["contacts"]), 1)
        self.assertEqual(result["contacts"][0]["role"], "POC")

    def test_migrate_flat_to_array_already_migrated(self):
        """Handle already-migrated format (idempotent)."""
        customer_info = {
            "agency": "Test Agency",
            "contacts": [
                {"role": "POC", "name": "John Doe", "email": "john@test.com", "phone": "", "title": ""}
            ]
        }
        result = contact_model.migrate_flat_to_array(customer_info)

        # Should be unchanged
        self.assertEqual(len(result["contacts"]), 1)
        self.assertEqual(result["contacts"][0]["name"], "John Doe")
        self.assertNotIn("poc_name", result)

    def test_migrate_flat_to_array_partial_fields(self):
        """Handle partial fields (only name, only email, etc.)."""
        customer_info = {
            "agency": "Test Agency",
            "poc_name": "John Doe",
            # No poc_email, no poc_phone
            "it_email": "it@test.com"
            # No it_director, no it_phone
        }
        result = contact_model.migrate_flat_to_array(customer_info)

        self.assertEqual(len(result["contacts"]), 2)

        # Check POC
        poc = next((c for c in result["contacts"] if c["role"] == "POC"), None)
        self.assertIsNotNone(poc)
        self.assertEqual(poc["name"], "John Doe")
        self.assertEqual(poc["email"], "")

        # Check IT
        it = next((c for c in result["contacts"] if c["role"] == "IT"), None)
        self.assertIsNotNone(it)
        self.assertEqual(it["name"], "")
        self.assertEqual(it["email"], "it@test.com")

    def test_migrate_flat_to_array_idempotent(self):
        """Migration is idempotent (safe to call multiple times)."""
        customer_info = {
            "poc_name": "John",
            "poc_email": "john@test.com"
        }

        first = contact_model.migrate_flat_to_array(customer_info)
        second = contact_model.migrate_flat_to_array(first)

        self.assertEqual(len(first["contacts"]), len(second["contacts"]))
        self.assertEqual(first["contacts"], second["contacts"])


class TestExtractContactForReportRole(unittest.TestCase):
    """Test extracting contact info for report generation."""

    def test_extract_contact_for_report_role(self):
        """Extract by role returns (name, email, phone)."""
        contacts = [
            {"role": "POC", "name": "John Doe", "email": "john@test.com", "phone": "555-1234", "title": ""},
            {"role": "IT", "name": "Jane Smith", "email": "jane@test.com", "phone": "555-5678", "title": ""}
        ]

        name, email, phone = contact_model.extract_contact_for_report_role(contacts, "POC")

        self.assertEqual(name, "John Doe")
        self.assertEqual(email, "john@test.com")
        self.assertEqual(phone, "555-1234")

    def test_extract_contact_for_report_role_not_found(self):
        """Extract missing role returns blank tuple."""
        contacts = [
            {"role": "POC", "name": "John Doe", "email": "john@test.com", "phone": "555-1234", "title": ""}
        ]

        name, email, phone = contact_model.extract_contact_for_report_role(contacts, "IT")

        self.assertEqual(name, "")
        self.assertEqual(email, "")
        self.assertEqual(phone, "")

    def test_extract_contact_for_report_role_empty_list(self):
        """Extract from empty contacts list returns blanks."""
        contacts = []

        name, email, phone = contact_model.extract_contact_for_report_role(contacts, "POC")

        self.assertEqual(name, "")
        self.assertEqual(email, "")
        self.assertEqual(phone, "")


if __name__ == "__main__":
    unittest.main()
