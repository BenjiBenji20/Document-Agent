import logging
from fastapi import HTTPException, Request
from upstash_ratelimit.asyncio import Ratelimit, SlidingWindow
from src.cache.redis_cache import redis_service

logger = logging.getLogger(__name__)


def rate_limit_by_ip(
    max_request=10, window=60
):
    """Rate Limit for IP based limiting"""
    ip_limiter = Ratelimit(
        redis=redis_service._client,
        limiter=SlidingWindow(max_requests=max_request, window=window),
        prefix="rl:ip"
    )
    
    async def dependency(request: Request):
        ip = request.client.host if request.client else "Unknown"
        try:
            response = await ip_limiter.limit(f"{request.url.path}:{ip}")
            if not response.allowed:
                raise HTTPException(status_code=429, detail="Too many requests.")
        except HTTPException:
            raise
        except Exception:
            logger.warning("Rate limiter unavailable (ip), failing open.")
    return dependency
