from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import close_db
from app.routers import simulation, simulation_3d, tasks, websocket_routes
from app.routers.websocket_routes import cleanup_expired_cache
import asyncio

app = FastAPI(
    title=settings.APP_NAME,
    description="基于磁感应断层成像的脑水肿监测系统",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulation.router)
app.include_router(simulation_3d.router)
app.include_router(tasks.router)
app.include_router(websocket_routes.router)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired_cache())


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "api_endpoints": [
            "POST /api/simulation/2d",
            "POST /api/simulation/multifrequency",
            "POST /api/simulation/timeseries",
            "POST /api/simulation/electrode_optimization",
            "POST /api/simulation/evaluate_quality",
            "POST /api/simulation/export_dicom",
            "POST /api/simulation/3d",
            "GET  /api/simulation/3d/{task_id}/status",
            "GET  /api/tasks",
            "GET  /api/tasks/{task_id}",
            "DELETE /api/tasks/{task_id}",
            "POST /api/tasks/{task_id}/notes",
            "GET  /api/tasks/{task_id}/notes",
            "WS   /ws/simulation/{client_id}"
        ]
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.on_event("shutdown")
async def shutdown_event():
    await close_db()
