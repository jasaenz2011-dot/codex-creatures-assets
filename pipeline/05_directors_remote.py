"""
MODULE 5: DIRECTOR'S REMOTE (Mobile-to-PC Bridge)
Role: Lightweight LAN HTTP server on the workstation. Mobile browser = controller.
      Trigger pipeline stages, monitor job status, preview renders remotely.
Input:  HTTP GET requests from any device on LAN
Output: JSON status feed + pipeline job triggers + render file listing

No app install. Open http://{PC_LAN_IP}:7777 in any mobile browser.
Do NOT expose to internet — LAN only, no auth.
"""

import json
import threading
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


# ── Job Registry ──────────────────────────────────────────
JOBS = {}
JOB_COUNTER = [0]


def run_pipeline_stage(job_id: str, asset_id: str, stage: str, blender_exe: str):
    """Execute one pipeline stage in a background thread."""
    JOBS[job_id]["status"] = "running"

    lore_path  = f"pipeline/lore/{asset_id}.json"
    blend_path = f"pipeline/assets/{asset_id}.blend"

    try:
        if stage == "lore":
            # Lore must be pre-populated via Genesis Pitch data entry
            JOBS[job_id]["output"] = lore_path

        elif stage == "asset":
            from pipeline.p02_asset_architect import AssetArchitect
            out = AssetArchitect().build(lore_path, blender_exe)
            JOBS[job_id]["output"] = out

        elif stage == "motion":
            from pipeline.p03_motion_hub import MotionHub
            out = MotionHub().animate_all(lore_path, blend_path, blender_exe)
            JOBS[job_id]["output"] = out

        elif stage == "vfx":
            from pipeline.p04_vfx_manager import VFXManager
            vfx     = VFXManager()
            blends  = list(Path("pipeline/animated").glob(f"{asset_id}_*.blend"))
            outputs = [vfx.render(lore_path, str(b), blender_exe) for b in blends]
            JOBS[job_id]["output"] = outputs

        elif stage == "full":
            for s in ["asset", "motion", "vfx"]:
                sub = f"{job_id}_{s}"
                JOBS[sub] = {"status": "running", "stage": s, "asset_id": asset_id}
                run_pipeline_stage(sub, asset_id, s, blender_exe)

        JOBS[job_id]["status"] = "done"

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"]  = str(e)


