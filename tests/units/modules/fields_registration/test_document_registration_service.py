import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException, Request, status
from src.modules.fields_registration.document_registration_service import DocumentRegistration
from src.modules.fields_registration.document_registration_schema import DocumentRegistrationRequest, DocumentFields

@pytest.fixture
def mock_request():
    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"
    return request

@pytest.fixture
def valid_documents():
    from uuid import uuid4
    return [
        DocumentRegistrationRequest(
            id=uuid4(),
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


@pytest.mark.asyncio
async def test_call_agent_to_extract_schema_happy_path(mock_redis, mock_request, mock_base_agent, monkeypatch):
    from src.modules.gcs_operations.direct_gcs_operations_schema import GCSFileObjectMetadata
    
    # Mock GCS Service
    mock_gcs = MagicMock()
    mock_gcs.get_gcs_storage_path.return_value = "api/public/upload/test-123"
    mock_gcs._get_model_file_uri.return_value = "gs://bucket/test-123"
    mock_gcs.get_object_metadata.return_value = {"size": 100, "content_type": "image/png"}
    monkeypatch.setattr("src.modules.fields_registration.document_registration_service.gcs_service", mock_gcs)
    
    service = DocumentRegistration(mock_redis, request=mock_request)
    files = [
        GCSFileObjectMetadata(id="test-123", file_name="doc.png", file_type="image/png", file_size=100)
    ]
    
    events = []
    async for event in service.call_agent_to_extract_schema(files):
        events.append(event)
        
    assert len(events) > 0
    # Ensure standard SSE format is met
    assert any("Counting documents..." in e for e in events)
    assert any("event: result" in e for e in events)
    assert any("event: complete" in e for e in events)


@pytest.mark.asyncio
async def test_call_agent_to_extract_schema_empty_input(mock_redis, mock_request, mock_base_agent):
    service = DocumentRegistration(mock_redis, request=mock_request)
    
    events = []
    async for event in service.call_agent_to_extract_schema([]):
        events.append(event)
        
    assert len(events) == 2
    assert any("Counting documents..." in e for e in events)
    assert any("event: error" in e for e in events)
    assert any("No files uploaded" in e for e in events)


@pytest.mark.asyncio
async def test_call_agent_to_extract_schema_exception_handling(mock_redis, mock_request, mock_base_agent, monkeypatch):
    from src.modules.gcs_operations.direct_gcs_operations_schema import GCSFileObjectMetadata
    
    # Mock GCS Service to raise exception
    mock_gcs = MagicMock()
    mock_gcs.get_gcs_storage_path.side_effect = Exception("Storage error")
    monkeypatch.setattr("src.modules.fields_registration.document_registration_service.gcs_service", mock_gcs)
    
    service = DocumentRegistration(mock_redis, request=mock_request)
    files = [
        GCSFileObjectMetadata(id="test-123", file_name="doc.png", file_type="image/png", file_size=100)
    ]
    
    events = []
    async for event in service.call_agent_to_extract_schema(files):
        events.append(event)
        
    assert any("event: error" in e for e in events)
    assert any("Storage error" in e for e in events)


@pytest.mark.asyncio
async def test_save_document_metadata_is_schema_extracted_false(mock_redis, mock_request):
    from uuid import UUID
    # Arrange: Document has id=None (e.g. from manual user registration request)
    doc_no_id = [
        DocumentRegistrationRequest(
            document_name="Manual Register",
            fields=[DocumentFields(field="test_field", is_required=True)]
        )
    ]
    service = DocumentRegistration(mock_redis, request=mock_request)
    mock_redis.set_hash_many.return_value = True

    # Act: call with is_schema_extracted=False
    responses = await service.save_document_metadata(documents=doc_no_id, is_schema_extracted=False)

    # Assert: verify a new UUID was generated
    assert len(responses) == 1
    response = responses[0]
    assert response.document_metadata.id is not None
    assert isinstance(response.document_metadata.id, UUID)


@pytest.mark.asyncio
async def test_save_document_metadata_is_schema_extracted_true_missing_id(mock_redis, mock_request):
    # Arrange: Document has id=None (e.g. from manual user registration request)
    doc_no_id = [
        DocumentRegistrationRequest(
            document_name="Manual Register",
            fields=[DocumentFields(field="test_field", is_required=True)]
        )
    ]
    service = DocumentRegistration(mock_redis, request=mock_request)

    # Act & Assert: should raise 400 HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await service.save_document_metadata(documents=doc_no_id, is_schema_extracted=True)

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "Document ID is required" in exc_info.value.detail
