"""
MODULE 5: DIRECTOR'S REMOTE (Mobile-to-PC Bridge)
Role: Lightweight HTTP server on the workstation. Mobile browser is the controller.
      Trigger pipeline stages, monitor render status, and preview outputs remotely.
Input:  HTTP requests from any device on LAN
Output: Pipeline triggers + JSON status feed + video preview links

No app install needed — mobile Safari/Chrome connects to http://<PC-IP>:7777
"""

import json
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess
import time


# ── In-memory job queue ───────────────────────────────────
JOBS = {}         # job_id → {status, module, character, start_time, output}
JOB_COUNTER = [0]


def run_pipeline_job(job_id: str, character: str, stage: str):
    """Execute a pipeline stage in a background thread."""
    JOBS[job_id]["status"] = "running"

    lore_path     = f"pipeline/lore/{character}.json"
    blend_path    = f"pipeline/assets/{character}.blend"
    animated_dir  = f"pipeline/animated/"

    try:
        if stage == "lore":
            from pipeline._01_lore_engine import LoreLogicEngine
            engine = LoreLogicEngine()
            JOBS[job_id]["output"] = str(engine.output_dir / f"{character}.json")

        elif stage == "asset":
            from pipeline._02_asset_architect import AssetArchitect
            arch = AssetArchitect()
            JOBS[job_id]["output"] = arch.build(lore_path)

        elif stage == "motion":
            from pipeline._03_motion_hub import MotionHub
            hub = MotionHub()
            outputs = hub.animate_all(lore_path, blend_path)
            JOBS[job_id]["output"] = outputs

        elif stage == "vfx":
            from pipeline._04_vfx_manager import VFXManager
            vfx = VFXManager()
            animated_blends = list(Path(animated_dir).glob(f"{character}_*.blend"))
            outputs = []
            for b in animated_blends:
                outputs.append(vfx.render(lore_path, str(b)))
            JOBS[job_id]["output"] = outputs

        elif stage == "full":
            # Run all stages sequentially
            for s in ["lore", "asset", "motion", "vfx"]:
                sub_job = f"{job_id}_{s}"
                JOBS[sub_job] = {"status": "running", "module": s, "character": character}
                run_pipeline_job(sub_job, character, s)

        JOBS[job_id]["status"] = "done"

    except Exception as e:
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"]  = str(e)


class DirectorHandler(BaseHTTPRequestHandler):
    """
    DNA:
    - Zero authentication (LAN only — don't expose to internet).
    - All responses are JSON or HTML — no JS framework needed.
    - Mobile UI served at GET / — works in any mobile browser.
    """

    def log_message(self, format, *args):
        pass  # suppress console noise

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

        elif parsed.path == "/run":
            character = params.get("character", ["embrix"])[0]
            stage     = params.get("stage", ["full"])[0]

            JOB_COUNTER[0] += 1
            job_id = f"job_{JOB_COUNTER[0]:04d}"
            JOBS[job_id] = {
                "status": "queued",
                "module": stage,
                "character": character,
                "start_time": time.strftime("%H:%M:%S"),
                "output": None
            }

            t = threading.Thread(target=run_pipeline_job, args=(job_id, character, stage))
            t.daemon = True
            t.start()

            self.send_json({"job_id": job_id, "message": f"Started {stage} for {character}"})

        elif parsed.path == "/renders":
            renders = list(Path("pipeline/renders").glob("*.mp4"))
            self.send_json({"renders": [str(r) for r in renders]})

        else:
            self.send_json({"error": "Unknown endpoint"}, 404)


# ── Mobile UI (served at GET /) ───────────────────────────
MOBILE_UI = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Director's Remote</title>
<style>
  body { background:#0d0d0f; color:#e8e8e8; font-family:monospace; padding:20px; }
  h1   { color:#9060ff; font-size:18px; letter-spacing:2px; }
  label { font-size:12px; color:#888; }
  select, button { width:100%; padding:12px; margin:8px 0;
    background:#1a1a28; border:1px solid #3a3a60;
    color:#e8e8e8; font-family:monospace; font-size:14px; border-radius:6px; }
  button { background:#2a2a50; cursor:pointer; }
  button:active { background:#4040a0; }
  #status { margin-top:20px; font-size:11px; color:#60e890;
    background:#0f0f18; padding:12px; border-radius:6px;
    white-space:pre; overflow:auto; min-height:100px; }
</style>
</head>
<body>
<h1>DIRECTOR'S REMOTE</h1>
<label>Character</label>
<select id="char">
  <option value="embrix">EMBRIX</option>
  <option value="leafang">LEAFANG</option>
</select>
<label>Pipeline Stage</label>
<select id="stage">
  <option value="full">Full Pipeline</option>
  <option value="lore">1 — Lore Engine</option>
  <option value="asset">2 — Asset Architect</option>
  <option value="motion">3 — Motion Hub</option>
  <option value="vfx">4 — VFX Manager</option>
</select>
<button onclick="runJob()">▶ RUN</button>
<button onclick="getStatus()">↻ REFRESH STATUS</button>
<div id="status">Ready.</div>
<script>
  async function runJob() {
    const c = document.getElementById('char').value;
    const s = document.getElementById('stage').value;
    const r = await fetch(`/run?character=${c}&stage=${s}`);
    const d = await r.json();
    document.getElementById('status').textContent = JSON.stringify(d, null, 2);
    setTimeout(getStatus, 2000);
  }
  async function getStatus() {
    const r = await fetch('/status');
    const d = await r.json();
    document.getElementById('status').textContent = JSON.stringify(d.jobs, null, 2);
  }
</script>
</body>
</html>"""


class DirectorsRemote:
    """Start the LAN server. Access from any device at http://<PC-IP>:7777"""

    def __init__(self, host="0.0.0.0", port=7777):
        self.host = host
        self.port = port

    def start(self):
        server = HTTPServer((self.host, self.port), DirectorHandler)
        print(f"[DirectorsRemote] ✓ Running at http://{self.host}:{self.port}")
        print(f"[DirectorsRemote]   Open on mobile: http://<your-PC-IP>:{self.port}")
        server.serve_forever()


if __name__ == "__main__":
    remote = DirectorsRemote()
    remote.start()
