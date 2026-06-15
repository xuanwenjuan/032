from fastapi import APIRouter, HTTPException, BackgroundTasks
from app.models.schemas import Simulation3DRequest
from app.services.task_service import TaskRepository
from app.core.config import settings
from datetime import datetime

router = APIRouter(prefix="/api/simulation", tags=["3D仿真"])

try:
    from app.workers.celery_app import celery_app
    from app.workers.tasks import run_3d_simulation_task
    CELERY_AVAILABLE = True
except Exception:
    CELERY_AVAILABLE = False


@router.post("/3d")
async def simulate_3d(request: Simulation3DRequest, background_tasks: BackgroundTasks):
    try:
        edema_regions = [r.model_dump() for r in request.edema_regions]

        task_data = {
            "task_type": "3D",
            "status": "queued",
            "edema_regions": edema_regions,
            "parameters": {"nx": request.nx, "ny": request.ny, "nz": request.nz},
            "clinical_notes": [],
            "created_at": datetime.now(),
            "completed_at": None
        }
        task_id = await TaskRepository.create_task(task_data)

        if CELERY_AVAILABLE:
            celery_task = run_3d_simulation_task.delay(task_id, edema_regions, request.nx, request.ny, request.nz)
            await TaskRepository.update_task(task_id, {
                "status": "running",
                "celery_task_id": celery_task.id
            })
        else:
            from app.algorithms.simulation_3d import reconstruct_3d_lbp
            from app.services.image_utils import matrix_to_base64

            await TaskRepository.update_task(task_id, {"status": "running"})
            result = reconstruct_3d_lbp(request.nx, request.ny, request.nz, edema_regions)
            recon_b64 = matrix_to_base64(result["mid_slice"])
            await TaskRepository.update_task(task_id, {
                "status": "completed",
                "reconstructed_image_base64": recon_b64,
                "reconstruction_data": result
            })

        return {
            "task_id": task_id,
            "status": "queued" if CELERY_AVAILABLE else "running",
            "message": "3D仿真任务已提交，请通过WebSocket或任务查询接口获取结果"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/3d/{task_id}/status")
async def get_3d_simulation_status(task_id: str):
    task = await TaskRepository.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task_id,
        "status": task.get("status"),
        "reconstructed_image_base64": task.get("reconstructed_image_base64"),
        "reconstruction_data": task.get("reconstruction_data")
    }
