from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException
import pytest
from tests.units.dependencies.test_secret import make_request

# ==========================================
# rate_limit_by_ip
# ==========================================

class TestRateLimitByIp:

    @pytest.fixture(autouse=True)
    def mock_ratelimit(self, monkeypatch):
        """
        Patch the Ratelimit class itself so no real Upstash client is created.
        """
        self.mock_limiter = AsyncMock()
        mock_ratelimit_cls = MagicMock(return_value=self.mock_limiter)
        monkeypatch.setattr("src.dependencies.rate_limit.Ratelimit", mock_ratelimit_cls)

    async def test_allowed_request_passes(self):
        from src.dependencies.rate_limit import rate_limit_by_ip

        self.mock_limiter.limit.return_value = MagicMock(allowed=True)

        request = make_request(ip="192.168.1.1")
        dependency = rate_limit_by_ip(max_request=10, window=60)

        # Should not raise
        await dependency(request)
        self.mock_limiter.limit.assert_called_once_with(
            "/api/public/document/registration:192.168.1.1"
        )

    async def test_exceeded_limit_raises_429(self):
        from src.dependencies.rate_limit import rate_limit_by_ip

        self.mock_limiter.limit.return_value = MagicMock(allowed=False)

        request = make_request(ip="192.168.1.2")
        dependency = rate_limit_by_ip(max_request=10, window=60)

        with pytest.raises(HTTPException) as exc:
            await dependency(request)

        assert exc.value.status_code == 429
        assert exc.value.detail == "Too many requests."

    async def test_limiter_unavailable_fails_open(self):
        """When Redis is down, request should pass through — not crash."""
        from src.dependencies.rate_limit import rate_limit_by_ip

        self.mock_limiter.limit.side_effect = Exception("Redis unreachable")

        request = make_request(ip="192.168.1.3")
        dependency = rate_limit_by_ip(max_request=10, window=60)

        # Should not raise — fails open by design
        await dependency(request)

    async def test_no_client_host_falls_back_to_unknown(self):
        from src.dependencies.rate_limit import rate_limit_by_ip

        self.mock_limiter.limit.return_value = MagicMock(allowed=True)

        request = make_request()
        request.client = None
        dependency = rate_limit_by_ip()

        await dependency(request)
        # Should use "Unknown" as the IP key
        call_arg = self.mock_limiter.limit.call_args[0][0]
        assert call_arg.endswith(":Unknown")