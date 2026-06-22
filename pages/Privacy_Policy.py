import streamlit as st

st.set_page_config(page_title="Privacy Policy - DFR Site Survey", page_icon="🔒")

st.title("Privacy Policy")
st.caption("DFR Site Survey & Deployment Automation Suite")
st.caption("Last updated: June 2026")

st.markdown("""
## Overview

The DFR Site Survey & Deployment Automation Suite ("the App") is an internal tool
built by **BRINC Drones** for use by authorized BRINC employees. This policy
describes how the App handles data when you authenticate with your Google
Workspace account.

## Data We Access

When you sign in with your `@brincdrones.com` Google account, the App requests
access to the following Google API scopes:

| Scope | Purpose |
|-------|---------|
| **Email & Profile** | Verify your identity and restrict access to BRINC employees |
| **Gmail (read-only)** | Search your inbox for prior agency contacts and kickoff call details |
| **Google Calendar (read-only)** | Look up scheduled meetings with survey agencies |
| **Google Drive** | Create folders and upload survey photos, processed images, and reports |

## How Data Is Used

- **Authentication tokens** are stored in your browser session and optionally
  cached locally so you stay signed in across page reloads. Tokens are never
  shared with third parties.
- **Gmail and Calendar data** is read on-demand when you click "Pull Contacts
  from Gmail." Results are displayed in the UI and may be saved into site
  survey metadata files within your Google Drive folder. The App does not
  store, index, or transmit this data outside of your Drive.
- **Survey photos and reports** are uploaded only to the BRINC team Google Drive
  folder you configure.

## Data Storage

- The App runs on Streamlit Cloud. No database is used.
- Processed site data is written to Google Drive and to the local working
  directory for the duration of the session.
- OAuth tokens are stored in the Streamlit session state and a local JSON
  file. They are deleted when you sign out.

## Data Sharing

The App does **not** share your data with any third party. All data remains
within BRINC's Google Workspace and the Streamlit Cloud environment.

## Data Retention

- Session data is cleared when you close the browser tab or sign out.
- Files uploaded to Google Drive persist until manually deleted by a team
  member with access.

## Your Rights

As a BRINC employee using an internal tool, you can:
- **Sign out** at any time to revoke the App's access to your Google account.
- **Revoke access** via your Google Account permissions page at
  [myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## Contact

For questions about this policy, contact the DFR engineering team at
**steven.beltran@brincdrones.com**.
""")
