import pytest
import datetime
from unittest.mock import MagicMock, patch, PropertyMock

from src.infrastructure.gcs_service import GCSService
from src.core.settings import settings

# In order to properly test NotFound, we need to import it
from google.cloud.exceptions import NotFound

@pytest.fixture
def gcs_svc(mock_gcs_client):
    """
    Returns a fresh instance of GCSService for each test.
    This utilizes the mock_gcs_client fixture which ensures get_storage_client()
    returns our mock.
    """
    from src.infrastructure.gcs_client import get_storage_client
    get_storage_client.cache_clear()
    return GCSService()


# ==========================================
# Signed URL Generation
# ==========================================

def test_generate_signed_upload_url_happy_path(gcs_svc, mock_gcs_client, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 3600)
    mock_blob = MagicMock()
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    mock_blob.generate_signed_url.return_value = "https://mock-upload.com"
    
    mock_credentials = MagicMock()
    monkeypatch.setattr(gcs_svc, "_get_signing_credentials", MagicMock(return_value=mock_credentials))
    
    # Act
    url = gcs_svc.generate_signed_upload_url("upload/test.txt", "text/plain")
    
    # Assert
    assert url == "https://mock-upload.com"
    mock_gcs_client.bucket.return_value.blob.assert_called_once_with("upload/test.txt")
    mock_blob.generate_signed_url.assert_called_once_with(
        version="v4",
        expiration=datetime.timedelta(seconds=3600),
        method="PUT",
        content_type="text/plain",
        credentials=mock_credentials
    )

def test_generate_signed_download_url_happy_path(gcs_svc, mock_gcs_client, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 7200)
    mock_blob = MagicMock()
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    mock_blob.generate_signed_url.return_value = "https://mock-download.com"
    
    mock_credentials = MagicMock()
    monkeypatch.setattr(gcs_svc, "_get_signing_credentials", MagicMock(return_value=mock_credentials))
    
    # Act
    url = gcs_svc.generate_signed_download_url("download/report.pdf")
    
    # Assert
    assert url == "https://mock-download.com"
    mock_gcs_client.bucket.return_value.blob.assert_called_once_with("download/report.pdf")
    mock_blob.generate_signed_url.assert_called_once_with(
        version="v4",
        expiration=datetime.timedelta(seconds=7200),
        method="GET",
        response_disposition='attachment; filename="report.pdf"',
        response_type="application/octet-stream",
        credentials=mock_credentials
    )

# ==========================================
# Object Management
# ==========================================

def test_delete_object_happy_path(gcs_svc, mock_gcs_client):
    # Arrange
    mock_blob = MagicMock()
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    
    # Act
    gcs_svc.delete_object("delete/me.png")
    
    # Assert
    mock_gcs_client.bucket.return_value.blob.assert_called_once_with("delete/me.png")
    mock_blob.delete.assert_called_once()

def test_delete_object_negative_path_silent_fail(gcs_svc, mock_gcs_client):
    # Arrange
    mock_blob = MagicMock()
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    # Simulating object already deleted or missing
    mock_blob.delete.side_effect = Exception("Object not found")
    
    # Act - Should not raise an exception
    gcs_svc.delete_object("already/deleted.png")
    
    # Assert
    mock_blob.delete.assert_called_once()

def test_get_object_metadata_happy_path(gcs_svc, mock_gcs_client):
    # Arrange
    mock_blob = MagicMock()
    mock_blob.size = 1024
    mock_blob.content_type = "image/jpeg"
    mock_blob.md5_hash = "fake-md5-hash"
    mock_blob.updated = "2026-05-15T00:00:00Z"
    
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    
    # Act
    metadata = gcs_svc.get_object_metadata("path/image.jpg")
    
    # Assert
    mock_blob.reload.assert_called_once()
    assert metadata == {
        "size": 1024,
        "content_type": "image/jpeg",
        "md5_hash": "fake-md5-hash",
        "updated": "2026-05-15T00:00:00Z",
    }

def test_get_object_metadata_negative_path_not_found(gcs_svc, mock_gcs_client):
    # Arrange
    mock_blob = MagicMock()
    mock_blob.reload.side_effect = NotFound("Blob missing")
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    
    # Act
    metadata = gcs_svc.get_object_metadata("missing/image.jpg")
    
    # Assert
    mock_blob.reload.assert_called_once()
    assert metadata is None


# ==========================================
# Helpers & Edge Cases
# ==========================================

def test_get_model_file_uri_edge_case_google(gcs_svc, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_BUCKET_NAME", "my-app-bucket")
    
    # Act
    # Test permutations of "google" (case-insensitive/whitespace)
    uri1 = gcs_svc._get_model_file_uri("file1.pdf", "Google")
    uri2 = gcs_svc._get_model_file_uri("file2.pdf", " google ")
    
    # Assert
    assert uri1 == "gs://my-app-bucket/file1.pdf"
    assert uri2 == "gs://my-app-bucket/file2.pdf"

def test_get_model_file_uri_edge_case_other(gcs_svc, monkeypatch):
    # Arrange
    mock_signed_url = "https://signed.com/download"
    monkeypatch.setattr(gcs_svc, "generate_signed_download_url", MagicMock(return_value=mock_signed_url))
    
    # Act
    uri = gcs_svc._get_model_file_uri("file.pdf", "openai")
    
    # Assert
    assert uri == mock_signed_url
    gcs_svc.generate_signed_download_url.assert_called_once_with("file.pdf")

def test_get_signing_credentials_happy_path(gcs_svc, monkeypatch):
    """
    Test _get_signing_credentials parses actual settings and uses from_service_account_info
    """
    # Act
    creds = gcs_svc._get_signing_credentials()
    
    # Assert
    from src.infrastructure.gcs_service import service_account
    
    expected_info = settings.get_gcs_credentials.copy()
    if "private_key" in expected_info and expected_info["private_key"]:
        expected_info["private_key"] = expected_info["private_key"].replace("\\n", "\n")
        
    # We intentionally do not use assert_called_with to avoid dumping the private key into the pytest logs if it fails
    # Instead, we assert the credentials object was successfully created by Google and has the correct project id
    assert isinstance(creds, service_account.Credentials)
    assert creds.project_id == expected_info.get("project_id")

def test_get_signing_credentials_negative_path_empty(gcs_svc, monkeypatch):
    # Arrange
    monkeypatch.setattr(type(settings), "get_gcs_credentials", PropertyMock(return_value={}))
    
    # Act
    creds = gcs_svc._get_signing_credentials()
    
    # Assert
    assert creds is None

def test_get_gcs_storage_path(gcs_svc):
    # Arrange
    file_id = "uuid-1234"
    
    # Act
    path = gcs_svc.get_gcs_storage_path(file_id=file_id)
    
    # Assert
    assert path == "api/public/upload/uuid-1234"

def test_download_object_as_bytes_happy_path(gcs_svc, mock_gcs_client):
    # Arrange
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = b"test content bytes"
    mock_gcs_client.bucket.return_value.blob.return_value = mock_blob
    
    # Act
    content = gcs_svc.download_object_as_bytes("path/to/object")
    
    # Assert
    assert content == b"test content bytes"
    mock_gcs_client.bucket.return_value.blob.assert_called_once_with("path/to/object")
    mock_blob.download_as_bytes.assert_called_once()
