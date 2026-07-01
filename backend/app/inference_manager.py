"""Owns hardware detection and diffusion model lifecycle.

The FastAPI routers never talk to torch/diffusers directly - they go through
`InferenceManager` so the inference strategy (direct diffusers pipeline today,
a headless ComfyUI process for video later) can change without touching the
API layer.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.schemas import DeviceInfo


@dataclass(frozen=True)
class Device:
    """A resolved compute device the manager will run models on."""

    torch_device: str  # value accepted by `torch.device(...)`, e.g. "cuda:0"
    backend: str  # "cuda" | "mps" | "cpu"
    name: str
    total_vram_mb: int | None = None
    free_vram_mb: int | None = None

    def to_schema(self) -> DeviceInfo:
        return DeviceInfo(
            name=self.name,
            backend=self.backend,
            total_vram_mb=self.total_vram_mb,
            free_vram_mb=self.free_vram_mb,
        )


def detect_best_device(override: str | None = None) -> Device:
    """Pick the GPU with the most free VRAM, falling back to Apple `mps`,
    then plain CPU. An explicit override always wins.
    """
    import torch

    if override:
        backend = override.split(":")[0]
        name = torch.cuda.get_device_name(override) if backend == "cuda" else override
        return Device(torch_device=override, backend=backend, name=name)

    if torch.cuda.is_available():
        best_index = 0
        best_free_bytes = -1
        best_total_bytes = 0
        for index in range(torch.cuda.device_count()):
            free_bytes, total_bytes = torch.cuda.mem_get_info(index)
            if free_bytes > best_free_bytes:
                best_index, best_free_bytes, best_total_bytes = index, free_bytes, total_bytes

        return Device(
            torch_device=f"cuda:{best_index}",
            backend="cuda",
            name=torch.cuda.get_device_name(best_index),
            total_vram_mb=best_total_bytes // (1024 * 1024),
            free_vram_mb=best_free_bytes // (1024 * 1024),
        )

    if torch.backends.mps.is_available():
        return Device(torch_device="mps", backend="mps", name="Apple Silicon (MPS)")

    return Device(torch_device="cpu", backend="cpu", name="CPU")


class InferenceManager:
    """Lazily loads and caches diffusion pipelines on the best available device."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._device: Device | None = None
        self._pipelines: dict[str, object] = {}

    @property
    def device(self) -> Device:
        if self._device is None:
            self._device = detect_best_device(settings.device_override)
        return self._device

    def _load_pipeline(self, model_id: str):
        import torch
        from diffusers import DiffusionPipeline

        dtype = torch.float16 if self.device.backend in ("cuda", "mps") else torch.float32
        pipeline = DiffusionPipeline.from_pretrained(model_id, torch_dtype=dtype)
        pipeline = pipeline.to(self.device.torch_device)
        return pipeline

    def get_pipeline(self, model_id: str):
        with self._lock:
            if model_id not in self._pipelines:
                self._pipelines[model_id] = self._load_pipeline(model_id)
            return self._pipelines[model_id]

    def generate_image(
        self,
        prompt: str,
        *,
        model_id: str | None = None,
        negative_prompt: str | None = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 4,
        seed: int | None = None,
    ) -> tuple[Path, int]:
        """Runs a text-to-image pipeline and writes the result to disk.

        Returns the output file path and the seed actually used, so callers
        (and the UI) can reproduce a generation later.
        """
        import torch

        resolved_model_id = model_id or settings.model_id
        pipeline = self.get_pipeline(resolved_model_id)

        if seed is None:
            seed = torch.randint(0, 2**32 - 1, (1,)).item()
        generator = torch.Generator(device=self.device.torch_device).manual_seed(seed)

        result = pipeline(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            generator=generator,
        )
        image = result.images[0]

        output_path = settings.output_dir / f"{uuid.uuid4().hex}.png"
        image.save(output_path)
        return output_path, seed


# Single shared instance used by the routers.
inference_manager = InferenceManager()
