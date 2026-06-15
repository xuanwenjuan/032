import asyncio
from datetime import datetime
from app.workers.celery_app import celery_app
from app.algorithms.simulation_3d import reconstruct_3d_lbp
from app.services.image_utils import matrix_to_base64
from app.services.task_service import TaskRepository
from app.core.database import get_db, close_db


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, name="run_3d_simulation")
def run_3d_simulation_task(self, task_id: str, edema_regions: list, nx: int, ny: int, nz: int):
    try:
        def progress_callback(progress, msg):
            self.update_state(
                state="PROGRESS",
                meta={"progress": progress, "message": msg}
            )

        result = reconstruct_3d_lbp(nx, ny, nz, edema_regions, progress_callback)
        recon_b64 = matrix_to_base64(result["mid_slice"])

        run_async(TaskRepository.update_task(task_id, {
            "status": "completed",
            "reconstructed_image_base64": recon_b64,
            "reconstruction_data": result,
            "completed_at": datetime.now()
        }))

        return {
            "task_id": task_id,
            "status": "completed",
            "mid_slice": result["mid_slice"],
            "reconstructed_image_base64": recon_b64
        }

    except Exception as e:
        run_async(TaskRepository.update_task(task_id, {
            "status": "failed",
            "completed_at": datetime.now()
        }))
        raise e
