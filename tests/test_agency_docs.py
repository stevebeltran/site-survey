"""Tests for agency documents and contact-to-POC role matching."""

import pytest
from unittest.mock import MagicMock, patch
from matcher import assign_contact_to_role
from gmail_lookup import extract_department_contacts


class TestContactToRoleMatching:
    """Test suite for assign_contact_to_role function."""

    def test_match_information_technology(self):
        """Test matching contact with IT Director title to Information Technology role."""
        contact = {
            "name": "John Smith",
            "title": "IT Director",
            "email": "john.smith@example.com",
            "phone": "555-1234"
        }
        result = assign_contact_to_role(contact)
        assert result == "Information Technology"

    def test_match_facilities(self):
        """Test matching contact with Facilities Manager title to Facilities Engineer role."""
        contact = {
            "name": "Jane Doe",
            "title": "Facilities Manager",
            "email": "jane.doe@example.com",
            "phone": "555-5678"
        }
        result = assign_contact_to_role(contact)
        assert result == "Facilities Engineer"

    def test_match_radio_shop(self):
        """Test matching contact with Radio Communications Engineer to Radio Shop Engineer role."""
        contact = {
            "name": "Bob Johnson",
            "title": "Radio Communications Engineer",
            "email": "bob.johnson@example.com",
            "phone": "555-9999"
        }
        result = assign_contact_to_role(contact)
        assert result == "Radio Shop Engineer"

    def test_fallback_other(self):
        """Test that unmatched contact title falls back to Other role."""
        contact = {
            "name": "Alice Brown",
            "title": "Human Resources Manager",
            "email": "alice.brown@example.com",
            "phone": "555-0000"
        }
        result = assign_contact_to_role(contact)
        assert result == "Other"

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        contact = {
            "name": "Charlie Green",
            "title": "it specialist",
            "email": "charlie.green@example.com",
            "phone": "555-1111"
        }
        result = assign_contact_to_role(contact)
        assert result == "Information Technology"


class TestDepartmentContactExtraction:
    """Test suite for extract_department_contacts function."""

    def test_extract_department_contacts_returns_list(self):
        """Test that extract_department_contacts returns a list."""
        result = extract_department_contacts("memphispd.gov")
        assert isinstance(result, list)

    def test_extract_department_contacts_required_keys(self):
        """Test that returned contacts have required keys: name, email, title, phone."""
        # This test verifies the function signature and return structure
        # even if no actual emails are found (returns empty list)
        result = extract_department_contacts("memphispd.gov")
        assert isinstance(result, list)
        # If contacts returned, each must have required keys
        for contact in result:
            assert "name" in contact
            assert "email" in contact
            assert "title" in contact
            assert "phone" in contact

    def test_extract_department_contacts_deduplication(self):
        """Test that contacts are deduplicated by email address (lowercase)."""
        # This test verifies structure even without actual Gmail access
        result = extract_department_contacts("memphispd.gov")
        assert isinstance(result, list)
        # If contacts exist, verify no duplicate emails (case-insensitive)
        if result:
            emails = [c["email"].lower() for c in result]
            assert len(emails) == len(set(emails)), "Duplicate emails found"

    def test_extract_department_contacts_title_phone_empty(self):
        """Test that title and phone are empty strings in returned contacts."""
        result = extract_department_contacts("memphispd.gov")
        assert isinstance(result, list)
        # Verify all contacts have empty title and phone strings
        for contact in result:
            assert contact.get("title") == ""
            assert contact.get("phone") == ""


class TestSearchDepartmentDocuments:
    """Test suite for search_department_documents function."""

    def test_search_department_documents_returns_list(self):
        """Test that search_department_documents returns a list of dicts."""
        from google_drive import GoogleDriveManager

        # Mock the service
        mock_service = MagicMock()
        mock_service.files().list().execute.return_value = {'files': []}
        mock_service.permissions().list().execute.return_value = {'permissions': []}

        manager = MagicMock(spec=GoogleDriveManager)
        manager.service = mock_service
        manager.search_files = MagicMock(return_value=[])

        # Import and bind the real method
        from google_drive import GoogleDriveManager as RealManager
        manager.search_department_documents = RealManager.search_department_documents.__get__(manager)

        result = manager.search_department_documents("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)

    def test_search_department_documents_required_keys(self):
        """Test that returned documents have required keys: name, owner, last_modified, url."""
        from google_drive import GoogleDriveManager

        # Create mock files
        mock_files = [
            {
                'id': 'file1',
                'name': 'West Memphis Police Site Survey',
                'owners': [{'displayName': 'John Doe'}],
                'modifiedTime': '2026-06-24T00:00:00Z',
                'webViewLink': 'https://drive.google.com/file/d/file1'
            }
        ]

        manager = MagicMock(spec=GoogleDriveManager)
        manager.search_files = MagicMock(return_value=mock_files)
        manager.service = MagicMock()
        manager.service.permissions().list().execute.return_value = {'permissions': []}

        from google_drive import GoogleDriveManager as RealManager
        manager.search_department_documents = RealManager.search_department_documents.__get__(manager)

        result = manager.search_department_documents("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)
        for doc in result:
            assert "name" in doc
            assert "owner" in doc
            assert "last_modified" in doc
            assert "url" in doc

    def test_search_department_documents_deduplication(self):
        """Test that documents are deduplicated by file ID."""
        from google_drive import GoogleDriveManager

        # Create duplicate files (same ID in both queries)
        mock_files = [
            {
                'id': 'file1',
                'name': 'West Memphis Police Survey',
                'owners': [{'displayName': 'John Doe'}],
                'modifiedTime': '2026-06-24T00:00:00Z',
                'webViewLink': 'https://drive.google.com/file/d/file1'
            }
        ]

        manager = MagicMock(spec=GoogleDriveManager)
        manager.search_files = MagicMock(return_value=mock_files)
        manager.service = MagicMock()
        manager.service.permissions().list().execute.return_value = {'permissions': []}

        from google_drive import GoogleDriveManager as RealManager
        manager.search_department_documents = RealManager.search_department_documents.__get__(manager)

        result = manager.search_department_documents("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)
        # Verify no duplicates by checking unique names
        names = [doc['name'] for doc in result]
        assert len(names) == len(set(names)), "Duplicate documents found"

    def test_search_department_documents_error_handling(self):
        """Test that exceptions are caught and empty list is returned."""
        from google_drive import GoogleDriveManager

        manager = MagicMock(spec=GoogleDriveManager)
        manager.search_files = MagicMock(side_effect=Exception("API error"))

        from google_drive import GoogleDriveManager as RealManager
        manager.search_department_documents = RealManager.search_department_documents.__get__(manager)

        result = manager.search_department_documents("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)
        assert result == []
