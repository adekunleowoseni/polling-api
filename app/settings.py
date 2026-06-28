from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _db_name_from_uri(uri: str) -> str | None:
    normalized = uri.replace("mongodb+srv://", "mongodb://", 1)
    path = (urlparse(normalized).path or "").lstrip("/").split("?")[0]
    if path and "." not in path and "@" not in path:
        return path
    return None


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

    @model_validator(mode="after")
    def normalize_mongodb_db_name(self) -> "Settings":
        name = self.mongodb_db_name.strip()
        invalid = (
            not name
            or "." in name
            or "/" in name
            or "mongodb" in name.lower()
            or "@" in name
        )
        if invalid:
            from_uri = _db_name_from_uri(self.mongodb_uri)
            self.mongodb_db_name = from_uri or "poll-live-feed"
        return self


settings = Settings()
