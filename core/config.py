"""
Secure Environment Configuration using Pydantic Settings
File: core/config.py
"""

from typing import Literal, Optional
from functools import lru_cache

from pydantic import Field, SecretStr, PostgresDsn, RedisDsn, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PayswapConfig(BaseSettings):
    """Secure application settings using Pydantic."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ============================================================================
    # APPLICATION
    # ============================================================================
    APP_NAME: str = Field(default="Payswap")
    APP_ENV: Literal["development", "staging", "production"] = Field(default="development")
    DEBUG: bool = Field(default=False)
    SECRET_KEY: SecretStr = Field(..., min_length=50)
    ALLOWED_HOSTS: str = Field(default="localhost,127.0.0.1")
    TIMEZONE: str = Field(default="Asia/Kolkata")

    # ============================================================================
    # DATABASE
    # ============================================================================
    DATABASE_URL: PostgresDsn = Field(...)

    # ============================================================================
    # REDIS
    # ============================================================================
    REDIS_URL: RedisDsn = Field(...)

    # ============================================================================
    # CELERY
    # ============================================================================
    CELERY_BROKER_URL: RedisDsn = Field(...)
    CELERY_RESULT_BACKEND: RedisDsn = Field(...)
    CELERY_TIMEZONE: str = Field(default="Asia/Kolkata")

    # ============================================================================
    # SECURITY
    # ============================================================================
    ENCRYPTION_KEY: SecretStr = Field(..., min_length=32)
    SIGNING_SECRET: SecretStr = Field(..., min_length=32)
    JWT_SIGNING_KEY: SecretStr = Field(..., min_length=32)
    JWT_ACCESS_TOKEN_LIFETIME: int = Field(default=300)
    JWT_REFRESH_TOKEN_LIFETIME: int = Field(default=86400)

    # ============================================================================
    # SMS - KALEYRA
    # ============================================================================
    KALEYRA_API_KEY: SecretStr = Field(...)
    KALEYRA_SID: str = Field(...)
    KALEYRA_BASE_URL: str = Field(default="https://api.kaleyra.io/v1")
    
    # ============================================================================
    # DOCUMENT VERIFICATION
    # ============================================================================
    CASHFREE_API_KEY: Optional[SecretStr] = Field(default=None)
    CASHFREE_API_SECRET: Optional[SecretStr] = Field(default=None)
    INVINCIBLE_OCEAN_API_KEY: Optional[SecretStr] = Field(default=None)
    INVINCIBLE_OCEAN_API_SECRET: Optional[SecretStr] = Field(default=None)

    # ============================================================================
    # EMAIL
    # ============================================================================
    SMTP_HOST: str = Field(default="smtp.office365.com")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(...)
    SMTP_PASSWORD: SecretStr = Field(...)
    SMTP_USE_TLS: bool = Field(default=True)
    SMTP_DEFAULT_FROM: str = Field(default="no-reply@payswap.in")

    # ============================================================================
    # AWS S3
    # ============================================================================
    S3_ACCESS_KEY: SecretStr = Field(...)
    S3_SECRET_KEY: SecretStr = Field(...)
    S3_BUCKET: str = Field(default="payswap-documents")
    S3_REGION: str = Field(default="ap-south-1")
    S3_ENDPOINT_URL: Optional[str] = Field(default=None)

    # ============================================================================
    # LOGGING
    # ============================================================================
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    PAYSWAP_LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="DEBUG")
    PAYSWAP_LOG_TEXT_FORMAT: bool = Field(default=False)
    PAYSWAP_LOG_ENABLE_API_CONTEXT: bool = Field(default=True)
    PAYSWAP_MASK_SHOW_START: int = Field(default=4)
    PAYSWAP_MASK_SHOW_END: int = Field(default=3)
    PAYSWAP_LOG_RETENTION_DAYS: int = Field(default=30)
    PAYSWAP_LOG_DIR: str = Field(default="logs")

    # ============================================================================
    # SENTRY
    # ============================================================================
    SENTRY_ENABLED: bool = Field(default=False)
    SENTRY_DSN: Optional[SecretStr] = Field(default=None)
    SENTRY_ENVIRONMENT: Optional[str] = Field(default=None)

    # ============================================================================
    # CORS
    # ============================================================================
    CORS_ALLOWED_ORIGINS: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    CORS_ALLOW_CREDENTIALS: bool = Field(default=True)

    # ============================================================================
    # VALIDATORS
    # ============================================================================
    @model_validator(mode="after")
    def validate_debug_mode(self):
        """Validate DEBUG is False in production."""
        if self.APP_ENV == "production" and self.DEBUG:
            raise ValueError("DEBUG must be False in production")
        return self

    @model_validator(mode="after")
    def set_sentry_environment(self):
        if self.SENTRY_ENABLED and not self.SENTRY_ENVIRONMENT:
            self.SENTRY_ENVIRONMENT = self.APP_ENV
        return self

    # ============================================================================
    # PROPERTIES
    # ============================================================================
    @property
    def allowed_hosts_list(self) -> list[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",")]

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    # ============================================================================
    # SECURE ACCESSORS
    # ============================================================================
    def get_secret_key(self) -> str:
        return self.SECRET_KEY.get_secret_value()

    def get_encryption_key(self) -> str:
        return self.ENCRYPTION_KEY.get_secret_value()

    def get_signing_secret(self) -> str:
        return self.SIGNING_SECRET.get_secret_value()

    def get_jwt_signing_key(self) -> str:
        return self.JWT_SIGNING_KEY.get_secret_value()

    def get_smtp_password(self) -> str:
        return self.SMTP_PASSWORD.get_secret_value()

    def get_kaleyra_api_key(self) -> str:
        return self.KALEYRA_API_KEY.get_secret_value()
    
    def get_cashfree_api_key(self) -> str:
        return self.CASHFREE_API_KEY.get_secret_value() if self.CASHFREE_API_KEY else ""
    
    def get_cashfree_api_secret(self) -> str:
        return self.CASHFREE_API_SECRET.get_secret_value() if self.CASHFREE_API_SECRET else ""
    
    def get_invincible_ocean_api_key(self) -> str:
        return self.INVINCIBLE_OCEAN_API_KEY.get_secret_value() if self.INVINCIBLE_OCEAN_API_KEY else ""
    
    def get_invincible_ocean_api_secret(self) -> str:
        return self.INVINCIBLE_OCEAN_API_SECRET.get_secret_value() if self.INVINCIBLE_OCEAN_API_SECRET else ""

    def get_s3_access_key(self) -> str:
        return self.S3_ACCESS_KEY.get_secret_value()

    def get_s3_secret_key(self) -> str:
        return self.S3_SECRET_KEY.get_secret_value()

    def get_sentry_dsn(self) -> str:
        return self.SENTRY_DSN.get_secret_value() if self.SENTRY_DSN else ""

    # ============================================================================
    # CONFIG GENERATORS
    # ============================================================================
    def get_database_config(self) -> dict:
        """Generate Django database configuration."""
        import dj_database_url
        return dj_database_url.parse(str(self.DATABASE_URL))

    def get_redis_config(self) -> dict:
        """Generate Redis cache configuration."""
        return {
            "default": {
                "BACKEND": "django_redis.cache.RedisCache",
                "LOCATION": str(self.REDIS_URL),
                "OPTIONS": {
                    "CLIENT_CLASS": "django_redis.client.DefaultClient",
                    "CONNECTION_POOL_KWARGS": {"max_connections": 50},
                },
                "KEY_PREFIX": f"{self.APP_NAME.lower()}",
                "TIMEOUT": 300,
            }
        }

    def get_celery_config(self) -> dict:
        """Generate Celery configuration."""
        return {
            "broker_url": str(self.CELERY_BROKER_URL),
            "result_backend": str(self.CELERY_RESULT_BACKEND),
            "timezone": self.CELERY_TIMEZONE,
            "task_serializer": "json",
            "result_serializer": "json",
            "accept_content": ["json"],
            "task_track_started": True,
            "task_time_limit": 1800,
            "task_soft_time_limit": 1500,
            "broker_connection_retry_on_startup": True,
        }

    def get_email_config(self) -> dict:
        """Generate email configuration."""
        return {
            "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
            "EMAIL_HOST": self.SMTP_HOST,
            "EMAIL_PORT": self.SMTP_PORT,
            "EMAIL_USE_TLS": self.SMTP_USE_TLS,
            "EMAIL_HOST_USER": self.SMTP_USER,
            "EMAIL_HOST_PASSWORD": self.get_smtp_password(),
            "DEFAULT_FROM_EMAIL": self.SMTP_DEFAULT_FROM,
        }

    def get_s3_config(self) -> dict:
        """Generate S3 storage configuration."""
        config = {
            "AWS_ACCESS_KEY_ID": self.get_s3_access_key(),
            "AWS_SECRET_ACCESS_KEY": self.get_s3_secret_key(),
            "AWS_STORAGE_BUCKET_NAME": self.S3_BUCKET,
            "AWS_S3_REGION_NAME": self.S3_REGION,
            "AWS_S3_FILE_OVERWRITE": False,
            "AWS_DEFAULT_ACL": "private",
            "AWS_S3_SIGNATURE_VERSION": "s3v4",
        }
        if self.S3_ENDPOINT_URL:
            config["AWS_S3_ENDPOINT_URL"] = self.S3_ENDPOINT_URL
        return config


@lru_cache()
def get_settings() -> PayswapConfig:
    """Get cached settings instance."""
    return PayswapConfig()


# Convenience instance
payswap_config = get_settings()