import logging
import datetime
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


async def check_extraction_rate_limit(request: Request, num_docs: int, limit: int = 50):
    """
    Limits the number of document extraction requests per user's IP address daily.
    The daily limit resets at Midnight UTC.
    """
    ip = request.client.host if request.client else "Unknown"
    key = f"rl:docs:{ip}"
    
    now = datetime.datetime.now(datetime.timezone.utc)
    tomorrow = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time.min, datetime.timezone.utc)
    ttl = int((tomorrow - now).total_seconds())
    
    LUA_INCR_LIMIT = """
    local current = redis.call('get', KEYS[1])
    if current == false then
        redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
        return {1, tonumber(ARGV[1])}
    elseif tonumber(current) + tonumber(ARGV[1]) > tonumber(ARGV[3]) then
        return {0, tonumber(current)}
    else
        local new_val = redis.call('incrby', KEYS[1], ARGV[1])
        return {1, new_val}
    end
    """
    
    try:
        res = await redis_service._client.eval(
            LUA_INCR_LIMIT,
            keys=[key],
            args=[str(num_docs), str(ttl), str(limit)]
        )
        
        allowed, count = res[0], res[1]
        if not allowed:
            remaining = limit - count
            raise HTTPException(
                status_code=429,
                detail=f"Daily document extraction limit exceeded for your IP. Max: {limit} daily. Remaining allocation: {max(0, remaining)}."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Daily document rate limiter failed: {e}. Failing open.")

