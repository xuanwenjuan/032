from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from app.core.database import (
    get_db,
    use_memory_db,
    _memory_db,
    process_large_fields_for_store,
    process_large_fields_for_retrieve,
    delete_gridfs_files
)


class TaskRepository:
    @staticmethod
    def _serialize_doc(doc: dict) -> dict:
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
        if "gridfs_file_ids" in doc:
            doc["gridfs_file_ids"] = [str(fid) for fid in doc["gridfs_file_ids"]]
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        if "completed_at" in doc and doc["completed_at"] and isinstance(doc["completed_at"], datetime):
            doc["completed_at"] = doc["completed_at"].isoformat()
        for note in doc.get("clinical_notes", []):
            if "timestamp" in note and isinstance(note["timestamp"], datetime):
                note["timestamp"] = note["timestamp"].isoformat()
        return doc

    @staticmethod
    async def create_task(task_data: Dict[str, Any]) -> str:
        if use_memory_db():
            new_id = str(ObjectId())
            task_data["_id"] = ObjectId(new_id)
            processed, stored_ids = await process_large_fields_for_store(
                task_data, new_id, {"storage_mode": "memory"}
            )
            if stored_ids:
                processed["gridfs_file_ids"] = [ObjectId(fid) for fid in stored_ids]
            _memory_db["simulation_tasks"].insert(0, dict(processed))
            return new_id

        new_id = str(ObjectId())
        processed, stored_ids = await process_large_fields_for_store(
            task_data, new_id, {"storage_mode": "gridfs"}
        )
        if stored_ids:
            processed["gridfs_file_ids"] = [ObjectId(fid) for fid in stored_ids]

        db = await get_db()
        processed["_id"] = ObjectId(new_id)
        await db.simulation_tasks.insert_one(processed)
        return new_id

    @staticmethod
    async def get_task(task_id: str) -> Optional[dict]:
        if use_memory_db():
            for t in _memory_db["simulation_tasks"]:
                if str(t["_id"]) == task_id:
                    doc = TaskRepository._serialize_doc(dict(t))
                    return await process_large_fields_for_retrieve(doc)
            return None

        db = await get_db()
        doc = await db.simulation_tasks.find_one({"_id": ObjectId(task_id)})
        if doc is None:
            return None
        doc = TaskRepository._serialize_doc(doc)
        return await process_large_fields_for_retrieve(doc)

    @staticmethod
    async def list_tasks(limit: int = 50) -> List[dict]:
        if use_memory_db():
            tasks = []
            for t in _memory_db["simulation_tasks"][:limit]:
                doc = TaskRepository._serialize_doc(dict(t))
                tasks.append(await process_large_fields_for_retrieve(doc))
            return tasks

        db = await get_db()
        cursor = db.simulation_tasks.find().sort("created_at", -1).limit(limit)
        tasks = []
        async for doc in cursor:
            doc = TaskRepository._serialize_doc(doc)
            tasks.append(await process_large_fields_for_retrieve(doc))
        return tasks

    @staticmethod
    async def update_task(task_id: str, update_data: Dict[str, Any]) -> bool:
        if "completed_at" in update_data and update_data["completed_at"] is None:
            update_data["completed_at"] = datetime.now()

        if use_memory_db():
            for i, t in enumerate(_memory_db["simulation_tasks"]):
                if str(t["_id"]) == task_id:
                    processed, stored_ids = await process_large_fields_for_store(
                        update_data, task_id, {"storage_mode": "memory"}
                    )
                    if stored_ids:
                        old_ids = _memory_db["simulation_tasks"][i].get("gridfs_file_ids", [])
                        all_ids = list(old_ids) + [ObjectId(fid) for fid in stored_ids]
                        processed["gridfs_file_ids"] = all_ids
                    _memory_db["simulation_tasks"][i].update(processed)
                    return True
            return False

        db = await get_db()
        existing = await db.simulation_tasks.find_one({"_id": ObjectId(task_id)})
        old_file_ids = []
        if existing and "gridfs_file_ids" in existing:
            old_file_ids = [str(fid) for fid in existing["gridfs_file_ids"]]

        processed, stored_ids = await process_large_fields_for_store(
            update_data, task_id, {"storage_mode": "gridfs"}
        )
        if stored_ids:
            all_ids = [ObjectId(fid) for fid in old_file_ids] + [ObjectId(fid) for fid in stored_ids]
            processed["gridfs_file_ids"] = all_ids

        result = await db.simulation_tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": processed}
        )
        return result.modified_count > 0

    @staticmethod
    async def add_clinical_note(task_id: str, note_data: Dict[str, Any]) -> bool:
        note_data["timestamp"] = datetime.now()

        if use_memory_db():
            for i, t in enumerate(_memory_db["simulation_tasks"]):
                if str(t["_id"]) == task_id:
                    if "clinical_notes" not in _memory_db["simulation_tasks"][i]:
                        _memory_db["simulation_tasks"][i]["clinical_notes"] = []
                    _memory_db["simulation_tasks"][i]["clinical_notes"].append(note_data)
                    return True
            return False

        db = await get_db()
        result = await db.simulation_tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$push": {"clinical_notes": note_data}}
        )
        return result.modified_count > 0

    @staticmethod
    async def delete_task(task_id: str) -> bool:
        file_ids_to_delete = []

        if use_memory_db():
            for i, t in enumerate(_memory_db["simulation_tasks"]):
                if str(t["_id"]) == task_id:
                    file_ids_to_delete = [
                        str(fid) for fid in t.get("gridfs_file_ids", [])
                    ]
                    del _memory_db["simulation_tasks"][i]
                    if file_ids_to_delete:
                        await delete_gridfs_files(file_ids_to_delete)
                    return True
            return False

        db = await get_db()
        existing = await db.simulation_tasks.find_one({"_id": ObjectId(task_id)})
        if existing and "gridfs_file_ids" in existing:
            file_ids_to_delete = [str(fid) for fid in existing["gridfs_file_ids"]]

        result = await db.simulation_tasks.delete_one({"_id": ObjectId(task_id)})

        if result.deleted_count > 0 and file_ids_to_delete:
            await delete_gridfs_files(file_ids_to_delete)

        return result.deleted_count > 0
