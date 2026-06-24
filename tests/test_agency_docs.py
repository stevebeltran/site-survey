"""Tests for agency documents and contact-to-POC role matching."""

import pytest
from unittest.mock import MagicMock, patch
from matcher import assign_contact_to_role
from gmail_lookup import extract_department_contacts, search_department_calendar_events


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


class TestSearchDepartmentCalendarEvents:
    """Test suite for search_department_calendar_events function."""

    def test_search_department_calendar_events_returns_list(self):
        """Test that search_department_calendar_events returns a list of dicts."""
        result = search_department_calendar_events("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)

    def test_search_department_calendar_events_required_keys(self):
        """Test that returned events have required keys: name, date, time, attendee_count, url."""
        result = search_department_calendar_events("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)
        # If events returned, each must have required keys
        for event in result:
            assert "name" in event
            assert "date" in event
            assert "time" in event
            assert "attendee_count" in event
            assert "url" in event

    def test_search_department_calendar_events_date_format(self):
        """Test that returned events have properly formatted dates (Mon DD, YYYY)."""
        result = search_department_calendar_events("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)
        # Verify date format if events exist
        import re
        for event in result:
            date_str = event.get("date", "")
            if date_str:
                # Format: "Mon DD, YYYY" (e.g., "Jun 20, 2026")
                assert re.match(r'^[A-Z][a-z]{2} \d{2}, \d{4}$', date_str), \
                    f"Date '{date_str}' does not match expected format 'Mon DD, YYYY'"

    def test_search_department_calendar_events_time_format(self):
        """Test that returned events have properly formatted times (HH:MM AM/PM or All day)."""
        result = search_department_calendar_events("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)
        # Verify time format if events exist
        import re
        for event in result:
            time_str = event.get("time", "")
            # Either "All day" or "H:MM AM/PM" (leading zero removed)
            assert re.match(r'^(?:All day|\d{1,2}:\d{2}\s(?:AM|PM))$', time_str), \
                f"Time '{time_str}' does not match expected format"

    def test_search_department_calendar_events_attendee_count_non_negative(self):
        """Test that attendee_count is a non-negative integer."""
        result = search_department_calendar_events("West Memphis Police", "memphispd.gov")
        assert isinstance(result, list)
        for event in result:
            count = event.get("attendee_count")
            assert isinstance(count, int)
            assert count >= 0


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


class TestParallelOrchestrator:
    """Test suite for fetch_agency_docs_parallel function."""

    @patch('agency_docs.extract_department_contacts')
    @patch('agency_docs.search_department_calendar_events')
    @patch('agency_docs.GoogleDriveManager')
    @patch('agency_docs.google_oauth.get_credentials')
    def test_fetch_agency_docs_parallel_returns_dict(self, mock_get_creds, mock_drive_manager,
                                                      mock_calendar, mock_gmail):
        """Test that fetch_agency_docs_parallel returns a dict with all required keys."""
        from agency_docs import fetch_agency_docs_parallel

        # Mock all three lookups to return empty results
        mock_get_creds.return_value = MagicMock()
        mock_gmail.return_value = []
        mock_calendar.return_value = []

        mock_manager_instance = MagicMock()
        mock_manager_instance.search_department_documents.return_value = []
        mock_drive_manager.return_value = mock_manager_instance

        result = fetch_agency_docs_parallel("West Memphis Police", "memphispd.gov", {})

        # Verify all four keys are present
        assert isinstance(result, dict)
        assert "contacts" in result
        assert "docs" in result
        assert "events" in result
        assert "errors" in result

    @patch('agency_docs.extract_department_contacts')
    @patch('agency_docs.search_department_calendar_events')
    @patch('agency_docs.GoogleDriveManager')
    @patch('agency_docs.google_oauth.get_credentials')
    def test_fetch_agency_docs_parallel_correct_structure(self, mock_get_creds, mock_drive_manager,
                                                           mock_calendar, mock_gmail):
        """Test that fetch_agency_docs_parallel returns correct data structure."""
        from agency_docs import fetch_agency_docs_parallel

        # Mock lookups with sample data
        mock_get_creds.return_value = MagicMock()

        # Gmail returns contacts with poc_role assigned
        mock_gmail.return_value = [
            {"name": "John Smith", "email": "john@example.com", "title": "IT Director", "phone": "555-1234"}
        ]
        mock_calendar.return_value = [
            {"name": "Team Meeting", "date": "Jun 24, 2026", "time": "2:00 PM", "attendee_count": 5, "url": "..."}
        ]

        mock_manager_instance = MagicMock()
        mock_manager_instance.search_department_documents.return_value = [
            {"name": "Site Survey", "owner": "John Doe", "last_modified": "2026-06-24", "url": "..."}
        ]
        mock_drive_manager.return_value = mock_manager_instance

        result = fetch_agency_docs_parallel("West Memphis Police", "memphispd.gov", {})

        # Verify structure
        assert isinstance(result["contacts"], list)
        assert isinstance(result["docs"], list)
        assert isinstance(result["events"], list)
        assert isinstance(result["errors"], dict)

    @patch('agency_docs.extract_department_contacts')
    @patch('agency_docs.search_department_calendar_events')
    @patch('agency_docs.GoogleDriveManager')
    @patch('agency_docs.google_oauth.get_credentials')
    def test_fetch_agency_docs_parallel_assigns_poc_role(self, mock_get_creds, mock_drive_manager,
                                                          mock_calendar, mock_gmail):
        """Test that contacts have poc_role assigned by assign_contact_to_role."""
        from agency_docs import fetch_agency_docs_parallel

        mock_get_creds.return_value = MagicMock()

        # Gmail returns contacts
        mock_gmail.return_value = [
            {"name": "John Smith", "email": "john@example.com", "title": "IT Director", "phone": "555-1234"}
        ]
        mock_calendar.return_value = []

        mock_manager_instance = MagicMock()
        mock_manager_instance.search_department_documents.return_value = []
        mock_drive_manager.return_value = mock_manager_instance

        result = fetch_agency_docs_parallel("West Memphis Police", "memphispd.gov", {})

        # Verify contacts have poc_role assigned
        assert len(result["contacts"]) > 0
        for contact in result["contacts"]:
            assert "poc_role" in contact
            assert contact["poc_role"] in [
                "Information Technology", "Facilities Engineer", "Radio Shop Engineer",
                "RTCC/RTIC", "Crane Contractor", "Tower Climber Contractor",
                "BRINC Project Manager", "Other"
            ]

    @patch('agency_docs.extract_department_contacts')
    @patch('agency_docs.search_department_calendar_events')
    @patch('agency_docs.GoogleDriveManager')
    @patch('agency_docs.google_oauth.get_credentials')
    def test_fetch_agency_docs_parallel_handles_gmail_error(self, mock_get_creds, mock_drive_manager,
                                                             mock_calendar, mock_gmail):
        """Test that Gmail errors are recorded but other lookups continue."""
        from agency_docs import fetch_agency_docs_parallel

        mock_get_creds.return_value = MagicMock()
        mock_gmail.side_effect = Exception("Gmail API error")
        mock_calendar.return_value = [{"name": "Meeting", "date": "Jun 24, 2026", "time": "2:00 PM", "attendee_count": 3, "url": "..."}]

        mock_manager_instance = MagicMock()
        mock_manager_instance.search_department_documents.return_value = [{"name": "Doc", "owner": "Jane", "last_modified": "2026-06-24", "url": "..."}]
        mock_drive_manager.return_value = mock_manager_instance

        result = fetch_agency_docs_parallel("West Memphis Police", "memphispd.gov", {})

        # Verify error is recorded
        assert "gmail" in result["errors"]
        # But other results should still be present
        assert isinstance(result["docs"], list)
        assert isinstance(result["events"], list)

    @patch('agency_docs.extract_department_contacts')
    @patch('agency_docs.search_department_calendar_events')
    @patch('agency_docs.GoogleDriveManager')
    @patch('agency_docs.google_oauth.get_credentials')
    def test_fetch_agency_docs_parallel_handles_drive_error(self, mock_get_creds, mock_drive_manager,
                                                             mock_calendar, mock_gmail):
        """Test that Drive errors are recorded but other lookups continue."""
        from agency_docs import fetch_agency_docs_parallel

        mock_get_creds.return_value = None  # Simulate no credentials
        mock_gmail.return_value = [{"name": "John", "email": "john@example.com", "title": "", "phone": ""}]
        mock_calendar.return_value = []

        # Drive manager will handle the None credentials case
        mock_drive_manager.side_effect = Exception("Drive API error")

        result = fetch_agency_docs_parallel("West Memphis Police", "memphispd.gov", {})

        # Verify error is recorded
        assert "drive" in result["errors"]
        # But other results should still be present
        assert isinstance(result["contacts"], list)
        assert isinstance(result["events"], list)

    @patch('agency_docs.extract_department_contacts')
    @patch('agency_docs.search_department_calendar_events')
    @patch('agency_docs.GoogleDriveManager')
    @patch('agency_docs.google_oauth.get_credentials')
    def test_fetch_agency_docs_parallel_handles_calendar_error(self, mock_get_creds, mock_drive_manager,
                                                                mock_calendar, mock_gmail):
        """Test that Calendar errors are recorded but other lookups continue."""
        from agency_docs import fetch_agency_docs_parallel

        mock_get_creds.return_value = MagicMock()
        mock_gmail.return_value = [{"name": "John", "email": "john@example.com", "title": "IT Director", "phone": "555-1234"}]
        mock_calendar.side_effect = Exception("Calendar API error")

        mock_manager_instance = MagicMock()
        mock_manager_instance.search_department_documents.return_value = [{"name": "Doc", "owner": "Jane", "last_modified": "2026-06-24", "url": "..."}]
        mock_drive_manager.return_value = mock_manager_instance

        result = fetch_agency_docs_parallel("West Memphis Police", "memphispd.gov", {})

        # Verify error is recorded
        assert "calendar" in result["errors"]
        # But other results should still be present
        assert isinstance(result["contacts"], list)
        assert isinstance(result["docs"], list)