class DirectorHandler(BaseHTTPRequestHandler):
    """
    ENDPOINTS:
    GET /            → Mobile controller UI (HTML)
    GET /status      → All job statuses (JSON)
    GET /run         → Trigger stage: ?asset_id={ASSET_ID}&stage={STAGE}
    GET /renders     → List completed MP4s (JSON)
    GET /assets      → List available lore_index entries (JSON)
    """

    def log_message(self, *_): pass  # suppress stdout noise

    def send_json(self, data, code=200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/":
            self.send_html(MOBILE_UI)

        elif parsed.path == "/status":
            self.send_json({"jobs": JOBS})

        elif parsed.path == "/assets":
            index_path = Path("pipeline/lore/lore_index.json")
            if index_path.exists():
                with open(index_path) as f:
                    self.send_json(json.load(f))
            else:
                self.send_json({"error": "lore_index.json not found"}, 404)

        elif parsed.path == "/renders":
            renders = [str(r) for r in Path("pipeline/renders").glob("*.mp4")]
            self.send_json({"renders": renders})

        elif parsed.path == "/run":
            asset_id    = params.get("asset_id", ["{ASSET_ID}"])[0]
            stage       = params.get("stage", ["full"])[0]
            blender_exe = params.get("blender", ["blender"])[0]

            JOB_COUNTER[0] += 1
            job_id = f"job_{JOB_COUNTER[0]:04d}"
            JOBS[job_id] = {
                "status":     "queued",
                "stage":      stage,
                "asset_id":   asset_id,
                "start_time": time.strftime("%H:%M:%S"),
                "output":     None,
            }

            t = threading.Thread(
                target=run_pipeline_stage,
                args=(job_id, asset_id, stage, blender_exe),
                daemon=True
            )
            t.start()
            self.send_json({"job_id": job_id, "queued": stage, "asset_id": asset_id})

        else:
            self.send_json({"error": "Unknown endpoint"}, 404)


# ── Mobile Controller UI ──────────────────────────────────

MOBILE_UI = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Director's Remote</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body  { background: #0d0d0f; color: #e8e8e8; font-family: monospace; padding: 20px; }
  h1    { color: #9060ff; font-size: 16px; letter-spacing: 3px; margin-bottom: 20px; }
  label { font-size: 11px; color: #666; display: block; margin: 12px 0 4px; }
  select, input, button {
    width: 100%; padding: 12px; background: #1a1a28;
    border: 1px solid #3a3a60; color: #e8e8e8;
    font-family: monospace; font-size: 13px; border-radius: 6px;
  }
  button { background: #2a2050; cursor: pointer; margin-top: 8px; }
  button:active { background: #5040a0; }
  #log  {
    margin-top: 20px; font-size: 11px; color: #60e890;
    background: #0f0f18; padding: 12px; border-radius: 6px;
    white-space: pre; overflow: auto; min-height: 120px; max-height: 300px;
  }
</style>
</head>
<body>
<h1>DIRECTOR'S REMOTE</h1>

<label>Asset ID</label>
<input id="asset" placeholder="{ASSET_ID}" value="">

<label>Pipeline Stage</label>
<select id="stage">
  <option value="full">Full Pipeline (asset → motion → vfx)</option>
  <option value="asset">2 — Asset Architect</option>
  <option value="motion">3 — Motion Hub</option>
  <option value="vfx">4 — VFX Manager</option>
</select>

<label>Blender Executable Path</label>
<input id="blender" value="blender" placeholder="/path/to/blender">

<button onclick="runJob()">▶ RUN PIPELINE</button>
<button onclick="poll()">↻ REFRESH STATUS</button>
<button onclick="listRenders()">📁 LIST RENDERS</button>
<button onclick="loadAssets()">📋 LOAD ASSET INDEX</button>

<div id="log">Ready. Enter an Asset ID and press RUN.</div>

<script>
  const log = document.getElementById("log");
  const show = d => { log.textContent = JSON.stringify(d, null, 2); };

  async function runJob() {
    const a = document.getElementById("asset").value.trim() || "{ASSET_ID}";
    const s = document.getElementById("stage").value;
    const b = document.getElementById("blender").value.trim();
    const r = await fetch(`/run?asset_id=${a}&stage=${s}&blender=${encodeURIComponent(b)}`);
    show(await r.json());
    setTimeout(poll, 2000);
  }

  async function poll() {
    const r = await fetch("/status");
    show((await r.json()).jobs);
  }

  async function listRenders() {
    const r = await fetch("/renders");
    show(await r.json());
  }

  async function loadAssets() {
    const r = await fetch("/assets");
    const d = await r.json();
    show(d);
    // Auto-fill first asset id
    const ids = Object.keys(d);
    if (ids.length) document.getElementById("asset").value = ids[0];
  }
</script>
</body>
</html>"""


class DirectorsRemote:
    """
    SYSTEM INSTRUCTIONS:
    - LAN only. Do not bind to a public IP or add auth — not designed for that.
    - All pipeline stages run as daemon threads. Server stays responsive.
    - /assets reads lore_index.json — Module 1 must run first to populate it.
    - Mobile UI auto-fills Asset ID from index to reduce manual entry errors.

    DNA RULES:
    1. Port 7777. Change only if conflicted.
    2. No file uploads via this server — assets enter via lore JSON only.
    3. Job state is in-memory only — clears on server restart.
    4. Blender path is configurable per-request for multi-install workstations.
    """

    def __init__(self, host="0.0.0.0", port=7777):
        self.host = host
        self.port = port

    def start(self):
        server = HTTPServer((self.host, self.port), DirectorHandler)
        print(f"[DirectorsRemote] ✓ Running at http://0.0.0.0:{self.port}")
        print(f"[DirectorsRemote]   Mobile: http://{{YOUR_PC_LAN_IP}}:{self.port}")
        server.serve_forever()


# ── USAGE ─────────────────────────────────────────────────
if __name__ == "__main__":
    DirectorsRemote().start()
