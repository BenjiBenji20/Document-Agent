import asyncio
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException, status

from src.core.settings import settings
from src.infrastructure.gcs_service import GCSService
from src.infrastructure.gcs_client import get_storage_client
import src.modules.gcs_operations.direct_gcs_operations_service as service_module
from src.modules.gcs_operations.direct_gcs_operations_service import DirectGCSOperationsService
from src.modules.gcs_operations.direct_gcs_operations_schema import GCSUploadFileMetadata
from src.shared.file_metadata import MAX_FILE_SIZE


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


# =====================================================================
# bulk_generate_gcs_upload_urls Tests
# =====================================================================

@pytest.mark.asyncio
async def test_bulk_generate_gcs_upload_urls_happy_single(patch_gcs_service, mock_gcs_client, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 3600)
    
    mock_upload_url = "https://gcs-upload.com/file-1"
    mock_generate = MagicMock(return_value=mock_upload_url)
    monkeypatch.setattr(patch_gcs_service, "generate_signed_upload_url", mock_generate)
    
    service = DirectGCSOperationsService()
    
    files = [
        GCSUploadFileMetadata(file_name="test.pdf", file_type="application/pdf", file_size=1024)
    ]
    
    # Act
    results = await service.bulk_generate_gcs_upload_urls(files)
    
    # Assert
    assert len(results) == 1
    res = results[0]
    assert res.upload_url == mock_upload_url
    assert res.expires_in_seconds == 3600
    assert res.storage_path == f"api/public/upload/{res.id}"
    mock_generate.assert_called_once_with(res.storage_path, "application/pdf")


@pytest.mark.asyncio
async def test_bulk_generate_gcs_upload_urls_happy_multiple(patch_gcs_service, mock_gcs_client, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 7200)
    
    urls = [
        "https://gcs-upload.com/f1",
        "https://gcs-upload.com/f2",
        "https://gcs-upload.com/f3"
    ]
    mock_generate = MagicMock(side_effect=urls)
    monkeypatch.setattr(patch_gcs_service, "generate_signed_upload_url", mock_generate)
    
    service = DirectGCSOperationsService()
    
    files = [
        GCSUploadFileMetadata(file_name="a.pdf", file_type="application/pdf", file_size=100),
        GCSUploadFileMetadata(file_name="b.png", file_type="image/png", file_size=200),
        GCSUploadFileMetadata(file_name="c.jpg", file_type="image/jpg", file_size=300),
    ]
    
    # Act
    results = await service.bulk_generate_gcs_upload_urls(files)
    
    # Assert
    assert len(results) == 3
    for i, res in enumerate(results):
        assert res.upload_url == urls[i]
        assert res.expires_in_seconds == 7200
        assert res.storage_path == f"api/public/upload/{res.id}"
    
    assert mock_generate.call_count == 3
    calls = mock_generate.call_args_list
    assert calls[0][0] == (results[0].storage_path, "application/pdf")
    assert calls[1][0] == (results[1].storage_path, "image/png")
    assert calls[2][0] == (results[2].storage_path, "image/jpg")


@pytest.mark.asyncio
async def test_bulk_generate_gcs_upload_urls_negative_empty_list(patch_gcs_service):
    # Arrange
    service = DirectGCSOperationsService()
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await service.bulk_generate_gcs_upload_urls([])
        
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "No files found..."


@pytest.mark.asyncio
async def test_bulk_generate_gcs_upload_urls_negative_gcs_exception(patch_gcs_service, monkeypatch):
    # Arrange
    mock_generate = MagicMock(side_effect=Exception("Connection timed out to GCS"))
    monkeypatch.setattr(patch_gcs_service, "generate_signed_upload_url", mock_generate)
    
    service = DirectGCSOperationsService()
    files = [
        GCSUploadFileMetadata(file_name="test.pdf", file_type="application/pdf", file_size=1024)
    ]
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await service.bulk_generate_gcs_upload_urls(files)
        
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Server error while uploading file."


@pytest.mark.asyncio
async def test_bulk_generate_gcs_upload_urls_edge_min_capabilities(patch_gcs_service, monkeypatch):
    # Arrange
    # Min boundaries: name len 1, size 1, expiration setting 1 sec
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 1)
    
    mock_upload_url = "https://gcs-upload.com/min"
    mock_generate = MagicMock(return_value=mock_upload_url)
    monkeypatch.setattr(patch_gcs_service, "generate_signed_upload_url", mock_generate)
    
    service = DirectGCSOperationsService()
    files = [
        GCSUploadFileMetadata(file_name="a", file_type="application/pdf", file_size=1)
    ]
    
    # Act
    results = await service.bulk_generate_gcs_upload_urls(files)
    
    # Assert
    assert len(results) == 1
    assert results[0].expires_in_seconds == 1
    assert results[0].upload_url == mock_upload_url


