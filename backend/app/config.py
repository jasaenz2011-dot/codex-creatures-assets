from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the inference backend.

    Every value can be overridden via an environment variable prefixed with
    ``CODEX_`` (e.g. ``CODEX_MODEL_ID``), or via a local ``.env`` file.
    """

    model_config = SettingsConfigDict(env_prefix="CODEX_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000

    # Default text-to-image model used by the direct-diffusers pipeline.
    model_id: str = "black-forest-labs/FLUX.1-schnell"

    # Where generated assets are written. Relative to the backend package dir.
    output_dir: Path = Path(__file__).resolve().parent.parent / "outputs"

    # Force a specific device ("cuda", "cuda:1", "mps", "cpu"). Leave unset to
    # let InferenceManager auto-detect the best available device.
    device_override: str | None = None

    # Origins allowed to call the API (the Tauri dev server + packaged app).
    allowed_origins: list[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
    ]


settings = Settings()
settings.output_dir.mkdir(parents=True, exist_ok=True)
