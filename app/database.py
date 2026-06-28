import certifi
from motor.motor_asyncio import AsyncIOMotorClient

from .settings import settings

_client: AsyncIOMotorClient | None = None


def _client_kwargs() -> dict:
    uri = settings.mongodb_uri.lower()
    if uri.startswith("mongodb+srv://") or "tls=true" in uri:
        # certifi + OCSP disable: common fix for Atlas TLS in Docker/VPS containers
        return {
            "tlsCAFile": certifi.where(),
            "tlsDisableOCSPEndpointCheck": True,
            "serverSelectionTimeoutMS": 15000,
            "connectTimeoutMS": 15000,
        }
    return {}


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri, **_client_kwargs())
    return _client


def get_database():
    return get_client()[settings.mongodb_db_name]


async def get_db():
    yield get_database()
