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
    response = client.post("/api/public/registration/registration", json=payload)

    # Assert
    assert response.status_code == 200
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
    response = client.post("/api/public/registration/registration", json=invalid_payload)

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
    response = client.post("/api/public/registration/registration", json=payload)

    # Assert
    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to save document metadata."
