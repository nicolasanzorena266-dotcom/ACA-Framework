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

from aca_os.public_web_demo import build_public_web_demo_manifest, validate_public_web_demo_readiness
from aca_os.public_demo_runtime_adapter import build_public_demo_runtime_adapter, validate_public_demo_runtime_adapter


def main() -> None:
    parser = argparse.ArgumentParser(description="ACA public web demo preparation helper")
    parser.add_argument("--demo-name", default="aca-public-web-demo")
    parser.add_argument("--public-base-url", default="https://example.com")
    parser.add_argument("--domain-pack-root", default="examples/domain_packs")
    parser.add_argument("--default-domain-pack", default="customer_support")
    parser.add_argument("--studio-path", default="studio/index.html")
    parser.add_argument("--port-env", default="PORT")
    parser.add_argument("--fallback-port", default=8765, type=int)
    parser.add_argument("--validate", action="store_true", help="Validate required demo files against the current project root.")
    parser.add_argument("--runtime-adapter", action="store_true", help="Print the public demo runtime adapter contract instead of the demo manifest.")
    parser.add_argument("--write", help="Write the public demo manifest/readiness JSON to this path.")
    args = parser.parse_args()

    if args.runtime_adapter:
        adapter = build_public_demo_runtime_adapter(
            demo_name=args.demo_name,
            public_base_url=args.public_base_url,
            domain_pack_root=args.domain_pack_root,
            default_domain_pack=args.default_domain_pack,
            studio_path=args.studio_path,
            port_env=args.port_env,
            fallback_port=args.fallback_port,
        )
        payload = validate_public_demo_runtime_adapter(project_root=ROOT, adapter=adapter) if args.validate else adapter
    else:
        manifest = build_public_web_demo_manifest(
            demo_name=args.demo_name,
            public_base_url=args.public_base_url,
            domain_pack_root=args.domain_pack_root,
            default_domain_pack=args.default_domain_pack,
            studio_path=args.studio_path,
            port_env=args.port_env,
            fallback_port=args.fallback_port,
        )
        payload = validate_public_web_demo_readiness(project_root=ROOT, manifest=manifest) if args.validate else manifest
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.write:
        target = Path(args.write)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(encoded + "\n", encoding="utf-8")

    print(encoded)


if __name__ == "__main__":
    main()
