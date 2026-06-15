from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime
from bson import ObjectId


class EdemaRegion(BaseModel):
    center_x: int = Field(..., description="水肿区域中心X坐标")
    center_y: int = Field(..., description="水肿区域中心Y坐标")
    center_z: Optional[int] = Field(None, description="水肿区域中心Z坐标(3D)")
    radius: int = Field(..., description="水肿区域半径(像素)")
    conductivity_factor: float = Field(2.0, description="电导率变化倍数")


class SimulationRequest(BaseModel):
    grid_size: int = Field(16, description="2D仿真网格大小")
    edema_regions: List[EdemaRegion] = Field([], description="水肿区域列表")
    drawn_mask: Optional[List[List[int]]] = Field(None, description="用户绘制的水肿掩码")


class Simulation3DRequest(BaseModel):
    nx: int = Field(32, description="3D网格X维度")
    ny: int = Field(32, description="3D网格Y维度")
    nz: int = Field(16, description="3D网格Z维度")
    edema_regions: List[EdemaRegion] = Field([], description="水肿区域列表")


class ClinicalNote(BaseModel):
    doctor_name: str = Field(..., description="医生姓名")
    note: str = Field(..., description="临床注释内容")
    timestamp: datetime = Field(default_factory=datetime.now)


class SimulationTask(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    task_type: str = Field("2D", description="任务类型: 2D 或 3D")
    status: str = Field("pending", description="任务状态")
    edema_regions: List[EdemaRegion] = Field([])
    parameters: dict = Field({})
    reconstructed_image_base64: Optional[str] = Field(None)
    reconstruction_data: Optional[Any] = Field(None)
    clinical_notes: List[ClinicalNote] = Field([])
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    celery_task_id: Optional[str] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
