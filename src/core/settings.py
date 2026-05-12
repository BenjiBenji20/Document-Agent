from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str
    LOG_LEVEL: str | None = "DEBUG"
    SECRET_HEADER_NAME: SecretStr | None = None
    SECRET_HEADER_KEY: SecretStr | None = None
    
    UPSTASH_REDIS_REST_URL: str | None = None
    UPSTASH_REDIS_REST_TOKEN: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
        
settings = Settings()
