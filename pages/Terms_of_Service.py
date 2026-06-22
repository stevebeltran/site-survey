import streamlit as st

st.set_page_config(page_title="Terms of Service - DFR Site Survey", page_icon="📜")

st.title("Terms of Service")
st.caption("DFR Site Survey & Deployment Automation Suite")
st.caption("Last updated: June 2026")

st.markdown("""
## Acceptance of Terms

By accessing and using the DFR Site Survey & Deployment Automation Suite
("the App"), you agree to these Terms of Service. The App is an internal tool
provided by **BRINC Drones** exclusively for authorized BRINC employees.

## Authorized Use

- Access is restricted to users with a valid `@brincdrones.com` Google
  Workspace account.
- The App is intended for DFR site survey processing, infrastructure analysis,
  and deployment report generation.
- You may not use the App for purposes unrelated to BRINC business operations.

## Google API Services

The App's use of Google API services complies with the
[Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy),
including the Limited Use requirements. Specifically:

- The App only requests access to Google data necessary for its stated
  functionality (Gmail contact lookup, Calendar meeting search, Drive file
  management).
- Data obtained from Google APIs is not transferred to third parties.
- Data is not used for advertising or any purpose unrelated to the App's
  core functionality.

## User Responsibilities

- You are responsible for the accuracy of survey data you upload and the
  reports you generate.
- You must not share your authentication credentials or allow unauthorized
  users to access the App through your account.
- You should sign out when finished using the App on shared devices.

## Intellectual Property

The App, including its source code, design, and documentation, is the
property of BRINC Drones. All rights reserved.

## Disclaimer of Warranties

The App is provided "as is" without warranty of any kind. BRINC Drones does
not guarantee uninterrupted or error-free operation. Airspace classifications,
airfield proximity data, and infrastructure analysis results are informational
and should be verified independently before making deployment decisions.

## Limitation of Liability

BRINC Drones shall not be liable for any indirect, incidental, or
consequential damages arising from use of the App, including but not limited
to data loss, service interruptions, or inaccuracies in generated reports.

## Changes to Terms

BRINC Drones reserves the right to modify these terms at any time. Continued
use of the App after changes constitutes acceptance of the updated terms.

## Contact

For questions about these terms, contact the DFR engineering team at
**steven.beltran@brincdrones.com**.
""")
