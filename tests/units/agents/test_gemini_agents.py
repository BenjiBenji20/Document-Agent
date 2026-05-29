import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.gemini_agents import GeminiAgents
from src.agents.schemas.agent_extract_schemas import ExtractionStatus
from google.genai import types

@pytest.mark.asyncio
async def test_gemini_agents_extract_single_document_schema_happy_path(mock_gemini_client, monkeypatch):
    # Arrange
    agent = GeminiAgents()
    metadata = {
        "id": "file-123",
        "file_name": "my_national_id.png",
        "file_type": "image/png"
    }
    
    # Mock GCS Service to return dummy bytes
    mock_gcs = MagicMock()
    mock_gcs.get_gcs_storage_path.return_value = "api/public/upload/file-123"
    mock_gcs.download_object_as_bytes.return_value = b"mock png content"
    monkeypatch.setattr("src.infrastructure.gcs_service.gcs_service", mock_gcs)
    
    # Setup mock response from generate_content
    mock_response = MagicMock()
    mock_response.text = (
        '{"document_name": "National ID", "file_name": "my_national_id.png", "confidence_score": 0.98, '
        '"fields": [{"field": "first_name", "is_required": true, "bounding_box": {"ymin": 100, "xmin": 100, "ymax": 150, "xmax": 200}}]}'
    )
    mock_gemini_client.aio.models.generate_content.return_value = mock_response
    
    # Act
    events = []
    async for event in agent.extract_single_document_schema(metadata):
        events.append(event)
        
    # Assert
    assert len(events) > 0
    statuses = [e["status"] for e in events if "status" in e]
    results = [e["result"] for e in events if "result" in e]
    
    assert any("Collecting metadata" in s for s in statuses)
    assert any("Reading the document" in s for s in statuses)
    assert any("Done extracting" in s for s in statuses)
    
    assert len(results) == 1
    result = results[0]
    assert result["id"] == "file-123"
    assert result["document_name"] == "National ID"
    assert result["status"] == ExtractionStatus.SUCCESS
    assert result["confidence_score"] == 0.98
    
    # Verify cleanup was called
    mock_gemini_client.aio.files.delete.assert_called_once_with(name="files/mock-file-123")


@pytest.mark.asyncio
async def test_gemini_agents_extract_single_document_schema_missing_mime_type(mock_gemini_client):
    # Arrange
    agent = GeminiAgents()
    metadata = {
        "id": "file-123",
        "file_name": "my_national_id.png"
        # file_type is missing
    }
    
    # Act
    events = []
    async for event in agent.extract_single_document_schema(metadata):
        events.append(event)
        
    # Assert
    results = [e["result"] for e in events if "result" in e]
    assert len(results) == 1
    result = results[0]
    assert result["status"] == ExtractionStatus.FAILED
    assert "Missing mime_type" in result["error"]


@pytest.mark.asyncio
async def test_gemini_agents_extract_single_document_schema_gcs_failure(mock_gemini_client, monkeypatch):
    # Arrange
    agent = GeminiAgents()
    metadata = {
        "id": "file-123",
        "file_name": "my_national_id.png",
        "file_type": "image/png"
    }
    
    # Mock GCS Service to throw an exception
    mock_gcs = MagicMock()
    mock_gcs.get_gcs_storage_path.return_value = "api/public/upload/file-123"
    mock_gcs.download_object_as_bytes.side_effect = Exception("GCS Down")
    monkeypatch.setattr("src.infrastructure.gcs_service.gcs_service", mock_gcs)
    
    # Act
    events = []
    async for event in agent.extract_single_document_schema(metadata):
        events.append(event)
        
    # Assert
    results = [e["result"] for e in events if "result" in e]
    assert len(results) == 1
    result = results[0]
    assert result["status"] == ExtractionStatus.FAILED
    assert "GCS Down" in result["error"]


@pytest.mark.asyncio
async def test_gemini_agents_extract_schemas_batch(mock_gemini_client, monkeypatch):
    # Arrange
    agent = GeminiAgents()
    files = [
        {"id": "file-1", "file_name": "id1.png", "file_type": "image/png"},
        {"id": "file-2", "file_name": "id2.png", "file_type": "image/png"}
    ]
    
    # Mock GCS
    mock_gcs = MagicMock()
    mock_gcs.get_gcs_storage_path.return_value = "api/public/upload/file-1"
    mock_gcs.download_object_as_bytes.return_value = b"bytes"
    monkeypatch.setattr("src.infrastructure.gcs_service.gcs_service", mock_gcs)
    
    # Mock generate_content response
    mock_response = MagicMock()
    mock_response.text = (
        '{"document_name": "Mock Document", "file_name": "id1.png", "confidence_score": 0.95, '
        '"fields": []}'
    )
    mock_gemini_client.aio.models.generate_content.return_value = mock_response
    
    # Act
    results = await agent.extract_schemas(files)
    
    # Assert
    assert len(results) == 2
    assert results[0]["status"] == ExtractionStatus.SUCCESS
    assert results[1]["status"] == ExtractionStatus.SUCCESS
