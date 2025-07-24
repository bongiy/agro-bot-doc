import os
import mimetypes
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
SERVICE_ACCOUNT_FILE = "credentials.json"  # після кроку з ENV цей файл буде існувати!
PARENT_FOLDER_ID = os.getenv("GOOGLE_DRIVE_PARENT")  # ID папки у Google Drive, яку ти шариш із service account

def get_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds)

def upload_pdf_to_drive(local_path, name, parent_folder=PARENT_FOLDER_ID):
    service = get_service()
    file_metadata = {"name": name, "parents": [parent_folder]}
    mime_type = mimetypes.guess_type(local_path)[0] or "application/pdf"
    media = MediaFileUpload(local_path, mimetype=mime_type)
    uploaded = service.files().create(
        body=file_metadata, media_body=media, fields="id,webViewLink"
    ).execute()
    return uploaded.get("id"), uploaded.get("webViewLink")
