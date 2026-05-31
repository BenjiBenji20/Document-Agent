import pytest
import json
from unittest.mock import MagicMock
from src.agents.schemas.agent_extract_schemas import ExtractionStatus

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

def test_extract_values_happy_path(client, mock_redis, mock_base_agent, monkeypatch):
    # Arrange
    doc_id = "c1a938c4-11e2-411a-8217-09eb12f5b5f2"
    file_id = "713be2a3-2ee0-47b2-9a00-111111111111"
    
    # Patch redis_service in router
    monkeypatch.setattr("src.api.document_values_extraction_router.redis_service", mock_redis)
    
    # Mock Redis to return schema
    mock_redis.get_hash.return_value = {
        "document_name": "National ID",
        "fields": '[{"field": "first_name", "is_required": true}]'
    }
    
    # Mock GCS Service
    mock_gcs = MagicMock()
    mock_gcs.get_gcs_storage_path.return_value = f"api/public/upload/{file_id}"
    mock_gcs._get_model_file_uri.return_value = f"gs://bucket/{file_id}"
    mock_gcs.get_object_metadata.return_value = {"size": 1024}
    monkeypatch.setattr("src.modules.values_extraction.document_values_extraction_service.gcs_service", mock_gcs)
    
    # Mock Agent value stream
    async def dummy_values_stream(doc_to_extract):
        yield {"status": "Extracting values..."}
        yield {"result": {
            "document_id": doc_id,
            "file_id": file_id,
            "document_name": "National ID",
            "file_name": "my_doc.pdf",
            "field_values": {"first_name": "John"},
            "confidence_score": 0.99,
            "score_reason": "Clear text",
            "status": ExtractionStatus.SUCCESS
        }}
        
    mock_base_agent.extract_document_values_stream = dummy_values_stream
    
    payload = [
        {
            "document_id": doc_id,
            "file_id": file_id,
            "file_name": "my_doc.pdf",
            "file_type": "application/pdf"
        }
    ]
    
    # Act
    response = client.post("/api/public/document/extract-values", json=payload)
    
    # Assert
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    content = response.text
    assert "Extracting values..." in content
    assert "event: result" in content
    assert "John" in content
    assert "complete" in content


def test_extract_values_schema_not_found(client, mock_redis, monkeypatch):
    # Arrange
    doc_id = "c1a938c4-11e2-411a-8217-09eb12f5b5f2"
    file_id = "713be2a3-2ee0-47b2-9a00-111111111111"
    
    monkeypatch.setattr("src.api.document_values_extraction_router.redis_service", mock_redis)
    
    # Mock Redis to return None (miss)
    mock_redis.get_hash.return_value = None
    
    payload = [
        {
            "document_id": doc_id,
            "file_id": file_id,
            "file_name": "my_doc.pdf",
            "file_type": "application/pdf"
        }
    ]
    
    # Act
    response = client.post("/api/public/document/extract-values", json=payload)
    
    # Assert
    assert response.status_code == 200  # SSE streams return 200 but error event inside stream
    content = response.text
    assert "event: error" in content
    assert "not found or expired" in content


def test_extract_values_empty_payload(client):
    # Act
    response = client.post("/api/public/document/extract-values", json=[])
    
    # Assert
    assert response.status_code == 400
    assert "No extraction requests found." in response.json()["detail"]
