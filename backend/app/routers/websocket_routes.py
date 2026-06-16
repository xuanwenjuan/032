from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from typing import Dict, Any, Optional
import json
import asyncio
from datetime import datetime
from app.models.schemas import Simulation3DRequest
from app.services.task_service import TaskRepository
from app.core.config import settings
from app.algorithms.simulation_3d import reconstruct_3d_lbp
from app.services.image_utils import matrix_to_base64

router = APIRouter()

HEARTBEAT_INTERVAL = 15
HEARTBEAT_TIMEOUT = 45
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY_BASE = 2

active_connections: Dict[str, Dict[str, Any]] = {}
pending_results: Dict[str, Any] = {}
active_tasks: Dict[str, asyncio.Task] = {}


class WSConnectionManager:
    def __init__(self, websocket: WebSocket, client_id: str):
        self.ws = websocket
        self.client_id = client_id
        self.last_ping_time: Optional[float] = None
        self.last_pong_time: Optional[float] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.is_connected = False
        self.missed_pongs = 0

    async def send_json(self, data: dict) -> None:
        try:
            await self.ws.send_text(json.dumps(data))
        except Exception as e:
            print(f"[WS-{self.client_id}] 发送失败: {e}")
            raise

    async def receive_json(self) -> dict:
        try:
            data = await self.ws.receive_text()
            return json.loads(data)
        except WebSocketDisconnect:
            raise
        except Exception as e:
            print(f"[WS-{self.client_id}] 接收失败: {e}")
            raise

    async def send_heartbeat(self) -> None:
        while self.is_connected:
            try:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if not self.is_connected:
                    break
                now = datetime.now().timestamp()
                if self.last_pong_time and (now - self.last_pong_time) > HEARTBEAT_TIMEOUT:
                    self.missed_pongs += 1
                    print(f"[WS-{self.client_id}] 心跳超时 ({self.missed_pongs}/3)")
                    if self.missed_pongs >= 3:
                        print(f"[WS-{self.client_id}] 3次心跳超时，断开连接")
                        self.is_connected = False
                        break
                    continue
                self.last_ping_time = now
                self.missed_pongs = 0
                await self.send_json({
                    "type": "ping",
                    "timestamp": now,
                    "interval": HEARTBEAT_INTERVAL,
                    "timeout": HEARTBEAT_TIMEOUT
                })
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[WS-{self.client_id}] 心跳发送异常: {e}")
                self.is_connected = False
                break

    async def start_heartbeat(self) -> None:
        if self.heartbeat_task is None or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self.send_heartbeat())

    async def stop_heartbeat(self) -> None:
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None


@router.websocket("/ws/simulation/{client_id}")
async def websocket_simulation(websocket: WebSocket, client_id: str):
    manager = WSConnectionManager(websocket, client_id)
    try:
        await websocket.accept()
        manager.is_connected = True
        manager.last_pong_time = datetime.now().timestamp()

        if client_id in active_connections:
            old_mgr = active_connections[client_id]
            await old_mgr.stop_heartbeat()
            old_mgr.is_connected = False

        active_connections[client_id] = {
            "manager": manager,
            "connected_at": datetime.now(),
            "last_activity": datetime.now()
        }

        if client_id in pending_results:
            cached = pending_results.pop(client_id)
            print(f"[WS-{client_id}] 重连成功，发送缓存结果 {cached.get('type', 'unknown')}")
            await manager.send_json({
                "type": "reconnected",
                "reconnect_attempts": cached.get("reconnect_attempts", 0),
                "cached_message": cached
            })
            await manager.send_json(cached)

        await manager.start_heartbeat()

        await manager.send_json({
            "type": "welcome",
            "client_id": client_id,
            "heartbeat_interval": HEARTBEAT_INTERVAL,
            "heartbeat_timeout": HEARTBEAT_TIMEOUT,
            "max_reconnect": MAX_RECONNECT_ATTEMPTS,
            "message": "已连接到MIT仿真服务"
        })

        while manager.is_connected:
            try:
                message = await asyncio.wait_for(manager.receive_json(), timeout=HEARTBEAT_TIMEOUT)
                active_connections[client_id]["last_activity"] = datetime.now()
                msg_type = message.get("type")

                if msg_type == "start_3d_simulation":
                    asyncio.create_task(handle_3d_simulation(manager, client_id, message))

                elif msg_type == "pong":
                    manager.last_pong_time = datetime.now().timestamp()
                    manager.missed_pongs = 0

                elif msg_type == "ping":
                    await manager.send_json({
                        "type": "pong",
                        "timestamp": datetime.now().timestamp(),
                        "echo": message.get("timestamp")
                    })

                elif msg_type == "reconnect_ack":
                    print(f"[WS-{client_id}] 客户端确认重连")

            except asyncio.TimeoutError:
                print(f"[WS-{client_id}] 接收超时")
                manager.missed_pongs += 1
                if manager.missed_pongs >= 3:
                    break
                continue

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        print(f"[WS-{client_id}] 客户端断开连接")
    except Exception as e:
        print(f"[WS-{client_id}] 连接异常: {e}")
    finally:
        manager.is_connected = False
        await manager.stop_heartbeat()

        if client_id in active_tasks and not active_tasks[client_id].done():
            print(f"[WS-{client_id}] 断开时仍有运行中的任务，缓存结果")
        else:
            if client_id in active_connections:
                del active_connections[client_id]


