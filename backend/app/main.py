from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.inference_manager import inference_manager
from app.routers import generate
from app.schemas import HealthResponse

app = FastAPI(title="Codex Creatures Inference API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        selected_device=inference_manager.device.to_schema(),
        model_id=settings.model_id,
    )
