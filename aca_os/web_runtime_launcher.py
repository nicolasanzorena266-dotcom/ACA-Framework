from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_STUDIO_PATH = Path("studio/index.html")


@dataclass(frozen=True)
class LocalWebRuntimeConfig:
    """Configuration for the local ACA Web Runtime launcher.

    The launcher is an interface boundary only: it describes how to expose the
    existing Runtime REST API and Studio shell locally. Runtime behavior stays in
    Runtime/API services.
    """

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    studio_path: Path = DEFAULT_STUDIO_PATH
    open_browser: bool = False

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def studio_url(self) -> str:
        return f"{self.base_url}/studio"

    @property
    def health_url(self) -> str:
        return f"{self.base_url}/health"

    @property
    def api_base_url(self) -> str:
        return self.base_url

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "base_url": self.base_url,
            "studio_url": self.studio_url,
            "health_url": self.health_url,
            "api_base_url": self.api_base_url,
            "studio_path": str(self.studio_path),
            "open_browser": self.open_browser,
        }


@dataclass(frozen=True)
class LocalWebRuntimePlan:
    """Stable launch plan consumed by CLI/server adapters."""

    contract: str
    config: LocalWebRuntimeConfig
    endpoints: Dict[str, str]
    commands: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract": self.contract,
            "config": self.config.to_dict(),
            "endpoints": dict(self.endpoints),
            "commands": dict(self.commands),
        }


def build_local_web_runtime_plan(
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    studio_path: str | Path = DEFAULT_STUDIO_PATH,
    open_browser: bool = False,
) -> LocalWebRuntimePlan:
    if not host:
        raise ValueError("host is required.")
    if int(port) <= 0 or int(port) > 65535:
        raise ValueError("port must be between 1 and 65535.")

    config = LocalWebRuntimeConfig(
        host=host,
        port=int(port),
        studio_path=Path(studio_path),
        open_browser=bool(open_browser),
    )
    return LocalWebRuntimePlan(
        contract="local_web_runtime_launcher.v1",
        config=config,
        endpoints={
            "studio": config.studio_url,
            "health": config.health_url,
            "runtime_status": f"{config.base_url}/runtime/status",
            "studio_state": f"{config.base_url}/studio/state",
            "studio_run": f"{config.base_url}/studio/run",
            "domain_packs": f"{config.base_url}/runtime/domain-packs",
        },
        commands={
            "start": f"python tools/aca_web.py --host {host} --port {int(port)}",
            "health_check": f"python -c \"import urllib.request; print(urllib.request.urlopen('{config.health_url}').read().decode())\"",
            "stop": "Ctrl+C",
        },
    )


def render_launch_banner(plan: LocalWebRuntimePlan) -> str:
    data = plan.to_dict()
    return "\n".join(
        [
            "ACA Local Web Runtime",
            f"contract: {data['contract']}",
            f"studio:   {data['endpoints']['studio']}",
            f"health:   {data['endpoints']['health']}",
            f"status:   {data['endpoints']['runtime_status']}",
            "stop:     Ctrl+C",
        ]
    )
