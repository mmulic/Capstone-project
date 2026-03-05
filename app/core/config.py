from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "disaster-assessment-api"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api"

    # Database
    database_host: str = "db"
    database_port: int = 5432
    database_user: str = "postgres"
    database_password: str = "postgres_dev_password"
    database_name: str = "disaster_assessment"
    database_url: str = "postgresql+asyncpg://postgres:postgres_dev_password@db:5432/disaster_assessment"

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "disaster-assessment-images"

    # JWT
    jwt_secret_key: str = "dev-secret-change-in-production-!!!"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Gemini
    gemini_api_key: str = ""

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def s3_configured(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key)

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
