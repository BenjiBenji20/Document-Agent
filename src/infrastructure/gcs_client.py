from functools import lru_cache

from google.cloud import storage
from google.oauth2 import service_account
from src.core.settings import settings


@lru_cache(maxsize=1)
def get_storage_client() -> storage.Client:
    """
    Returns a singleton GCP Storage client.
    """
    if settings.get_gcs_credentials:
        info: dict[str] = settings.get_gcs_credentials
        
        # escaped newlines in private_key
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        return storage.Client(credentials=credentials, project=info.get("project_id"))

    return storage.Client()


def get_bucket(client: storage.Client | None = None) -> storage.Bucket:
    if not settings.GCS_BUCKET_NAME:
        raise RuntimeError("GCS bucket name environment variable is not set.")
    
    c = client or get_storage_client()
    return c.bucket(settings.GCS_BUCKET_NAME)
