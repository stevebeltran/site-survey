from contact_rows import build_initial_poc_rows, sync_customer_info_from_poc_rows


def _uid_source():
    value = 0

    def _next():
        nonlocal value
        value += 1
        return value

    return _next


def test_build_initial_poc_rows_seeds_expected_legacy_contacts_once():
    customer_info = {
        "poc_name": "Pat Smith",
        "poc_email": "pat@example.com",
        "poc_phone": "111-222-3333",
        "it_director": "Lee Admin",
        "it_email": "lee@example.com",
        "it_phone": "444-555-6666",
    }

    rows = build_initial_poc_rows(customer_info, _uid_source())

    assert rows == [
        {
            "_uid": 1,
            "role": "POC",
            "name": "Pat Smith",
            "email": "pat@example.com",
            "title": "",
            "phone": "111-222-3333",
        },
        {
            "_uid": 2,
            "role": "IT",
            "name": "Lee Admin",
            "email": "lee@example.com",
            "title": "",
            "phone": "444-555-6666",
        },
    ]


def test_build_initial_poc_rows_does_not_readd_removed_contact_on_rerun():
    customer_info = {
        "it_director": "Lee Admin",
        "it_email": "lee@example.com",
        "it_phone": "444-555-6666",
    }
    next_uid = _uid_source()

    rows = build_initial_poc_rows(customer_info, next_uid)
    rows.pop(0)

    assert rows == []


def test_build_initial_poc_rows_prefers_structured_contacts():
    customer_info = {
        "contacts": [
            {
                "role": "Facilities",
                "name": "Jordan Tech",
                "title": "Engineer",
                "email": "jordan@example.com",
                "phone": "999-111-2222",
            }
        ],
        "it_director": "Legacy IT",
        "it_email": "legacy@example.com",
        "it_phone": "123-123-1234",
    }

    rows = build_initial_poc_rows(customer_info, _uid_source())

    assert rows == [
        {
            "_uid": 1,
            "role": "Facilities",
            "name": "Jordan Tech",
            "title": "Engineer",
            "email": "jordan@example.com",
            "phone": "999-111-2222",
        }
    ]


def test_sync_customer_info_from_poc_rows_uses_widget_state_values():
    customer_info = {
        "poc_name": "",
        "poc_email": "",
        "poc_phone": "",
        "it_director": "",
        "it_email": "",
        "it_phone": "",
        "facilities_engineer": "",
        "facilities_email": "",
        "facilities_phone": "",
        "rtcc_name": "",
        "rtcc_email": "",
        "rtcc_phone": "",
        "radio_shop_name": "",
        "radio_shop_email": "",
        "radio_shop_phone": "",
        "contacts": [],
    }
    poc_rows = [{"_uid": 7, "role": "Other", "name": "", "title": "", "email": "", "phone": ""}]
    widget_state = {
        "poc_role_7": "POC",
        "poc_name_7": "Alex Carter",
        "poc_title_7": "Captain",
        "poc_email_7": "alex@example.com",
        "poc_phone_7": "222-333-4444",
    }

    rows = sync_customer_info_from_poc_rows(customer_info, poc_rows, widget_state=widget_state)

    assert rows == [
        {
            "_uid": 7,
            "role": "POC",
            "name": "Alex Carter",
            "title": "Captain",
            "email": "alex@example.com",
            "phone": "222-333-4444",
        }
    ]
    assert customer_info["poc_name"] == "Alex Carter"
    assert customer_info["poc_email"] == "alex@example.com"
    assert customer_info["poc_phone"] == "222-333-4444"
    assert customer_info["contacts"] == [
        {
            "role": "POC",
            "name": "Alex Carter",
            "title": "Captain",
            "email": "alex@example.com",
            "phone": "222-333-4444",
        }
    ]
