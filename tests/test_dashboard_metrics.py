from dashboard_metrics import count_connected_sources, count_contacts


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


def test_count_connected_sources_uses_harvested_result_state():
    state = {
        "agency_contacts": [{"name": "Alice", "email": "alice@example.com"}],
        "agency_docs": [{"name": "Drive Note"}],
        "agency_calendar": [{"name": "Kickoff"}],
        "jira_results": {"status": "idle"},
        "hubspot_results": {"status": "idle"},
    }

    assert count_connected_sources(state) == 3

