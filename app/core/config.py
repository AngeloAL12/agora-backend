from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_IOS_CLIENT_ID: str = ""
    GOOGLE_ANDROID_CLIENT_ID: str = ""
    MICROSOFT_CLIENT_ID: str = ""
    MICROSOFT_TENANT_ID: str = ""

    # 'extra="ignore"' evita el error de "Extra inputs are not permitted"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
