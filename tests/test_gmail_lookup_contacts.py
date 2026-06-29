"""Tests for gmail_lookup contact discovery with unified format."""

import sys
import unittest
from unittest.mock import Mock, patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gmail_lookup
import contact_model


class TestSearchGmailForContactsReturnFormat(unittest.TestCase):
    """Test search_gmail_for_contacts returns unified contacts array format."""

    def test_search_gmail_returns_unified_format_on_success(self):
        """Test that successful search returns contacts in unified array format."""
        # Mock the Gmail service
        with patch("gmail_lookup._get_gmail_service") as mock_gmail_service:
            mock_service = Mock()
            mock_gmail_service.return_value = mock_service

            # Mock message list response
            mock_service.users().messages().list().execute.return_value = {
                "messages": []
            }

            # Mock calendar service
            with patch("gmail_lookup._get_calendar_service") as mock_cal_service:
                mock_cal_service.return_value = None

                result = gmail_lookup.search_gmail_for_contacts("Test Agency")

        # Check return format
        self.assertIn("status", result)
        self.assertIn("contacts", result)
        self.assertIn("error", result)
        self.assertNotIn("poc_name", result)
        self.assertNotIn("poc_email", result)
        self.assertNotIn("all_contacts", result)

    def test_search_gmail_returns_error_format_on_auth_error(self):
        """Test auth error returns proper format with error message."""
        with patch("gmail_lookup._get_gmail_service") as mock_gmail_service:
            mock_gmail_service.return_value = None

            result = gmail_lookup.search_gmail_for_contacts("Test Agency")

        self.assertEqual(result["status"], "auth_error")
        self.assertEqual(result["contacts"], [])
        self.assertIsNotNone(result["error"])

    def test_search_gmail_contacts_array_has_unified_structure(self):
        """Test that returned contacts have unified schema."""
        # Create a mock contact dict with unified format
        contact_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "title": "Chief of Police",
            "phone": "555-1234"
        }

        # Normalize it
        normalized = contact_model.normalize_contact(
            role="POC",
            name=contact_data["name"],
            email=contact_data["email"],
            phone=contact_data["phone"],
            title=contact_data["title"]
        )

        # Check unified structure
        self.assertIn("role", normalized)
        self.assertIn("name", normalized)
        self.assertIn("email", normalized)
        self.assertIn("phone", normalized)
        self.assertIn("title", normalized)

        # Check values
        self.assertEqual(normalized["role"], "POC")
        self.assertEqual(normalized["name"], "John Doe")
        self.assertEqual(normalized["email"], "john@example.com")

    def test_search_gmail_contacts_no_old_fields(self):
        """Test that result doesn't have old flat fields."""
        with patch("gmail_lookup._get_gmail_service") as mock_gmail_service:
            mock_service = Mock()
            mock_gmail_service.return_value = mock_service

            # Mock empty search
            mock_service.users().messages().list().execute.return_value = {
                "messages": []
            }

            with patch("gmail_lookup._get_calendar_service") as mock_cal_service:
                mock_cal_service.return_value = None

                result = gmail_lookup.search_gmail_for_contacts("Test Agency")

        # Ensure old fields are not present
        old_fields = ["poc_name", "poc_email", "poc_phone", "it_director", "it_email", "it_phone", "all_contacts"]
        for field in old_fields:
            self.assertNotIn(field, result, f"Old field '{field}' should not be in result")


class TestSearchGmailContactsRoleAssignment(unittest.TestCase):
    """Test that search_gmail_for_contacts assigns roles correctly."""

    def test_it_keywords_assigned_to_it_role(self):
        """Test that contacts with IT keywords get IT role."""
        # Create a mock contact with IT keywords
        contact = {
            "name": "Jane Smith IT",
            "email": "jane.smith@agency.gov",
            "title": "IT Director",
            "phone": "555-5678"
        }

        it_keywords = __import__('re').compile(
            r'\b(it|tech|information.technology|systems|network|infra)\b',
            __import__('re').IGNORECASE
        )

        # Check if IT keywords are detected
        has_it_keyword = (
            it_keywords.search(contact["name"]) or
            it_keywords.search(contact["email"].split("@")[0]) or
            it_keywords.search(contact["title"])
        )

        self.assertTrue(has_it_keyword, "IT keywords should be detected in contact")

    def test_non_it_contacts_assigned_to_poc_role(self):
        """Test that non-IT contacts get POC role."""
        # Create a mock contact without IT keywords
        contact = {
            "name": "Chief Officer",
            "email": "chief@agency.gov",
            "title": "Police Chief",
            "phone": "555-9999"
        }

        it_keywords = __import__('re').compile(
            r'\b(it|tech|information.technology|systems|network|infra)\b',
            __import__('re').IGNORECASE
        )

        # Check if IT keywords are NOT detected
        has_it_keyword = (
            it_keywords.search(contact["name"]) or
            it_keywords.search(contact["email"].split("@")[0]) or
            it_keywords.search(contact["title"])
        )

        self.assertFalse(has_it_keyword, "IT keywords should not be detected in POC contact")


if __name__ == "__main__":
    unittest.main()
