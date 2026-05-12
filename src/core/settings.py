from pydantic import SecretStr
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str
    LOG_LEVEL: str | None = "DEBUG"
    SECRET_HEADER_NAME: SecretStr | None = None
    SECRET_HEADER_KEY: SecretStr | None = None
    
    UPSTASH_REDIS_REST_URL: str | None = None
    UPSTASH_REDIS_REST_TOKEN: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"

        
settings = Settings()
