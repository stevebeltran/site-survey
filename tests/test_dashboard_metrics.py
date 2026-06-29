from dashboard_metrics import (
    count_connected_sources,
    count_contacts,
    get_connected_source_statuses,
)


def test_count_contacts_prefers_connected_and_manual_results_without_duplicates():
    state = {
        "customer_info": {
            "contacts": [
                {"name": "Alice", "email": "alice@example.com", "phone": "111"},
            ]
        },
        "agency_contacts": [
            {"name": "Alice Duplicate", "email": "alice@example.com", "phone": "222"},
            {"name": "Bob", "email": "bob@example.com", "phone": "333"},
        ],
    }

    assert count_contacts(state) == 2


def test_count_contacts_falls_back_to_gmail_buffer():
    state = {
        "gmail_found_contacts": [
            {"name": "Carol", "email": "carol@example.com", "phone": ""},
        ]
    }

    assert count_contacts(state) == 1


def test_count_contacts_falls_back_to_legacy_contact_fields():
    state = {
        "customer_info": {
            "poc_name": "Pat Smith",
            "poc_email": "pat@example.com",
            "poc_phone": "111",
            "it_director": "Lee Admin",
            "it_email": "lee@example.com",
            "it_phone": "222",
            "contacts": [],
        }
    }

    assert count_contacts(state) == 2
    assert count_connected_sources(state) == 1


def test_count_connected_sources_uses_harvested_result_state():
    state = {
        "agency_contacts": [{"name": "Alice", "email": "alice@example.com"}],
        "agency_docs": [{"name": "Drive Note"}],
        "agency_calendar": [{"name": "Kickoff"}],
        "jira_results": {"status": "idle"},
        "hubspot_results": {"status": "idle"},
    }

    assert count_connected_sources(state) == 3


def test_get_connected_source_statuses_lists_each_source_individually():
    state = {
        "gmail_found_contacts": [{"name": "Alice", "email": "alice@example.com"}],
        "agency_docs": [{"name": "Drive Note"}],
        "calendar_results": {"status": "no_results"},
        "jira_results": {"status": "connected"},
        "hubspot_results": {"status": "no_credentials"},
    }

    assert get_connected_source_statuses(
        state,
        google_authenticated=True,
        slack_configured=True,
    ) == [
        ("Gmail", "Connected"),
        ("Google Docs", "Connected"),
        ("Calendar", "Authenticated"),
        ("HubSpot", "Needs credentials"),
        ("Jira", "Connected"),
        ("Slack", "Configured"),
    ]


def test_get_connected_source_statuses_uses_auth_state_when_data_not_populated():
    assert get_connected_source_statuses(
        {},
        google_authenticated=True,
        slack_configured=False,
    ) == [
        ("Gmail", "Authenticated"),
        ("Google Docs", "Authenticated"),
        ("Calendar", "Authenticated"),
        ("HubSpot", "Not connected"),
        ("Jira", "Not connected"),
        ("Slack", "Not configured"),
    ]
