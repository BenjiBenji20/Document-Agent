from fastapi import Request, HTTPException, status
from src.core.settings import settings
import logging
from src.cache.redis_cache import redis_service, BAN_IP_CACHE_PREFIX, BAN_IP_CACHE_TTL

logger = logging.getLogger(__name__)

async def document_agent_secret(request: Request) -> None:
    """
    Pass secrets in header
    IF request has wrong secrets, ban the IP for 1 day.
    It's a total sign that attacker is accessing the API else where.
    """
    # 1. check in cache if IP is currently ban, if True, deny the requests
    ip = request.client.host if request.client else "Unknown"
    is_ip_ban = await redis_service.get(key=ip, prefix=BAN_IP_CACHE_PREFIX)
    if is_ip_ban:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Requests denied. You don't have access to this service. Please visit again later."
        )
    
    # support both str and SecretStr
    header_name = settings.SECRET_HEADER_NAME
    if hasattr(header_name, "get_secret_value"):
        header_name = header_name.get_secret_value()
    
    # 2. check if secret is matched, if False, ban for 1 day store in cache
    secret: str = request.headers.get(header_name, "Anonymous")
    
    # support both str and SecretStr
    secret_key = settings.SECRET_HEADER_KEY
    if hasattr(secret_key, "get_secret_value"):
        secret_key = secret_key.get_secret_value()
        
    if secret.strip() != secret_key:
        logger.debug("[DEBUG] Secret key not match. Check header name or value.")
        await redis_service.set(
                key=ip,
                value=ip,
                prefix=BAN_IP_CACHE_PREFIX,
                ttl=BAN_IP_CACHE_TTL,
                nx=False # overwrite if already exists to reset TTL
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Requests denied. Ban for 1 day."
        )

    logger.info("[SUCCESS] Requests success. Secrets are matched.")
