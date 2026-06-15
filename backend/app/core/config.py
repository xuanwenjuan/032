from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    APP_NAME: str = "MIT脑水肿监测系统"
    DEBUG: bool = True

    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "mit_monitor"

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    GRID_SIZE_2D: int = 16
    GRID_SIZE_3D_X: int = 32
    GRID_SIZE_3D_Y: int = 32
    GRID_SIZE_3D_Z: int = 16

    class Config:
        env_file = ".env"


settings = Settings()
