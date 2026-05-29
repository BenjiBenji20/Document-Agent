import pytest
from unittest.mock import MagicMock
from fastapi import status

from src.core.settings import settings
from src.infrastructure.gcs_service import GCSService
from src.infrastructure.gcs_client import get_storage_client
import src.modules.gcs_operations.direct_gcs_operations_service as service_module

# Helper to bypass the secret check for routing logic testing
def override_document_agent_secret():
    pass

def override_rate_limit_by_ip():
    pass

@pytest.fixture(autouse=True)
def override_dependencies():
    from src.main import app
    from src.dependencies.secrets import document_agent_secret
    from src.dependencies.rate_limit import rate_limit_by_ip
    
    app.dependency_overrides[document_agent_secret] = override_document_agent_secret
    app.dependency_overrides[rate_limit_by_ip] = override_rate_limit_by_ip
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def patch_gcs_service(mock_gcs_client, monkeypatch):
    """
    Fixture that clears the GCS client singleton cache, instantiates GCSService under
    the active mock_gcs_client mock, and monkeypatches the module-level gcs_service.
    """
    get_storage_client.cache_clear()
    mocked_svc = GCSService()
    monkeypatch.setattr(service_module, "gcs_service", mocked_svc)
    return mocked_svc


def test_gcs_operations_router_happy_path(client, patch_gcs_service, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 3600)
    mock_upload_url = "https://gcs-upload.com/integration-test-url"
    
    mock_generate = MagicMock(return_value=mock_upload_url)
    monkeypatch.setattr(patch_gcs_service, "generate_signed_upload_url", mock_generate)

    payload = [
        {
            "file_name": "receipt.pdf",
            "file_type": "application/pdf",
            "file_size": 2048
        }
    ]

    # Act
    response = client.post("/api/public/gcs/generate-upload-urls", json=payload)

    # Assert
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 1
    
    res_url = data[0]
    assert res_url["upload_url"] == mock_upload_url
    assert res_url["expires_in_seconds"] == 3600
    assert "id" in res_url
    assert res_url["storage_path"] == f"api/public/upload/{res_url['id']}"


def test_gcs_operations_router_negative_empty_list(client, patch_gcs_service):
    # Act - Empty list of files
    response = client.post("/api/public/gcs/generate-upload-urls", json=[])

    # Assert
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert data["detail"] == "No files found..."


def test_gcs_operations_router_negative_validation_error(client):
    # Arrange
    # Missing required 'file_size' and unsupported 'file_type'
    payload = [
        {
            "file_name": "unsupported.exe",
            "file_type": "application/x-msdownload"
        }
    ]

    # Act
    response = client.post("/api/public/gcs/generate-upload-urls", json=payload)

    # Assert
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    data = response.json()
    assert "detail" in data
    # Checking validation errors
    errors = data["detail"]
    assert any(err["loc"] == ["body", 0, "file_size"] for err in errors)
    assert any("Unsupported file type" in err["msg"] for err in errors)


def test_gcs_operations_router_gcs_exception(client, patch_gcs_service, monkeypatch):
    # Arrange
    monkeypatch.setattr(
        patch_gcs_service,
        "generate_signed_upload_url",
        MagicMock(side_effect=Exception("Failed to talk to GCS"))
    )

    payload = [
        {
            "file_name": "photo.png",
            "file_type": "image/png",
            "file_size": 4096
        }
    ]

    # Act
    response = client.post("/api/public/gcs/generate-upload-urls", json=payload)

    # Assert
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = response.json()
    assert data["detail"] == "Server error while uploading file."
