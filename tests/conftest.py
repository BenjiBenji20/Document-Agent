import os

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

# ==========================================
# 1. EXTERNAL SERVICE MOCKS
# Pattern: Create Mock -> Patch -> Yield
# ==========================================

# Set APP_NAME BEFORE any imports of src.main
os.environ.setdefault("APP_NAME", "Document Agent Test")

@pytest.fixture
def mock_redis(monkeypatch):
    """
    Intercepts the real Redis service and replaces it with an AsyncMock.
    """
    # Import the actual service type/instance for spec and patching
    from src.cache.redis_cache import redis_service
    
    mock = AsyncMock(spec=redis_service)
    # Setup default mock behaviors (can be overridden in specific tests)
    mock.get.return_value = None
    mock.set.return_value = True
    mock.exists.return_value = False
    mock._client = AsyncMock() # Required for upstash-ratelimit initialization
    
    # Replace the actual module instance
    monkeypatch.setattr("src.cache.redis_cache.redis_service", mock)
    monkeypatch.setattr("src.modules.fields_registration.document_registration_service.redis_service", mock, raising=False)
    monkeypatch.setattr("src.api.document_registration_router.redis_service", mock, raising=False)
    monkeypatch.setattr("src.dependencies.secrets.redis_service", mock, raising=False)

    
    # Yield the mock so individual tests can assert what was called
    yield mock


@pytest.fixture
def mock_gcs_client(monkeypatch):
    """
    Intercepts the GCP Storage client creation and replaces it with a MagicMock.
    We intentionally DO NOT mock `from_service_account_info` so that the actual
    secret keys in settings are parsed and validated by the Google library.
    """
    from unittest.mock import MagicMock
    from google.cloud import storage
    
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock(spec=storage.Bucket)
    mock_client.bucket.return_value = mock_bucket
    
    # Mock the Client constructor
    monkeypatch.setattr("src.infrastructure.gcs_client.storage.Client", MagicMock(return_value=mock_client))
    
    yield mock_client


# ==========================================
# 2. FASTAPI APP CLIENT
# Pattern: Inject required mocks -> Yield Client
# ==========================================

@pytest.fixture
def client(mock_redis):
    """
    Global test client. 
    By depending on `mock_redis`, we ensure the app never hits live Upstash
    when handling test HTTP requests.
    """
    # Import app inside the fixture to ensure mocks are applied BEFORE the app is loaded
    from src.main import app
    
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_base_agent(monkeypatch):
    """
    Provider-agnostic agent mock fixture.
    Mimics the select_provider method of OrchestrateAgentCall.
    """
    from src.agents.base_agent import BaseAgent
    from unittest.mock import MagicMock, AsyncMock
    
    mock_agent = MagicMock(spec=BaseAgent)
    mock_agent.extract_schemas = AsyncMock(return_value=[])
    
    async def dummy_stream(files):
        yield {"status": "Mock status update"}
        yield {"result": {
            "id": "test-file-id",
            "document_name": "Mock Document",
            "fields": [],
            "file_name": "mock.pdf",
            "confidence_score": 0.95,
            "status": "success",
            "error": None
        }}
        
    mock_agent.extract_schemas_stream = dummy_stream
    mock_agent.extract_single_document_schema = dummy_stream

    # Patch select_provider to return our mock
    monkeypatch.setattr("src.agents.orchestrate_agent_call.OrchestrateAgentCall.select_provider", MagicMock(return_value=mock_agent))
    monkeypatch.setattr("src.modules.fields_registration.document_registration_service.OrchestrateAgentCall.select_provider", MagicMock(return_value=mock_agent), raising=False)
    
    yield mock_agent


@pytest.fixture
def mock_gemini_client(monkeypatch):
    """
    Mocks the google-genai Client specifically for Gemini agents tests.
    """
    from unittest.mock import MagicMock, AsyncMock
    from google import genai
    
    mock_client = MagicMock(spec=genai.Client)
    mock_client.aio = MagicMock()
    mock_client.aio.files = AsyncMock()
    mock_client.aio.models = AsyncMock()
    
    # Mock uploaded file state
    mock_file = MagicMock()
    mock_file.name = "files/mock-file-123"
    mock_file.state.name = "ACTIVE"
    mock_client.aio.files.upload.return_value = mock_file
    mock_client.aio.files.get.return_value = mock_file
    
    # Mock generate_content response
    mock_response = MagicMock()
    mock_response.text = '{"document_name": "Mock Document", "fields": [], "file_name": "mock.pdf", "confidence_score": 0.95}'
    mock_client.aio.models.generate_content.return_value = mock_response
    
    monkeypatch.setattr("src.agents.gemini_agents.genai.Client", MagicMock(return_value=mock_client))
    
    yield mock_client