@pytest.mark.asyncio
async def test_bulk_generate_gcs_upload_urls_edge_max_capabilities(patch_gcs_service, monkeypatch):
    # Arrange
    # Max boundaries: name len 255, size MAX_FILE_SIZE, expiration setting 86400 secs
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 86400)
    
    mock_upload_url = "https://gcs-upload.com/max"
    mock_generate = MagicMock(return_value=mock_upload_url)
    monkeypatch.setattr(patch_gcs_service, "generate_signed_upload_url", mock_generate)
    
    service = DirectGCSOperationsService()
    files = [
        GCSUploadFileMetadata(file_name="x" * 255, file_type="image/png", file_size=MAX_FILE_SIZE)
    ]
    
    # Act
    results = await service.bulk_generate_gcs_upload_urls(files)
    
    # Assert
    assert len(results) == 1
    assert results[0].expires_in_seconds == 86400
    assert results[0].upload_url == mock_upload_url


@pytest.mark.asyncio
async def test_bulk_generate_gcs_upload_urls_edge_large_batch(patch_gcs_service, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 3600)
    
    mock_upload_url = "https://gcs-upload.com/batch"
    mock_generate = MagicMock(return_value=mock_upload_url)
    monkeypatch.setattr(patch_gcs_service, "generate_signed_upload_url", mock_generate)
    
    service = DirectGCSOperationsService()
    
    # Batch of 50 files
    files = [
        GCSUploadFileMetadata(file_name=f"file_{i}.pdf", file_type="application/pdf", file_size=100)
        for i in range(50)
    ]
    
    # Act
    results = await service.bulk_generate_gcs_upload_urls(files)
    
    # Assert
    assert len(results) == 50
    assert mock_generate.call_count == 50
    for res in results:
        assert res.upload_url == mock_upload_url
        assert res.expires_in_seconds == 3600


# =====================================================================
# generate_gcs_download_url Tests
# =====================================================================

@pytest.mark.asyncio
async def test_generate_gcs_download_url_happy(patch_gcs_service, monkeypatch):
    # Arrange
    monkeypatch.setattr(settings, "GCS_SIGNED_URL_EXPIRATION", 3600)
    file_id = "test-file-uuid"
    expected_path = f"api/public/upload/{file_id}"
    mock_download_url = "https://gcs-download.com/test-file-uuid"
    
    mock_generate = MagicMock(return_value=mock_download_url)
    monkeypatch.setattr(patch_gcs_service, "generate_signed_download_url", mock_generate)
    
    service = DirectGCSOperationsService()
    
    # Act
    res = await service.generate_gcs_download_url(file_id)
    
    # Assert
    assert res.id == file_id
    assert res.storage_path == expected_path
    assert res.expires_in_seconds == 3600
    mock_generate.assert_called_once_with(expected_path)


@pytest.mark.asyncio
async def test_generate_gcs_download_url_negative_empty_url(patch_gcs_service, monkeypatch):
    # Arrange
    file_id = "missing-file-id"
    mock_generate = MagicMock(return_value="")
    monkeypatch.setattr(patch_gcs_service, "generate_signed_download_url", mock_generate)
    
    service = DirectGCSOperationsService()
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await service.generate_gcs_download_url(file_id)
        
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert "No files to download found using this GCS storage path" in exc_info.value.detail


@pytest.mark.asyncio
async def test_generate_gcs_download_url_negative_gcs_exception(patch_gcs_service, monkeypatch):
    # Arrange
    file_id = "error-file-id"
    mock_generate = MagicMock(side_effect=Exception("GCS authentication failed"))
    monkeypatch.setattr(patch_gcs_service, "generate_signed_download_url", mock_generate)
    
    service = DirectGCSOperationsService()
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await service.generate_gcs_download_url(file_id)
        
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Server error while uploading file."


@pytest.mark.asyncio
async def test_generate_gcs_download_url_edge_cases(patch_gcs_service, monkeypatch):
    # Arrange
    # Edge case: Empty ID
    file_id_min = ""
    mock_generate = MagicMock(return_value="https://gcs-download.com/empty")
    monkeypatch.setattr(patch_gcs_service, "generate_signed_download_url", mock_generate)
    
    service = DirectGCSOperationsService()
    
    # Act
    res_min = await service.generate_gcs_download_url(file_id_min)
    
    # Assert
    assert res_min.id == ""
    assert res_min.storage_path == "api/public/upload/"
    mock_generate.assert_called_with("api/public/upload/")
    
    # Edge case: Max allowed ID length (510 - 18 prefix = 492 characters)
    file_id_max = "x" * 492
    res_max = await service.generate_gcs_download_url(file_id_max)
    assert res_max.id == file_id_max
    assert res_max.storage_path == f"api/public/upload/{file_id_max}"
    mock_generate.assert_called_with(f"api/public/upload/{file_id_max}")
