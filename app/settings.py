from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Defaults match a local MongoDB on 27017 (MongoDB Compass) without Docker.
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "poll-live-feed"
    google_cloud_project_id: str = ""
    google_cloud_location: str = "us"
    google_documentai_processor_id: str = ""
    super_admin_email: str = "admin@ogun.monitor"
    super_admin_password: str = "ChangeMeAdmin123!"
    # Comma-separated browser origins allowed to call the API (Vercel + local dev).
    cors_origins: str = "http://localhost:3000"


settings = Settings()
