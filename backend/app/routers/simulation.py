from fastapi import APIRouter, HTTPException
from app.models.schemas import SimulationRequest
from app.algorithms.reconstruction import (
    run_complete_simulation_2d,
    run_multifrequency_simulation
)
from app.algorithms.timeseries_monitor import simulate_temporal_edema_progression
from app.services.image_utils import matrix_to_base64, drawn_mask_to_edema_regions
from app.services.task_service import TaskRepository
from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

router = APIRouter(prefix="/api/simulation", tags=["仿真"])


class MultifrequencyRequest(BaseModel):
    grid_size: int = 16
    edema_regions: List[Dict[str, Any]] = []
    drawn_mask: Optional[List[List[int]]] = None


class TimeseriesRequest(BaseModel):
    grid_size: int = 16
    edema_regions: List[Dict[str, Any]] = []
    drawn_mask: Optional[List[List[int]]] = None
    num_scans: int = 10
    interval_seconds: int = 30
    expansion_rate: float = 0.08


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


@router.post("/multifrequency")
async def simulate_multifrequency(request: MultifrequencyRequest):
    try:
        edema_regions = list(request.edema_regions)
        if request.drawn_mask:
            drawn_regions = drawn_mask_to_edema_regions(request.drawn_mask)
            edema_regions.extend(drawn_regions)

        result = run_multifrequency_simulation(
            grid_size=request.grid_size,
            edema_regions=edema_regions
        )

        recon_images_b64 = {}
        for freq, recon in result["reconstructions"].items():
            recon_images_b64[freq] = matrix_to_base64(recon)
        fused_image_b64 = matrix_to_base64(result["fused_reconstruction"])

        task_data = {
            "task_type": "MultiFreq",
            "status": "completed",
            "edema_regions": edema_regions,
            "parameters": {
                "grid_size": request.grid_size,
                "frequencies": ["1kHz", "10kHz", "100kHz"]
            },
            "reconstructed_image_base64": fused_image_b64,
            "reconstruction_data": result,
            "clinical_notes": [],
            "created_at": datetime.now(),
            "completed_at": datetime.now()
        }
        task_id = await TaskRepository.create_task(task_data)

        return {
            "task_id": task_id,
            "grid_size": request.grid_size,
            "reconstructions": result["reconstructions"],
            "reconstructed_images_base64": recon_images_b64,
            "fused_reconstruction": result["fused_reconstruction"],
            "fused_image_base64": fused_image_b64,
            "true_conductivity_maps": result["true_conductivity_maps"],
            "cole_cole_params": result["cole_cole_params"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timeseries")
async def simulate_timeseries(request: TimeseriesRequest):
    try:
        edema_regions = list(request.edema_regions)
        if request.drawn_mask:
            drawn_regions = drawn_mask_to_edema_regions(request.drawn_mask)
            edema_regions.extend(drawn_regions)

        result = simulate_temporal_edema_progression(
            grid_size=request.grid_size,
            num_scans=request.num_scans,
            interval_seconds=request.interval_seconds,
            initial_regions=edema_regions,
            expansion_rate=request.expansion_rate
        )

        last_scan = result["scans"][-1]
        task_data = {
            "task_type": "TimeSeries",
            "status": "completed",
            "edema_regions": edema_regions,
            "parameters": {
                "grid_size": request.grid_size,
                "num_scans": request.num_scans,
                "interval_seconds": request.interval_seconds
            },
            "reconstructed_image_base64": matrix_to_base64(last_scan["fused_reconstruction"]),
            "reconstruction_data": {
                "prediction": result["prediction"],
                "times": result["times_minutes"],
                "time_series": result["time_series"],
                "last_scan_fused": last_scan["fused_reconstruction"]
            },
            "clinical_notes": [],
            "created_at": datetime.now(),
            "completed_at": datetime.now()
        }
        task_id = await TaskRepository.create_task(task_data)

        return {
            "task_id": task_id,
            "num_scans": request.num_scans,
            "interval_seconds": request.interval_seconds,
            "times_minutes": result["times_minutes"],
            "scans": result["scans"],
            "time_series": result["time_series"],
            "prediction": result["prediction"],
            "warnings": result["warnings"]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
