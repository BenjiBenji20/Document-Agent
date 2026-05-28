import datetime
from typing import Optional

from src.core.settings import settings
from google.oauth2 import service_account
from google.cloud import storage

import logging

from src.infrastructure.gcs_client import get_bucket, get_storage_client

logger = logging.getLogger(__name__)

class GCSService:
    def __init__(self) -> None:
        self._client: storage.Client = get_storage_client()
        self._bucket: storage.Bucket = get_bucket(self._client)
        
    def generate_signed_upload_url(
        self,
        object_key: str,
        content_type: str,
    ) -> str:
        """
        Generates a V4 signed URL for a direct PUT upload from the client.

        The signed URL is scoped to:
          - a specific object key
          - a specific content-type
          - a max Content-Length via condition
        """
        blob = self._bucket.blob(object_key)

        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=settings.GCS_SIGNED_URL_EXPIRATION),
            method="PUT",
            content_type=content_type,
            credentials=self._get_signing_credentials()
        )
        return url
    
    
    def generate_signed_download_url(self, object_key: str) -> str:
        """
        Generates a V4 signed URL for a GET download.
        """
        blob = self._bucket.blob(object_key)
        file_name = object_key.split("/")[-1]
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(seconds=settings.GCS_SIGNED_URL_EXPIRATION),
            method="GET",
            response_disposition=f'attachment; filename="{file_name}"',
            response_type="application/octet-stream",
            credentials=self._get_signing_credentials()
        )
        return url
    
    
    def delete_object(self, object_key: str) -> None:
        """
        Deletes an object from GCS. Silent if already missing.
        """
        blob = self._bucket.blob(object_key)
        try:
            blob.delete()
        except Exception:
            # Object may already be gone (e.g. lifecycle-deleted). That's fine.
            pass
        
    
    def get_object_metadata(self, object_key: str) -> Optional[dict]:
        """
        Returns size, content_type, md5_hash of an object.
        Returns None if the object doesn't exist.
        """
        from google.cloud.exceptions import NotFound
        blob = self._bucket.blob(object_key)
        try:
            blob.reload()
        except NotFound:
            return None
        return {
            "size": blob.size,
            "content_type": blob.content_type,
            "md5_hash": blob.md5_hash,
            "updated": blob.updated,
        }
    
    
    def _get_model_file_uri(self, object_key: str, model_provider: str) -> str:
        """
        Model directly reads the file using public URI
        Returns the correct file reference depending on the model provider.
        """
        model_provider = model_provider.strip().lower()
        if model_provider == "gemini":
            return f"gs://{settings.GCS_BUCKET_NAME}/{object_key}"
        else:
            return self.generate_signed_download_url(object_key)
            
    
    def _get_signing_credentials(self):
        """
        Signed URL generation requires explicit credentials even on Cloud Run.
        Reads from JSON info in settings.
        """
        credentials = settings.get_gcs_credentials.copy()
        if credentials:
            if "private_key" in credentials and credentials["private_key"]:
                credentials["private_key"] = credentials["private_key"].replace("\\n", "\n")
                
            return service_account.Credentials.from_service_account_info(
                credentials,
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
        return None
    
    
    def get_gcs_storage_path(self, file_id: str) -> str:
        return f"api/public/upload/{file_id}"
        

gcs_service = GCSService()
