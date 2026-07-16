from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
KERNEL_PATH = ROOT / "kernel"

for path in [ROOT, KERNEL_PATH]:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from aca_os.runtime_rest import RuntimeRESTAPI
from aca_os.llm_verbalization import warmup_default_llm_provider
from aca_os.web_runtime_launcher import build_local_web_runtime_plan, render_launch_banner


DEFAULT_STUDIO_FILE = ROOT / "studio" / "index.html"
DEFAULT_HOST = os.environ.get("ACA_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT") or os.environ.get("ACA_PORT") or "8765")


class ACAWebRuntimeRequestHandler(BaseHTTPRequestHandler):
    """Local web adapter for Studio + Runtime REST.

    Static Studio serving stays here. Runtime behavior is delegated to
    RuntimeRESTAPI, keeping the web layer as I/O only.
    """

    api = RuntimeRESTAPI()
    studio_file = DEFAULT_STUDIO_FILE

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/studio", "/studio/"}:
            self._serve_studio()
            return
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook
        self._dispatch("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib hook
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _serve_studio(self) -> None:
        try:
            content = self.studio_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._send_json(404, {"error": {"code": "studio_not_found", "message": str(self.studio_file)}})
            return

        encoded = content.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "text/html; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self._send_cors_headers()
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        body = self._read_body()
        response = self.api.route(method, parsed.path, query=parsed.query, body=body)
        self._send_json(response.status_code, response.payload, headers=response.headers)

    def _send_json(self, status_code: int, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status_code)
        for key, value in (headers or {"content-type": "application/json; charset=utf-8"}).items():
            self.send_header(key, value)
        self._send_cors_headers()
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_cors_headers(self) -> None:
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "GET, POST, OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("content-length", "0") or "0")
        return self.rfile.read(length) if length else b""


class ACAWebRuntimeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def build_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    studio_file: str | Path = DEFAULT_STUDIO_FILE,
) -> ThreadingHTTPServer:
    handler = type(
        "ConfiguredACAWebRuntimeRequestHandler",
        (ACAWebRuntimeRequestHandler,),
        {"studio_file": Path(studio_file)},
    )
    return ACAWebRuntimeServer((host, port), handler)


def serve(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    studio_file: str | Path = DEFAULT_STUDIO_FILE,
    open_browser: bool = False,
) -> None:
    plan = build_local_web_runtime_plan(host=host, port=port, studio_path=studio_file, open_browser=open_browser)
    warmup_event = warmup_default_llm_provider()
    if warmup_event["warmup_requested"]:
        print(json.dumps({"technical_event": warmup_event}, ensure_ascii=False), flush=True)
    server = build_server(host, port, studio_file=studio_file)
    print(render_launch_banner(plan), flush=True)
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(plan.config.studio_url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="ACA Local Web Runtime")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Host to bind. Defaults to ACA_HOST or localhost.")
    parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="Port to bind. Defaults to PORT, ACA_PORT or 8765.")
    parser.add_argument("--studio-file", default=str(DEFAULT_STUDIO_FILE), help="Studio HTML file to serve.")
    parser.add_argument("--open", action="store_true", help="Open Studio in the default browser.")
    parser.add_argument("--print-plan", action="store_true", help="Print launch plan and exit.")
    args = parser.parse_args()

    if args.print_plan:
        plan = build_local_web_runtime_plan(
            host=args.host,
            port=args.port,
            studio_path=args.studio_file,
            open_browser=args.open,
        )
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
        return

    serve(host=args.host, port=args.port, studio_file=args.studio_file, open_browser=args.open)


if __name__ == "__main__":
    main()
