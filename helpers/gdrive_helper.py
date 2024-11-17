import os
import uuid
import dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

class GDriveHelper:
    def __init__(self):
        service_account_file = os.getenv("GOOGLE_SERVICE_ACCOUNT")
        SCOPES = ['https://www.googleapis.com/auth/drive']
        credentials = service_account.Credentials.from_service_account_file(service_account_file, scopes=SCOPES)
        self.main_folder_id = os.getenv("GDRIVE_FOLDER_ID")
        self.drive_service = build('drive', 'v3', credentials=credentials)

    def get_files(self, folder_id: str = None):
        folder_id = folder_id or self.main_folder_id
        results = self.drive_service.files().list(
            #q=f"'{folder_id}' in parents and trashed=false",
            q="trashed = false",
            fields="files(id, name, mimeType, webViewLink, parents)"
        ).execute()
        return results.get('files', [])
    
    def download_file(self, file_id: str, destination: str):
        file_name = str(uuid.uuid4())
        request = self.drive_service.files().get_media(fileId=file_id)
        os.makedirs(destination, exist_ok=True)
        with open(destination + "/" + file_name, 'wb') as file:
            downloader = MediaIoBaseDownload(file, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%.")
        return file_name
    
    def file_in_drive(self, file_name):
        files = self.get_files()
        for file in files:
            if file['name'] == file_name:
                return True
        return False

if __name__ == "__main__":
    dotenv.load_dotenv()
    gdrive = GDriveHelper()
    for file in gdrive.get_files():
        print(file)
        print("------------------")
    print(gdrive.file_in_drive("gacha.json"))
    print(gdrive.file_in_drive("Melware.zip"))
    #gdrive.download_file("1wKw7J0yUgqJ1k2bJbRd8fJ6q8tJ6q8t", "Melbot/data")