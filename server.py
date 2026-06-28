#!/usr/bin/env python3
"""Local dev server for Codex Creatures assets — runs on http://127.0.0.1:8765/"""

import http.server
import os
import sys
import json
import mimetypes
import urllib.parse
from pathlib import Path

PORT = 8765
HOST = "127.0.0.1"
ROOT = Path(__file__).parent.resolve()

IGNORED = {".git", "__pycache__", ".DS_Store"}

STYLE = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0f1117; color: #e2e8f0; font-family: 'Segoe UI', system-ui, sans-serif; padding: 2rem; }
  h1 { font-size: 1.75rem; font-weight: 700; color: #a78bfa; margin-bottom: 0.25rem; }
  .subtitle { color: #64748b; font-size: 0.9rem; margin-bottom: 2rem; }
  .breadcrumb { font-size: 0.85rem; color: #64748b; margin-bottom: 1rem; }
  .breadcrumb a { color: #7c3aed; text-decoration: none; }
  .breadcrumb a:hover { text-decoration: underline; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; padding: 0.5rem 1rem; border-bottom: 1px solid #1e293b;
       color: #64748b; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
  td { padding: 0.6rem 1rem; border-bottom: 1px solid #1e293b; font-size: 0.9rem; }
  tr:hover td { background: #1e293b; }
  .icon { width: 1.25rem; display: inline-block; }
  a { color: #c4b5fd; text-decoration: none; }
  a:hover { color: #a78bfa; text-decoration: underline; }
  .size { color: #64748b; text-align: right; font-variant-numeric: tabular-nums; }
  .badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px;
           font-size: 0.7rem; font-weight: 600; text-transform: uppercase; }
  .badge-dir  { background: #1e3a5f; color: #7dd3fc; }
  .badge-html { background: #3b1f6e; color: #c4b5fd; }
  .badge-py   { background: #1a3a1a; color: #86efac; }
  .badge-json { background: #3a2a0a; color: #fcd34d; }
  .badge-img  { background: #3a1a1a; color: #fca5a5; }
  .badge-audio{ background: #1a1a3a; color: #93c5fd; }
  .badge-file { background: #1e293b; color: #94a3b8; }
</style>
"""


def badge(name: str, is_dir: bool) -> str:
    if is_dir:
        return '<span class="badge badge-dir">dir</span>'
    ext = Path(name).suffix.lower()
    cls = {
        ".html": "badge-html", ".htm": "badge-html",
        ".py": "badge-py",
        ".json": "badge-json",
        ".png": "badge-img", ".jpg": "badge-img", ".jpeg": "badge-img",
        ".gif": "badge-img", ".svg": "badge-img", ".webp": "badge-img",
        ".mp3": "badge-audio", ".wav": "badge-audio", ".ogg": "badge-audio",
    }.get(ext, "badge-file")
    return f'<span class="badge {cls}">{ext[1:] if ext else "file"}</span>'


def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def build_index(url_path: str, fs_path: Path) -> bytes:
    # Breadcrumbs
    parts = [p for p in url_path.strip("/").split("/") if p]
    crumbs = ['<a href="/">/</a>']
    for i, part in enumerate(parts):
        href = "/" + "/".join(parts[: i + 1]) + "/"
        crumbs.append(f'<a href="{href}">{part}</a>')
    breadcrumb = " / ".join(crumbs)

    rows = []
    if url_path != "/":
        rows.append(
            '<tr><td><span class="icon">↑</span>'
            f'<a href="../">.. (parent)</a></td>'
            '<td></td><td class="size">—</td></tr>'
        )

    entries = sorted(fs_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for entry in entries:
        if entry.name in IGNORED or entry.name.startswith("."):
            continue
        is_dir = entry.is_dir()
        href = urllib.parse.quote(entry.name) + ("/" if is_dir else "")
        icon = "📁" if is_dir else "📄"
        size = "—" if is_dir else fmt_size(entry.stat().st_size)
        rows.append(
            f'<tr><td><span class="icon">{icon}</span>'
            f'<a href="{href}">{entry.name}</a>&nbsp;&nbsp;{badge(entry.name, is_dir)}</td>'
            f'<td></td><td class="size">{size}</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex Creatures — {url_path}</title>
  {STYLE}
</head>
<body>
  <h1>🐉 Codex Creatures Assets</h1>
  <p class="subtitle">Local dev server &mdash; <code>http://{HOST}:{PORT}</code></p>
  <p class="breadcrumb">{breadcrumb}</p>
  <table>
    <thead><tr><th>Name</th><th></th><th>Size</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</body>
</html>"""
    return html.encode()


class AssetsHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_cors()
        self.end_headers()

    def do_HEAD(self):
        self.do_GET(head_only=True)

    def do_GET(self, head_only=False):
        raw_path = urllib.parse.urlparse(self.path).path
        url_path = urllib.parse.unquote(raw_path)

        # API: list files as JSON
        if url_path == "/_api/files":
            self._api_files(head_only)
            return

        fs_path = (ROOT / url_path.lstrip("/")).resolve()

        # Security: stay inside ROOT
        try:
            fs_path.relative_to(ROOT)
        except ValueError:
            self.send_error(403, "Forbidden")
            return

        if fs_path.is_dir():
            # Redirect /foo to /foo/ for relative links to work
            if not url_path.endswith("/"):
                self.send_response(301)
                self.send_header("Location", raw_path + "/")
                self.end_headers()
                return
            body = build_index(url_path, fs_path)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_cors()
            self.end_headers()
            if not head_only:
                self.wfile.write(body)
            return

        if not fs_path.exists():
            self.send_error(404, "Not Found")
            return

        mime, _ = mimetypes.guess_type(str(fs_path))
        mime = mime or "application/octet-stream"
        data = fs_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_cors()
        self.end_headers()
        if not head_only:
            self.wfile.write(data)

    def _api_files(self, head_only):
        def walk(p: Path, base: str):
            result = []
            for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name)):
                if entry.name in IGNORED or entry.name.startswith("."):
                    continue
                rel = base + "/" + entry.name if base else entry.name
                if entry.is_dir():
                    result.append({"name": entry.name, "path": rel, "type": "dir", "children": walk(entry, rel)})
                else:
                    result.append({"name": entry.name, "path": rel, "type": "file", "size": entry.stat().st_size})
            return result

        payload = json.dumps(walk(ROOT, ""), indent=2).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_cors()
        self.end_headers()
        if not head_only:
            self.wfile.write(payload)


def main():
    mimetypes.add_type("application/javascript", ".js")
    mimetypes.add_type("text/css", ".css")
    mimetypes.add_type("image/webp", ".webp")

    server = http.server.HTTPServer((HOST, PORT), AssetsHandler)
    print(f"🐉 Codex Creatures Assets — dev server")
    print(f"   http://{HOST}:{PORT}/")
    print(f"   Serving: {ROOT}")
    print(f"   Press Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
