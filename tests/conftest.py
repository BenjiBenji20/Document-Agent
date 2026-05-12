import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get.return_value = None
    redis.set.return_value = True
    return redis
