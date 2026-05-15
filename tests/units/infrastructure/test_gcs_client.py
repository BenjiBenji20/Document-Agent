import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from src.infrastructure.gcs_client import get_storage_client, get_bucket, service_account, storage
from src.core.settings import settings

# Clear the lru_cache before each test to ensure isolation
@pytest.fixture(autouse=True)
def clear_cache():
    get_storage_client.cache_clear()
    yield
    get_storage_client.cache_clear()


# ==========================================
# get_storage_client() Tests
# ==========================================

def test_get_storage_client_happy_path(mock_gcs_client):
    """
    Test that get_storage_client correctly initializes credentials using 
    the actual settings values and properly handles private key newlines.
    """
    # Act
    client = get_storage_client()
    
    # Assert
    assert client == mock_gcs_client
    
    # Construct expected arguments directly from actual settings
    expected_info = settings.get_gcs_credentials.copy()
    if "private_key" in expected_info and expected_info["private_key"]:
        expected_info["private_key"] = expected_info["private_key"].replace("\\n", "\n")
        
    service_account.Credentials.from_service_account_info.assert_called_once_with(
        expected_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    
    storage.Client.assert_called_once_with(
        credentials=service_account.Credentials.from_service_account_info.return_value,
        project=expected_info.get("project_id")
    )


def test_get_storage_client_negative_path_empty_credentials(mock_gcs_client, monkeypatch):
    """
    Test fallback to default client when credentials are empty/not provided.
    """
    # Arrange: Mock the property to return an empty dict
    monkeypatch.setattr(type(settings), "get_gcs_credentials", PropertyMock(return_value={}))
    
    # Act
    client = get_storage_client()
    
    # Assert
    assert client == mock_gcs_client
    service_account.Credentials.from_service_account_info.assert_not_called()
    storage.Client.assert_called_once_with()


def test_get_storage_client_edge_case_caching(mock_gcs_client):
    """
    Test that the @lru_cache works correctly (client is only initialized once 
    and the same instance is returned on subsequent calls).
    """
    # Act
    client1 = get_storage_client()
    client2 = get_storage_client()
    
    # Assert
    assert client1 is client2
    assert client1 == mock_gcs_client
    
    # Should only be called ONCE due to caching
    storage.Client.assert_called_once()
    service_account.Credentials.from_service_account_info.assert_called_once()


# ==========================================
# get_bucket() Tests
# ==========================================

def test_get_bucket_happy_path(mock_gcs_client, monkeypatch):
    """
    Test getting a bucket with a valid GCS_BUCKET_NAME.
    """
    # Arrange
    monkeypatch.setattr(settings, "GCS_BUCKET_NAME", "my-test-bucket")
    
    # Act
    bucket = get_bucket()
    
    # Assert
    assert bucket == mock_gcs_client.bucket.return_value
    mock_gcs_client.bucket.assert_called_once_with("my-test-bucket")


def test_get_bucket_negative_path_no_bucket_name(monkeypatch):
    """
    Test that get_bucket raises RuntimeError if GCS_BUCKET_NAME is missing or None.
    """
    # Arrange
    monkeypatch.setattr(settings, "GCS_BUCKET_NAME", None)
    
    # Act & Assert
    with pytest.raises(RuntimeError, match="GCS bucket name environment variable is not set."):
        get_bucket()


def test_get_bucket_edge_case_explicit_client(mock_gcs_client, monkeypatch):
    """
    Test getting a bucket by passing an explicit custom client, 
    bypassing the default get_storage_client.
    """
    # Arrange
    monkeypatch.setattr(settings, "GCS_BUCKET_NAME", "explicit-bucket")
    custom_mock_client = MagicMock()
    
    # Act
    bucket = get_bucket(client=custom_mock_client)
    
    # Assert
    assert bucket == custom_mock_client.bucket.return_value
    custom_mock_client.bucket.assert_called_once_with("explicit-bucket")
    
    # The default mock client should NOT have been used
    mock_gcs_client.bucket.assert_not_called()
