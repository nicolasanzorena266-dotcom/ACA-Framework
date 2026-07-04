from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KERNEL_PATH = ROOT / "kernel"
for path in [ROOT, KERNEL_PATH]:
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)

from aca_os.deployable_web_package import build_deployable_web_package, validate_deployable_web_package


def main() -> None:
    parser = argparse.ArgumentParser(description="ACA deployable web package helper")
    parser.add_argument("--app-name", default="aca-framework")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port-env", default="PORT")
    parser.add_argument("--fallback-port", default=8765, type=int)
    parser.add_argument("--studio-path", default="studio/index.html")
    parser.add_argument("--domain-pack-root", default="examples/domain_packs")
    parser.add_argument("--validate", action="store_true", help="Validate required files against the current project root.")
    parser.add_argument("--write", help="Write the package JSON to this path.")
    args = parser.parse_args()

    package = build_deployable_web_package(
        app_name=args.app_name,
        host=args.host,
        port_env=args.port_env,
        fallback_port=args.fallback_port,
        studio_path=args.studio_path,
        domain_pack_root=args.domain_pack_root,
    )
    payload = validate_deployable_web_package(project_root=ROOT, package=package) if args.validate else package
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.write:
        target = Path(args.write)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded + "\n", encoding="utf-8")

    print(encoded)


if __name__ == "__main__":
    main()
