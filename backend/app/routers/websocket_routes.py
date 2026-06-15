from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict
import json
from datetime import datetime
from app.models.schemas import Simulation3DRequest
from app.services.task_service import TaskRepository
from app.core.config import settings
from app.algorithms.simulation_3d import reconstruct_3d_lbp
from app.services.image_utils import matrix_to_base64

router = APIRouter()

active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/simulation/{client_id}")
async def websocket_simulation(websocket: WebSocket, client_id: str):
    await websocket.accept()
    active_connections[client_id] = websocket
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "start_3d_simulation":
                await handle_3d_simulation(websocket, client_id, message)
            elif msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        if client_id in active_connections:
            del active_connections[client_id]
    except Exception as e:
        if client_id in active_connections:
            del active_connections[client_id]


async def handle_3d_simulation(websocket: WebSocket, client_id: str, message: dict):
    try:
        edema_regions = message.get("edema_regions", [])
        nx = message.get("nx", settings.GRID_SIZE_3D_X)
        ny = message.get("ny", settings.GRID_SIZE_3D_Y)
        nz = message.get("nz", settings.GRID_SIZE_3D_Z)

        task_data = {
            "task_type": "3D",
            "status": "running",
            "edema_regions": edema_regions,
            "parameters": {"nx": nx, "ny": ny, "nz": nz},
            "clinical_notes": [],
            "created_at": datetime.now(),
            "completed_at": None
        }
        task_id = await TaskRepository.create_task(task_data)

        await websocket.send_text(json.dumps({
            "type": "task_created",
            "task_id": task_id,
            "status": "running"
        }))

        def progress_cb(progress, msg):
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    websocket.send_text(json.dumps({
                        "type": "progress",
                        "task_id": task_id,
                        "progress": progress,
                        "message": msg
                    }))
                )
            finally:
                loop.close()

        result = reconstruct_3d_lbp(nx, ny, nz, edema_regions, progress_cb)

        recon_image_b64 = matrix_to_base64(result["mid_slice"])

        await TaskRepository.update_task(task_id, {
            "status": "completed",
            "reconstructed_image_base64": recon_image_b64,
            "reconstruction_data": result,
            "completed_at": datetime.now()
        })

        await websocket.send_text(json.dumps({
            "type": "simulation_complete",
            "task_id": task_id,
            "status": "completed",
            "mid_slice": result["mid_slice"],
            "reconstructed_image_base64": recon_image_b64,
            "reconstruction_3d": result["reconstruction_3d"],
            "grid_size": result["grid_size"]
        }))

    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))


async def broadcast_message(message: dict):
    for conn in active_connections.values():
        try:
            await conn.send_text(json.dumps(message))
        except:
            pass
