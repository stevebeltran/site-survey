"""Google Drive API wrapper for authentication and file operations."""

import os
import json
import io
from google.auth.transport.requests import Request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
import streamlit as st


class GoogleDriveManager:
    """Manages Google Drive operations: auth, file upload/download, folder creation."""

    def __init__(self, credentials):
        """
        Initialize with either OAuth Credentials or a service account JSON string.

        Args:
            credentials: google.oauth2.credentials.Credentials object,
                         OR a JSON string of service account credentials
        """
        from google.oauth2.credentials import Credentials
        try:
            if isinstance(credentials, str):
                creds_dict = json.loads(credentials)
                self.credentials = service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=['https://www.googleapis.com/auth/drive']
                )
            else:
                self.credentials = credentials
            self.service = build('drive', 'v3', credentials=self.credentials)
        except Exception as e:
            raise ValueError(f"Failed to initialize Google Drive: {e}")

    def get_or_create_folder(self, parent_folder_id, folder_name):
        """
        Get folder by name in parent, or create if doesn't exist.

        Args:
            parent_folder_id: Google Drive folder ID of parent
            folder_name: Name of folder to find/create

        Returns:
            Folder ID (string)
        """
        # Escape single quotes in folder name for query
        escaped_name = folder_name.replace("'", "\\'")
        query = f"'{parent_folder_id}' in parents and name='{escaped_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
            pageSize=1,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        if results.get('error'):
            raise ValueError(f"Search failed: {results['error']}")

        files = results.get('files', [])
        if files:
            return files[0]['id']

        # Create folder
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = self.service.files().create(
            body=file_metadata,
            fields='id',
            supportsAllDrives=True
        ).execute()

        if folder.get('error'):
            raise ValueError(f"Folder creation failed: {folder['error']}")

        return folder.get('id')

    def upload_file(self, file_path, folder_id, file_name=None):
        """
        Upload file to Google Drive folder.

        Args:
            file_path: Local file path
            folder_id: Google Drive folder ID
            file_name: Optional custom name for file in Drive

        Returns:
            File ID (string)
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_name = file_name or os.path.basename(file_path)

        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }

        media = MediaFileUpload(file_path, resumable=True)
        file_obj = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()

        if file_obj.get('error'):
            raise ValueError(f"Upload failed: {file_obj['error']}")

        return file_obj.get('id')

    def upload_bytes(self, file_bytes, folder_id, file_name, mime_type='application/octet-stream'):
        """
        Upload bytes to Google Drive.

        Args:
            file_bytes: Bytes to upload
            folder_id: Google Drive folder ID
            file_name: Name of file in Drive
            mime_type: MIME type

        Returns:
            File ID (string)
        """
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }

        media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mime_type, resumable=True)
        file_obj = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()

        if file_obj.get('error'):
            raise ValueError(f"Upload failed: {file_obj['error']}")

        return file_obj.get('id')

    def download_file(self, file_id, local_path):
        """
        Download file from Google Drive to local path.

        Args:
            file_id: Google Drive file ID
            local_path: Local destination path
        """
        try:
            request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
            with open(local_path, 'wb') as f:
                while True:
                    try:
                        status, done = request.next_chunk()
                        if done:
                            break
                    except Exception as e:
                        raise IOError(f"Failed to download file: {e}")
        except Exception as e:
            if os.path.exists(local_path):
                os.remove(local_path)
            raise

        return local_path

    def search_files(self, query, max_results=20):
        """Search Google Drive using a query string.

        Args:
            query: Drive API query string (e.g. "fullText contains 'agency'")
            max_results: Maximum number of results to return

        Returns:
            List of file dicts with id, name, mimeType, webViewLink, modifiedTime
        """
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType, webViewLink, modifiedTime, owners)',
            pageSize=max_results,
            orderBy='modifiedTime desc',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()

        if results.get('error'):
            raise ValueError(f"Search failed: {results['error']}")

        return results.get('files', [])

    def search_department_documents(self, dept_name, dept_domain):
        """Search Google Drive for documents matching department name or domain.

        Searches by two criteria:
        1. Department name in filename (fuzzy match >= 80% similarity)
        2. Document shared with any email from department domain

        Args:
            dept_name: Department name (e.g. "West Memphis Police")
            dept_domain: Department domain (e.g. "memphispd.gov")

        Returns:
            List of document dicts with keys: name, owner, last_modified, url
            Up to 20 documents per query, deduplicated by file ID
        """
        from fuzzywuzzy import fuzz

        results_by_id = {}

        try:
            # Query 1: Search by department name in filename
            try:
                query = f"fullText contains '{dept_name}' and trashed=false"
                files = self.search_files(query, max_results=20)
                for f in files:
                    file_id = f.get('id')
                    # Fuzzy match filename against department name
                    similarity = fuzz.token_set_ratio(f.get('name', '').lower(), dept_name.lower())
                    if similarity >= 80:
                        results_by_id[file_id] = f
            except Exception as e:
                print(f"Error searching by department name '{dept_name}': {e}")

            # Query 2: Search shared documents and filter by domain
            try:
                query = f"sharedWithMe and trashed=false"
                shared_files = self.search_files(query, max_results=20)
                for f in shared_files:
                    file_id = f.get('id')
                    # Check if document is shared with dept_domain
                    try:
                        perms = self.service.permissions().list(
                            fileId=file_id,
                            fields='permissions(emailAddress, type)',
                            supportsAllDrives=True
                        ).execute()
                        for perm in perms.get('permissions', []):
                            email = perm.get('emailAddress', '').lower()
                            if email.endswith(f'@{dept_domain.lower()}'):
                                results_by_id[file_id] = f
                                break
                    except Exception as e:
                        print(f"Error checking permissions for file {file_id}: {e}")
            except Exception as e:
                print(f"Error searching shared documents: {e}")

            # Format results
            formatted_results = []
            for file_id, f in results_by_id.items():
                owners = f.get('owners', [])
                owner = owners[0].get('displayName', 'Unknown') if owners else 'Unknown'
                formatted_results.append({
                    'name': f.get('name', ''),
                    'owner': owner,
                    'last_modified': f.get('modifiedTime', ''),
                    'url': f.get('webViewLink', '')
                })

            return formatted_results

        except Exception as e:
            print(f"Error in search_department_documents: {e}")
            return []

    def list_files(self, folder_id, file_type='all'):
        """
        List files in folder.

        Args:
            folder_id: Google Drive folder ID
            file_type: 'folders', 'images', or 'all'

        Returns:
            List of file dicts with id, name, mimeType
        """
        if file_type == 'folders':
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        elif file_type == 'images':
            query = f"'{folder_id}' in parents and (mimeType contains 'image/') and trashed=false"
        else:
            query = f"'{folder_id}' in parents and trashed=false"

        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name, mimeType, size)',
            pageSize=100,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True
        ).execute()

        if results.get('error'):
            raise ValueError(f"List failed: {results['error']}")

        return results.get('files', [])


def get_drive_manager():
    """Get authenticated Drive manager, preferring OAuth over service account.

    Returns GoogleDriveManager or None if neither auth method is available.
    """
    import google_oauth

    # Try OAuth credentials first
    oauth_creds = google_oauth.get_credentials()
    if oauth_creds:
        try:
            return GoogleDriveManager(oauth_creds)
        except Exception:
            pass

    # Fall back to service account from secrets
    try:
        credentials_json = st.secrets.get('GOOGLE_DRIVE_CREDENTIALS')
        if credentials_json:
            return GoogleDriveManager(credentials_json)
    except Exception:
        pass

    return None
