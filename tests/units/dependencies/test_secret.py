import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from starlette.requests import Request

# ==========================================
# HELPERS
# ==========================================

def make_request(ip: str = "192.168.1.1", headers: dict = {}) -> MagicMock:
    """Build a minimal mock Request object."""
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = ip
    request.headers = headers
    request.url.path = "/api/public/document/registration"
    return request


# ==========================================
# document_agent_secret
# ==========================================

class TestDocumentAgentSecret:

    @pytest.fixture(autouse=True)
    def mock_redis(self, monkeypatch):
        mock = AsyncMock()
        mock.get.return_value = None   # IP not banned by default
        mock.set.return_value = True
        monkeypatch.setattr("src.dependencies.secrets.redis_service", mock)
        self.redis = mock

    @pytest.fixture(autouse=True)
    def mock_settings(self, monkeypatch):
        monkeypatch.setattr("src.dependencies.secrets.settings.SECRET_HEADER_NAME", "X-Secret-Key")
        monkeypatch.setattr("src.dependencies.secrets.settings.SECRET_HEADER_KEY", "valid-secret")

    async def test_valid_secret_passes(self):
        from src.dependencies.secrets import document_agent_secret

        request = make_request(headers={"X-Secret-Key": "valid-secret"})
        # Should not raise
        await document_agent_secret(request)

    async def test_missing_secret_raises_401_and_bans_ip(self):
        from src.dependencies.secrets import document_agent_secret
        from src.dependencies.secrets import document_agent_secret
        from src.cache.redis_cache import BAN_IP_CACHE_PREFIX, BAN_IP_CACHE_TTL

        request = make_request(ip="10.0.0.1", headers={})
        with pytest.raises(HTTPException) as exc:
            await document_agent_secret(request)

        assert exc.value.status_code == 401
        # IP should be written to ban cache
        self.redis.set.assert_called_once_with(
            key="10.0.0.1",
            value="10.0.0.1",
            prefix=BAN_IP_CACHE_PREFIX,
            ttl=BAN_IP_CACHE_TTL,
            nx=False
        )

    async def test_wrong_secret_raises_401_and_bans_ip(self):
        from src.dependencies.secrets import document_agent_secret

        request = make_request(ip="10.0.0.2", headers={"X-Secret-Key": "wrong-secret"})
        with pytest.raises(HTTPException) as exc:
            await document_agent_secret(request)

        assert exc.value.status_code == 401
        self.redis.set.assert_called_once()

    async def test_banned_ip_raises_401_before_secret_check(self):
        from src.dependencies.secrets import document_agent_secret

        # Simulate IP already in ban cache
        self.redis.get.return_value = "10.0.0.3"

        request = make_request(ip="10.0.0.3", headers={"X-Secret-Key": "valid-secret"})
        with pytest.raises(HTTPException) as exc:
            await document_agent_secret(request)

        assert exc.value.status_code == 401
        assert "don't have access" in exc.value.detail.lower()
        # Secret check never reached — no ban write
        self.redis.set.assert_not_called()

    async def test_no_client_host_uses_unknown(self):
        from src.dependencies.secrets import document_agent_secret
        from src.cache.redis_cache import BAN_IP_CACHE_PREFIX

        request = make_request(headers={"X-Secret-Key": "valid-secret"})
        request.client = None  # simulate missing client

        # Should complete without raising — "Unknown" is used as the IP
        await document_agent_secret(request)
        self.redis.get.assert_called_once_with(key="Unknown", prefix=BAN_IP_CACHE_PREFIX)

