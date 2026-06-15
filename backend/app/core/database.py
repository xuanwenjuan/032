from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    AsyncIOMotorClient = None

from app.core.config import settings

client = None
_memory_db: Dict[str, List[Dict[str, Any]]] = {"simulation_tasks": []}


async def get_db():
    global client
    if MONGO_AVAILABLE:
        if client is None:
            try:
                client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=2000)
                await client.admin.command("ping")
                return client[settings.MONGODB_DB_NAME]
            except Exception:
                client = None
                return None
        return client[settings.MONGODB_DB_NAME]
    return None


async def close_db():
    global client
    if client and MONGO_AVAILABLE:
        try:
            client.close()
        except Exception:
            pass
        client = None


def use_memory_db():
    return not MONGO_AVAILABLE or client is None

