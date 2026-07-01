# Codex Creatures Assets

A local-first desktop app for generating creature assets with local AI models,
hidden behind a clean UI instead of a raw node graph.

## Architecture

- **Frontend (`apps/desktop`)** — Tauri 2 + React + TypeScript. Talks to the
  backend only through the REST API in `apps/desktop/src/api/client.ts`. It
  never touches inference code directly.
- **Backend (`backend`)** — Python + FastAPI. Owns model loading and
  inference. Runs as a separate local process (`127.0.0.1:8000` by default)
  so it can be developed, tested, and swapped out independently of the UI.
- **Vendor (`vendor`)** — reserved for the embedded/headless ComfyUI instance
  used for complex video workflows (added as a submodule or vendored copy
  later; not required for direct-diffusers image generation).

```
codex-creatures-assets/
├── apps/
│   └── desktop/          # Tauri frontend
│       ├── src/           # React/TS UI
│       └── src-tauri/     # Rust shell (window, packaging)
├── backend/               # Python/FastAPI inference service
│   ├── app/
│   │   ├── main.py            # FastAPI app + CORS + routers
│   │   ├── config.py          # Settings (model id, output dir, host/port)
│   │   ├── schemas.py         # Pydantic request/response models
│   │   ├── inference_manager.py  # GPU/VRAM detection + pipeline cache
│   │   └── routers/
│   │       └── generate.py    # POST /generate/image
│   ├── requirements.txt
│   └── scripts/setup_env.sh   # creates an isolated, portable venv
└── vendor/                # future home for the headless ComfyUI vendor/submodule
```

## Getting started

### Backend

```bash
cd backend
./scripts/setup_env.sh        # creates backend/.venv and installs requirements
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The first request that triggers generation will lazily download and load the
configured diffusion model (default: `black-forest-labs/FLUX.1-schnell`).
Set `CODEX_MODEL_ID` in the environment to point at a different model.

### Frontend

```bash
cd apps/desktop
npm install
npm run tauri dev
```

On Linux, Tauri also needs the system WebKitGTK/GTK dev packages installed
(see the [Tauri Linux prerequisites](https://v2.tauri.app/start/prerequisites/)),
e.g. on Debian/Ubuntu: `libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev
libayatana-appindicator3-dev libsoup-3.0-dev`.

The dev UI expects the backend to already be running on `http://127.0.0.1:8000`.

## Design notes

- Inference logic is fully decoupled from the UI: the frontend only knows
  about the REST API, never about diffusers/ComfyUI/model internals.
- `inference_manager.py` picks the best available device (CUDA GPU with the
  most free VRAM, then Apple `mps`, then CPU) and caches loaded pipelines so
  repeated generations don't reload weights.
- The FastAPI backend is intentionally the only place that knows how to talk
  to ComfyUI (once vendored) or diffusers — the UI layer stays simple.
