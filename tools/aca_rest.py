from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from aca_os.runtime_rest import RuntimeRESTAPI


class ACARESTRequestHandler(BaseHTTPRequestHandler):
    api = RuntimeRESTAPI()

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook
        self._dispatch("POST")

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        body = self._read_body()
        response = self.api.route(method, parsed.path, query=parsed.query, body=body)
        encoded = response.to_json().encode("utf-8")
        self.send_response(response.status_code)
        for key, value in response.headers.items():
            self.send_header(key, value)
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("content-length", "0") or "0")
        return self.rfile.read(length) if length else b""


class ACARESTServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def build_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ACARESTServer((host, port), ACARESTRequestHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="ACA Runtime REST API")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind. Defaults to localhost.")
    parser.add_argument("--port", default=8765, type=int, help="Port to bind. Defaults to 8765.")
    parser.add_argument("--print-endpoints", action="store_true", help="Print endpoint catalog and exit.")
    args = parser.parse_args()

    if args.print_endpoints:
        api = RuntimeRESTAPI()
        print(json.dumps([endpoint.to_dict() for endpoint in api.endpoints], ensure_ascii=False, indent=2))
        return

    server = build_server(args.host, args.port)
    print(f"ACA REST API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
