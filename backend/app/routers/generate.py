from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.inference_manager import inference_manager
from app.schemas import GenerateImageRequest, GenerateImageResponse

router = APIRouter(prefix="/generate", tags=["generate"])


@router.post("/image", response_model=GenerateImageResponse)
async def generate_image(request: GenerateImageRequest) -> GenerateImageResponse:
    # Diffusion inference is blocking/CPU+GPU bound, so it runs off the event loop.
    file_path, seed = await run_in_threadpool(
        inference_manager.generate_image,
        request.prompt,
        negative_prompt=request.negative_prompt,
        width=request.width,
        height=request.height,
        steps=request.steps,
        seed=request.seed,
    )

    return GenerateImageResponse(
        file_path=str(file_path),
        prompt=request.prompt,
        seed=seed,
        device=inference_manager.device.torch_device,
        model_id=settings.model_id,
    )
