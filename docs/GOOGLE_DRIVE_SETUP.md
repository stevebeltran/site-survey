# Google Drive Setup for Site Survey App

## One-Time Setup (Admin Only)

### 1. Create Google Cloud Project

- Go to https://console.cloud.google.com/
- Create new project: "Site Survey"
- Enable Google Drive API in the project

### 2. Create Service Account

- Go to Service Accounts (in left menu of Google Cloud Console)
- Create new service account: "site-survey-app"
- Grant "Editor" role
- Create JSON key
- Copy entire JSON content

### 3. Share Google Drive Folder

- The team folder: https://drive.google.com/drive/folders/1FXXNVLaAFWSc1HYDUx8lyaosqF9BJdgL
- Right-click → Share
- Share with service account email (from JSON key, looks like: `xxx@xxx.iam.gserviceaccount.com`)
- Grant "Editor" access

### 4. Configure Streamlit Cloud Secrets

- Go to https://share.streamlit.io/ → select your app → Settings
- In "Secrets" section, paste:
  - `GOOGLE_DRIVE_CREDENTIALS` = entire service account JSON as a string
  - `GOOGLE_DRIVE_TEAM_FOLDER_ID` = `1FXXNVLaAFWSc1HYDUx8lyaosqF9BJdgL`
  - `TEAM_EMAILS` = `steven.beltran@brincdrones.com,david.campise@brincdrones.com`

### 5. Deploy to Streamlit Cloud

- Push code to GitHub (main branch)
- Streamlit Cloud auto-deploys from main branch
- App will be available at: https://site-survey.streamlit.app/

---

## Local Testing (Before Deployment)

1. Copy `.streamlit/secrets.toml.template` to `.streamlit/secrets.toml`
2. Fill in actual credentials from your Google Cloud service account
3. Run: `streamlit run dashboard.py`
4. Test upload and verify files appear in Google Drive

---

## Folder Structure

After setup, Google Drive will contain:

```
1FXXNVLaAFWSc1HYDUx8lyaosqF9BJdgL (Team Site Survey folder)
├── [Client Name]_20260618_143022/
│   ├── 01_Raw_Images/
│   ├── 02_Processed_Sites/
│   ├── 03_Reports/
│   └── 04_Metadata/
└── [Client Name]_20260618_150000/
    ├── 01_Raw_Images/
    ├── 02_Processed_Sites/
    ├── 03_Reports/
    └── 04_Metadata/
```

Each client run creates a timestamped folder with automatic subfolders.

---

## Troubleshooting

**"Google Drive credentials not configured"**
- Check that GOOGLE_DRIVE_CREDENTIALS is set in Streamlit secrets
- Verify the JSON is properly escaped as a string

**"Permission denied" when uploading**
- Verify the service account email has Editor access to the team folder
- Check that the folder ID is correct

**"Failed to initialize Google Drive"**
- Ensure google-auth, googleapiclient, and related packages are installed
- Run: `pip install -r requirements.txt`
