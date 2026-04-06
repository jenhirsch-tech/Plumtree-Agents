"""Google Drive integration — upload files and copy templates."""

import io
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

from config.settings import Settings
from integrations.google_auth import get_credentials


class GoogleDriveClient:
    """Upload files to Drive and copy templates."""

    def __init__(self, settings: Settings):
        creds = get_credentials(settings)
        self.service = build("drive", "v3", credentials=creds)

    def upload_file(
        self,
        file_path: str,
        folder_id: str,
        mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) -> dict:
        """Upload a local file to a specific Drive folder. Returns file metadata."""
        name = Path(file_path).name
        file_metadata = {"name": name, "parents": [folder_id]}
        media = MediaFileUpload(file_path, mimetype=mime_type)
        file = self.service.files().create(
            body=file_metadata, media_body=media, fields="id, name, webViewLink"
        ).execute()
        return file

    def upload_bytes(
        self,
        content: bytes,
        filename: str,
        folder_id: str,
        mime_type: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ) -> dict:
        """Upload in-memory bytes to Drive. Returns file metadata."""
        file_metadata = {"name": filename, "parents": [folder_id]}
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type)
        file = self.service.files().create(
            body=file_metadata, media_body=media, fields="id, name, webViewLink"
        ).execute()
        return file

    def copy_file(self, source_file_id: str, new_name: str, folder_id: str) -> dict:
        """Copy a file (template) into a target folder with a new name."""
        body = {"name": new_name, "parents": [folder_id]}
        copy = self.service.files().copy(
            fileId=source_file_id, body=body, fields="id, name, webViewLink"
        ).execute()
        return copy

    def get_web_link(self, file_id: str) -> str:
        """Get the web view link for a file."""
        file = self.service.files().get(fileId=file_id, fields="webViewLink").execute()
        return file.get("webViewLink", "")
