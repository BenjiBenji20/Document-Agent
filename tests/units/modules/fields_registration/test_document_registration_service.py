import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request, status
from src.modules.fields_registration.document_registration_service import DocumentRegistration
from src.modules.fields_registration.schema import DocumentRegistrationRequest, DocumentFields

@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"
    return request

@pytest.fixture
def valid_documents():
    return [
        DocumentRegistrationRequest(
            document_name="Test Document",
            fields=[DocumentFields(field="test_field", is_required=True)]
        )
    ]

@pytest.mark.asyncio
async def test_save_document_metadata_happy_path(mock_redis, mock_request, valid_documents):
    # Arrange
    service = DocumentRegistration(mock_redis, request=mock_request)
    mock_redis.set_hash_many.return_value = True

    # Act
    responses = await service.save_document_metadata(documents=valid_documents)

    # Assert
    assert mock_redis.set_hash_many.called
    assert len(responses) == 1
    response = responses[0]
    
    assert response.details.successful is True
    assert response.details.success_count == 1
    assert response.details.failure_count == 0
    assert response.document_metadata.document_name == "Test Document"
    assert len(response.document_metadata.fields) == 1

@pytest.mark.asyncio
async def test_save_document_metadata_negative_path_redis_failure(mock_redis, mock_request, valid_documents):
    # Arrange: Redis fails to set
    service = DocumentRegistration(mock_redis, request=mock_request)
    mock_redis.set_hash_many.return_value = False

    # Act
    responses = await service.save_document_metadata(documents=valid_documents)

    # Assert
    assert mock_redis.set_hash_many.called
    assert len(responses) == 1
    response = responses[0]
    
    assert response.details.successful is False
    assert response.details.success_count == 0
    assert response.details.failure_count == 1
    assert "failed" in response.details.description.lower()

@pytest.mark.asyncio
async def test_save_document_metadata_negative_path_exception(mock_redis, mock_request, valid_documents):
    # Arrange: Redis throws an exception
    service = DocumentRegistration(mock_redis, request=mock_request)
    mock_redis.set_hash_many.side_effect = Exception("Redis connection error")

    # Act & Assert
    with pytest.raises(HTTPException) as exc_info:
        await service.save_document_metadata(documents=valid_documents)
        
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert exc_info.value.detail == "Failed to save document metadata."