async def handle_3d_simulation(manager: WSConnectionManager, client_id: str, message: dict):
    if client_id in active_tasks and not active_tasks[client_id].done():
        await manager.send_json({
            "type": "error",
            "message": "已有运行中的3D仿真任务"
        })
        return

    try:
        edema_regions = message.get("edema_regions", [])
        nx = message.get("nx", settings.GRID_SIZE_3D_X)
        ny = message.get("ny", settings.GRID_SIZE_3D_Y)
        nz = message.get("nz", settings.GRID_SIZE_3D_Z)
        session_token = message.get("session_token", datetime.now().isoformat())

        task_data = {
            "task_type": "3D",
            "status": "running",
            "edema_regions": edema_regions,
            "parameters": {"nx": nx, "ny": ny, "nz": nz},
            "clinical_notes": [],
            "created_at": datetime.now(),
            "completed_at": None,
            "session_token": session_token
        }
        task_id = await TaskRepository.create_task(task_data)

        await manager.send_json({
            "type": "task_created",
            "task_id": task_id,
            "status": "running",
            "session_token": session_token
        })

        async def async_progress_cb(progress: float, msg: str):
            if manager.is_connected and client_id in active_connections:
                try:
                    await manager.send_json({
                        "type": "progress",
                        "task_id": task_id,
                        "progress": progress,
                        "message": msg,
                        "session_token": session_token,
                        "timestamp": datetime.now().timestamp()
                    })
                except Exception as e:
                    print(f"[WS-{client_id}] 进度推送失败: {e}")

        def sync_progress_cb(progress: float, msg: str):
            loop = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
            try:
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(async_progress_cb(progress, msg), loop)
                else:
                    loop.run_until_complete(async_progress_cb(progress, msg))
            except Exception as e:
                print(f"[WS-{client_id}] 进度回调异常: {e}")

        def run_sync():
            return reconstruct_3d_lbp(nx, ny, nz, edema_regions, sync_progress_cb)

        result = await asyncio.to_thread(run_sync)

        recon_image_b64 = matrix_to_base64(result["mid_slice"])

        await TaskRepository.update_task(task_id, {
            "status": "completed",
            "reconstructed_image_base64": recon_image_b64,
            "reconstruction_data": result,
            "completed_at": datetime.now(),
            "session_token": session_token
        })

        complete_msg = {
            "type": "simulation_complete",
            "task_id": task_id,
            "status": "completed",
            "mid_slice": result["mid_slice"],
            "reconstructed_image_base64": recon_image_b64,
            "reconstruction_3d": result["reconstruction_3d"],
            "grid_size": result["grid_size"],
            "session_token": session_token,
            "timestamp": datetime.now().timestamp()
        }

        if manager.is_connected:
            await manager.send_json(complete_msg)
        else:
            pending_results[client_id] = {
                **complete_msg,
                "reconnect_attempts": 0,
                "expires_at": datetime.now().timestamp() + 3600
            }
            print(f"[WS-{client_id}] 客户端离线，结果已缓存，1小时后过期")

    except Exception as e:
        import traceback
        traceback.print_exc()
        error_msg = {
            "type": "error",
            "task_id": task_id if 'task_id' in locals() else None,
            "message": str(e),
            "session_token": message.get("session_token"),
            "timestamp": datetime.now().timestamp()
        }
        if manager.is_connected:
            await manager.send_json(error_msg)
        else:
            pending_results[client_id] = {
                **error_msg,
                "reconnect_attempts": 0,
                "expires_at": datetime.now().timestamp() + 3600
            }

    finally:
        if client_id in active_tasks:
            del active_tasks[client_id]


async def broadcast_message(message: dict):
    to_remove = []
    for client_id, conn_info in active_connections.items():
        try:
            manager = conn_info["manager"]
            if manager.is_connected:
                await manager.send_json(message)
            else:
                to_remove.append(client_id)
        except Exception:
            to_remove.append(client_id)
    for cid in to_remove:
        if cid in active_connections:
            del active_connections[cid]


async def cleanup_expired_cache():
    while True:
        try:
            await asyncio.sleep(300)
            now = datetime.now().timestamp()
            expired = [cid for cid, data in pending_results.items()
                       if data.get("expires_at", 0) < now]
            for cid in expired:
                print(f"[Cache] 清理过期缓存: {cid}")
                pending_results.pop(cid, None)
        except Exception as e:
            print(f"[Cache] 清理异常: {e}")
