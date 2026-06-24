"""Tests for agency documents and contact-to-POC role matching."""

import pytest
from matcher import assign_contact_to_role


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
