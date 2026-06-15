from fastapi import APIRouter, HTTPException
from app.models.schemas import SimulationRequest
from app.algorithms.reconstruction import run_complete_simulation_2d
from app.services.image_utils import matrix_to_base64, drawn_mask_to_edema_regions
from app.services.task_service import TaskRepository
from datetime import datetime

router = APIRouter(prefix="/api/simulation", tags=["仿真"])


@router.post("/2d")
async def simulate_2d(request: SimulationRequest):
    try:
        edema_regions = [r.model_dump() for r in request.edema_regions]

        if request.drawn_mask:
            drawn_regions = drawn_mask_to_edema_regions(request.drawn_mask)
            edema_regions.extend(drawn_regions)

        result = run_complete_simulation_2d(
            grid_size=request.grid_size,
            edema_regions=edema_regions
        )

        recon_image_b64 = matrix_to_base64(result["reconstructed_conductivity"])
        true_image_b64 = matrix_to_base64(result["true_conductivity"])

        task_data = {
            "task_type": "2D",
            "status": "completed",
            "edema_regions": edema_regions,
            "parameters": {
                "grid_size": request.grid_size
            },
            "reconstructed_image_base64": recon_image_b64,
            "reconstruction_data": result,
            "clinical_notes": [],
            "created_at": datetime.now(),
            "completed_at": datetime.now()
        }
        task_id = await TaskRepository.create_task(task_data)

        return {
            "task_id": task_id,
            "reconstructed_conductivity": result["reconstructed_conductivity"],
            "true_conductivity": result["true_conductivity"],
            "reconstructed_image_base64": recon_image_b64,
            "true_image_base64": true_image_b64,
            "grid_size": request.grid_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
