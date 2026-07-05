from urllib.request import urlopen
import threading

from aca_os.runtime_api_endpoints import RuntimeEndpointAPI
from aca_os.runtime_rest import RuntimeRESTAPI
from tools.aca_web import build_server


def test_runtime_api_and_rest_expose_public_demo_usability():
    api = RuntimeEndpointAPI()
    rest = RuntimeRESTAPI()

    paths = {endpoint["path"] for endpoint in api.catalog()["endpoints"]}
    assert "/public-demo/usability" in paths
    assert rest.route("GET", "/public-demo/usability").status_code == 200


def test_public_studio_shell_uses_human_runtime_reading_and_modal_thought():
    html = open("studio/index.html", encoding="utf-8").read()

    assert "Lectura humana del runtime" in html
    assert "Ver pensamiento" in html
    assert "thoughtModal" in html
    assert "✕" in html


def test_web_runtime_serves_usability_shell_and_endpoint():
    server = build_server("127.0.0.1", 0)
    host, port = server.server_address
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        with urlopen(f"http://{host}:{port}/studio", timeout=5) as response:
            studio_html = response.read().decode("utf-8")
        with urlopen(f"http://{host}:{port}/public-demo/usability", timeout=5) as response:
            payload = response.read().decode("utf-8")

        assert "Lectura humana del runtime" in studio_html
        assert "public_demo_usability.v1" in payload
    finally:
        server.shutdown()
        server.server_close()
