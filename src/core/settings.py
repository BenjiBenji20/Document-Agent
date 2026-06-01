from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str | None = "Document Agent"
    LOG_LEVEL: str | None = "DEBUG"
    SECRET_HEADER_NAME: SecretStr | None = None
    SECRET_HEADER_KEY: SecretStr | None = None
    
    UPSTASH_REDIS_REST_URL: str | None = None
    UPSTASH_REDIS_REST_TOKEN: str | None = None
    
    TYPE: str | None = None 
    PROJECT_ID: str | None = None 
    PRIVATE_KEY_ID: str | None = None 
    PRIVATE_KEY: str | None = None 
    CLIENT_EMAIL: str | None = None 
    CLIENT_ID: str | None = None 
    AUTH_URI: str | None = None 
    TOKEN_URI: str | None = None 
    AUTH_PROVIDER_X509_CERT_URL: str | None = None 
    CLIENT_X509_CERT_URL: str | None = None 
    UNIVERSE_DOMAIN: str | None = None
    
    GCS_BUCKET_NAME: str | None = None
    GCS_SIGNED_URL_EXPIRATION: int | None = None
    
    AGENT_API_KEY: str | None = None
    AGENT_PROVIDER: str = "google"
    
    DEV_ORIGIN: str | None = None
    PROD_ORIGIN: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    @property
    def get_gcs_credentials(self) -> dict:
        """Returns the Google credentials as a dictionary"""
        return {
            "type": self.TYPE,
            "project_id": self.PROJECT_ID,
            "private_key_id": self.PRIVATE_KEY_ID,
            "private_key": self.PRIVATE_KEY,
            "client_email": self.CLIENT_EMAIL,
            "client_id": self.CLIENT_ID,
            "auth_uri": self.AUTH_URI,
            "token_uri": self.TOKEN_URI,
            "auth_provider_x509_cert_url": self.AUTH_PROVIDER_X509_CERT_URL,
            "client_x509_cert_url": self.CLIENT_X509_CERT_URL,
            "universe_domain": self.UNIVERSE_DOMAIN
        }
        
settings = Settings()
