from datetime import datetime
from typing import List, Optional, Dict, Any
from bson import ObjectId
from app.core.database import get_db, use_memory_db, _memory_db


class TaskRepository:
    @staticmethod
    def _serialize_doc(doc: dict) -> dict:
        if doc is None:
            return None
        doc["_id"] = str(doc["_id"])
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
            _memory_db["simulation_tasks"].insert(0, dict(task_data))
            return new_id

        db = await get_db()
        result = await db.simulation_tasks.insert_one(task_data)
        return str(result.inserted_id)

    @staticmethod
    async def get_task(task_id: str) -> Optional[dict]:
        if use_memory_db():
            for t in _memory_db["simulation_tasks"]:
                if str(t["_id"]) == task_id:
                    return TaskRepository._serialize_doc(dict(t))
            return None

        db = await get_db()
        doc = await db.simulation_tasks.find_one({"_id": ObjectId(task_id)})
        return TaskRepository._serialize_doc(doc)

    @staticmethod
    async def list_tasks(limit: int = 50) -> List[dict]:
        if use_memory_db():
            tasks = []
            for t in _memory_db["simulation_tasks"][:limit]:
                tasks.append(TaskRepository._serialize_doc(dict(t)))
            return tasks

        db = await get_db()
        cursor = db.simulation_tasks.find().sort("created_at", -1).limit(limit)
        tasks = []
        async for doc in cursor:
            tasks.append(TaskRepository._serialize_doc(doc))
        return tasks

    @staticmethod
    async def update_task(task_id: str, update_data: Dict[str, Any]) -> bool:
        if "completed_at" in update_data and update_data["completed_at"] is None:
            update_data["completed_at"] = datetime.now()

        if use_memory_db():
            for i, t in enumerate(_memory_db["simulation_tasks"]):
                if str(t["_id"]) == task_id:
                    _memory_db["simulation_tasks"][i].update(update_data)
                    return True
            return False

        db = await get_db()
        result = await db.simulation_tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": update_data}
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
        if use_memory_db():
            for i, t in enumerate(_memory_db["simulation_tasks"]):
                if str(t["_id"]) == task_id:
                    del _memory_db["simulation_tasks"][i]
                    return True
            return False

        db = await get_db()
        result = await db.simulation_tasks.delete_one({"_id": ObjectId(task_id)})
        return result.deleted_count > 0
