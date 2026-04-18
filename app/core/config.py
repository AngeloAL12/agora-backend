from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_IOS_CLIENT_ID: str = ""
    GOOGLE_ANDROID_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_TENANT_ID: str = ""

    API_TESTING_SECRET: str | None = None

    # Cloudflare R2 Storage
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_ENDPOINT: str = ""
    ENV: str = "development"
    R2_BUCKET_PRIVATE: str
    R2_BUCKET_PUBLIC: str
    R2_PUBLIC_URL: str | None = None

    @model_validator(mode="after")
    def set_r2_endpoint(self) -> "Settings":
        if not self.R2_ENDPOINT:
            self.R2_ENDPOINT = f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        return self

    # 'extra="ignore"' evita el error de "Extra inputs are not permitted"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
