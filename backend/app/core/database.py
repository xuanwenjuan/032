from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from bson import ObjectId
import base64
import io

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    AsyncIOMotorClient = None
    AsyncIOMotorGridFSBucket = None

from app.core.config import settings

client = None
gridfs_bucket = None
_memory_db: Dict[str, List[Dict[str, Any]]] = {
    "simulation_tasks": [],
    "gridfs_files": [],
    "gridfs_chunks": []
}

LARGE_FIELD_THRESHOLD = 100 * 1024
GRIDFS_FIELDS = [
    "reconstructed_image_base64",
    "true_image_base64",
    "fused_image_base64",
    "reconstructed_images_base64"
]


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


async def get_gridfs():
    global gridfs_bucket
    db = await get_db()
    if db is None:
        return None
    if gridfs_bucket is None:
        gridfs_bucket = AsyncIOMotorGridFSBucket(db)
    return gridfs_bucket


async def close_db():
    global client, gridfs_bucket
    if client and MONGO_AVAILABLE:
        try:
            client.close()
        except Exception:
            pass
        client = None
        gridfs_bucket = None


def use_memory_db():
    return not MONGO_AVAILABLE or client is None


def _is_large_base64(data: Any, field_name: str) -> bool:
    if not isinstance(data, (str, dict)):
        return False
    if field_name not in GRIDFS_FIELDS:
        return False
    if isinstance(data, dict):
        total_len = sum(len(v) for v in data.values() if isinstance(v, str))
        return total_len > LARGE_FIELD_THRESHOLD
    return len(data) > LARGE_FIELD_THRESHOLD


async def _store_large_field(
    field_name: str,
    data: Any,
    task_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[Any, Optional[str]]:
    if not _is_large_base64(data, field_name):
        return data, None

    if use_memory_db():
        file_id = str(ObjectId())
        _memory_db["gridfs_files"].append({
            "_id": ObjectId(file_id),
            "filename": f"{task_id}_{field_name}",
            "contentType": "application/octet-stream",
            "length": len(str(data)),
            "uploadDate": datetime.now(),
            "metadata": {
                "task_id": task_id,
                "field_name": field_name,
                **(metadata or {})
            },
            "data": data
        })
        return {
            "$gridfs_ref": file_id,
            "field_name": field_name,
            "storage": "memory"
        }, file_id

    fs = await get_gridfs()
    if fs is None:
        return data, None

    if isinstance(data, dict):
        import json
        bytes_data = json.dumps(data).encode('utf-8')
        content_type = "application/json"
    elif isinstance(data, str):
        try:
            if data.startswith('data:') or len(data) % 4 == 0:
                try:
                    bytes_data = base64.b64decode(data)
                    content_type = "image/png"
                except Exception:
                    bytes_data = data.encode('utf-8')
                    content_type = "text/plain"
            else:
                bytes_data = data.encode('utf-8')
                content_type = "text/plain"
        except Exception:
            bytes_data = data.encode('utf-8')
            content_type = "text/plain"
    else:
        bytes_data = str(data).encode('utf-8')
        content_type = "text/plain"

    file_metadata = {
        "task_id": task_id,
        "field_name": field_name,
        "content_type": content_type,
        **(metadata or {})
    }

    file_id = await fs.upload_from_stream(
        filename=f"{task_id}_{field_name}",
        source=io.BytesIO(bytes_data),
        metadata=file_metadata
    )

    return {
        "$gridfs_ref": str(file_id),
        "field_name": field_name,
        "content_type": content_type,
        "storage": "gridfs"
    }, str(file_id)


async def _retrieve_large_field(ref: Dict[str, Any]) -> Any:
    if not isinstance(ref, dict) or "$gridfs_ref" not in ref:
        return ref

    file_id = ref["$gridfs_ref"]
    field_name = ref["field_name"]
    storage = ref.get("storage", "gridfs")

    if storage == "memory":
        for f in _memory_db["gridfs_files"]:
            if str(f["_id"]) == file_id:
                return f["data"]
        return None

    fs = await get_gridfs()
    if fs is None:
        return None

    try:
        out = io.BytesIO()
        await fs.download_to_stream(ObjectId(file_id), out)
        data_bytes = out.getvalue()
        content_type = ref.get("content_type", "text/plain")
        if content_type == "application/json":
            import json
            return json.loads(data_bytes.decode('utf-8'))
        elif content_type == "image/png":
            return base64.b64encode(data_bytes).decode('ascii')
        else:
            try:
                return data_bytes.decode('utf-8')
            except Exception:
                return base64.b64encode(data_bytes).decode('ascii')
    except Exception as e:
        print(f"[GridFS] 读取失败 {file_id}: {e}")
        return None


async def process_large_fields_for_store(
    task_data: Dict[str, Any],
    task_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], List[str]]:
    processed = dict(task_data)
    stored_ids = []

    for field_name in GRIDFS_FIELDS:
        if field_name in processed and processed[field_name] is not None:
            if _is_large_base64(processed[field_name], field_name):
                stored_value, file_id = await _store_large_field(
                    field_name, processed[field_name], task_id, metadata
                )
                if file_id:
                    processed[field_name] = stored_value
                    stored_ids.append(file_id)

    return processed, stored_ids


async def process_large_fields_for_retrieve(task_data: Dict[str, Any]) -> Dict[str, Any]:
    processed = dict(task_data)

    for field_name in GRIDFS_FIELDS:
        if field_name in processed:
            processed[field_name] = await _retrieve_large_field(processed[field_name])

    rd = processed.get("reconstruction_data")
    if isinstance(rd, dict):
        for f in ["reconstructed_image_base64", "reconstructed_images_base64",
                   "fused_reconstruction"]:
            if f in rd:
                rd[f] = await _retrieve_large_field(rd[f])
        processed["reconstruction_data"] = rd

    return processed


async def delete_gridfs_files(file_ids: List[str]) -> int:
    deleted = 0
    for fid in file_ids:
        try:
            if use_memory_db():
                _memory_db["gridfs_files"] = [
                    f for f in _memory_db["gridfs_files"]
                    if str(f["_id"]) != fid
                ]
                deleted += 1
            else:
                fs = await get_gridfs()
                if fs is not None:
                    await fs.delete(ObjectId(fid))
                    deleted += 1
        except Exception as e:
            print(f"[GridFS] 删除失败 {fid}: {e}")
    return deleted


