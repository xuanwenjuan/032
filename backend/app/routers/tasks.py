from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.schemas import ClinicalNote
from app.services.task_service import TaskRepository

router = APIRouter(prefix="/api/tasks", tags=["任务"])


@router.get("")
async def list_tasks(limit: int = Query(50, ge=1, le=200)):
    tasks = await TaskRepository.list_tasks(limit)
    return {"tasks": tasks}


@router.get("/{task_id}")
async def get_task(task_id: str):
    task = await TaskRepository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: str):
    success = await TaskRepository.delete_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"success": True}


@router.post("/{task_id}/notes")
async def add_clinical_note(task_id: str, note: ClinicalNote):
    task = await TaskRepository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    success = await TaskRepository.add_clinical_note(
        task_id,
        note.model_dump()
    )
    if not success:
        raise HTTPException(status_code=500, detail="添加注释失败")
    return {"success": True}


@router.get("/{task_id}/notes")
async def get_clinical_notes(task_id: str):
    task = await TaskRepository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"notes": task.get("clinical_notes", [])}
