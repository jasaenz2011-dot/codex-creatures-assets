from pydantic import BaseModel, Field


class GenerateImageRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    negative_prompt: str | None = None
    width: int = Field(default=1024, ge=64, le=2048, multiple_of=8)
    height: int = Field(default=1024, ge=64, le=2048, multiple_of=8)
    steps: int = Field(default=4, ge=1, le=100)
    seed: int | None = None


class GenerateImageResponse(BaseModel):
    file_path: str
    prompt: str
    seed: int
    device: str
    model_id: str


class DeviceInfo(BaseModel):
    name: str
    backend: str  # "cuda" | "mps" | "cpu"
    total_vram_mb: int | None = None
    free_vram_mb: int | None = None


class HealthResponse(BaseModel):
    status: str
    selected_device: DeviceInfo
    model_id: str
