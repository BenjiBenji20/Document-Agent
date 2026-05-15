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
    Also mocks credentials loading to avoid needing real JSON keys during tests.
    """
    from unittest.mock import MagicMock
    from google.cloud import storage
    
    mock_client = MagicMock(spec=storage.Client)
    mock_bucket = MagicMock(spec=storage.Bucket)
    mock_client.bucket.return_value = mock_bucket
    
    # Mock the Client constructor
    monkeypatch.setattr("src.infrastructure.gcs_client.storage.Client", MagicMock(return_value=mock_client))
    
    # Mock credentials loading so it doesn't crash on dummy settings
    mock_credentials = MagicMock()
    monkeypatch.setattr(
        "src.infrastructure.gcs_client.service_account.Credentials.from_service_account_info", 
        MagicMock(return_value=mock_credentials)
    )
    
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
