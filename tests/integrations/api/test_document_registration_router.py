import pytest

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

def test_registration_router_happy_path(client, mock_redis):
    # Arrange
    mock_redis.set_hash_many.return_value = True
    payload = [
        {
            "document_name": "National ID",
            "fields": [
                {"field": "first_name", "is_required": True},
                {"field": "last_name", "is_required": True}
            ]
        }
    ]

    # Act
    response = client.post("/api/public/document/registration/false", json=payload)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    
    doc_response = data[0]
    assert doc_response["details"]["successful"] is True
    assert doc_response["details"]["success_count"] == 1
    assert doc_response["document_metadata"]["document_name"] == "National ID"
    assert len(doc_response["document_metadata"]["fields"]) == 2

def test_registration_router_negative_path_invalid_payload(client, mock_redis):
    # Arrange
    # Missing 'fields' which is required
    invalid_payload = [
        {
            "document_name": "Invalid Doc"
        }
    ]

    # Act
    response = client.post("/api/public/document/registration/false", json=invalid_payload)

    # Assert
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    # Ensure it's a validation error for the missing 'fields'
    assert any(error["loc"] == ["body", 0, "fields"] for error in data["detail"])

def test_registration_router_negative_path_internal_error(client, mock_redis):
    # Arrange
    # Force redis to throw an exception to simulate internal server error
    mock_redis.set_hash_many.side_effect = Exception("Internal DB error")
    payload = [
        {
            "document_name": "National ID",
            "fields": [
                {"field": "first_name", "is_required": True}
            ]
        }
    ]

    # Act
    response = client.post("/api/public/document/registration/false", json=payload)

    # Assert
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to save document metadata."


def test_agent_extract_schemas_integration_happy_path(client, mock_redis, mock_base_agent, monkeypatch):
    # Arrange
    from unittest.mock import MagicMock
    mock_gcs = MagicMock()
    mock_gcs.get_gcs_storage_path.return_value = "api/public/upload/test-uuid"
    mock_gcs._get_model_file_uri.return_value = "gs://bucket/test-uuid"
    mock_gcs.get_object_metadata.return_value = {"size": 2048, "content_type": "application/pdf"}
    monkeypatch.setattr("src.modules.fields_registration.document_registration_service.gcs_service", mock_gcs)

    payload = [
        {
            "id": "test-uuid",
            "file_name": "national_id.pdf",
            "file_type": "application/pdf",
            "file_size": 2048
        }
    ]

    # Act
    # We must use client.post with stream=True or read the content directly
    response = client.post("/api/public/document/agent-extracts", json=payload)

    # Assert
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    content = response.text
    assert "Counting documents..." in content
    assert "event: result" in content
    assert "event: complete" in content


def test_agent_extract_schemas_integration_negative_empty(client, mock_redis):
    # Arrange
    payload = []

    # Act
    response = client.post("/api/public/document/agent-extracts", json=payload)

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "No files found."


def test_registration_router_happy_path_is_schema_extracted_true(client, mock_redis):
    # Arrange
    mock_redis.set_hash_many.return_value = True
    payload = [
        {
            "id": "c1a938c4-11e2-411a-8217-09eb12f5b5f2",
            "document_name": "National ID",
            "fields": [
                {"field": "first_name", "is_required": True}
            ]
        }
    ]

    # Act
    response = client.post("/api/public/document/registration/true", json=payload)

    # Assert
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    doc_response = data[0]
    assert doc_response["details"]["successful"] is True
    assert doc_response["document_metadata"]["id"] == "c1a938c4-11e2-411a-8217-09eb12f5b5f2"
    assert doc_response["document_metadata"]["document_name"] == "National ID"


def test_registration_router_negative_path_missing_id_when_is_schema_extracted_true(client, mock_redis):
    # Arrange
    payload = [
        {
            # 'id' is omitted, meaning it defaults to None
            "document_name": "National ID",
            "fields": [
                {"field": "first_name", "is_required": True}
            ]
        }
    ]

    # Act
    response = client.post("/api/public/document/registration/true", json=payload)

    # Assert
    assert response.status_code == 400
    assert "Document ID is required" in response.json()["detail"]
