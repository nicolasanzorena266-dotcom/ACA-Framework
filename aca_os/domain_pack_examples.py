from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from aca_os.domain_pack_loader import DomainPackLoader, DomainPackLoaderSnapshot
from aca_os.domain_pack_manifest import DomainPackManifest

EXAMPLE_DOMAIN_PACKS_ROOT = Path(__file__).resolve().parent.parent / "examples" / "domain_packs"
EXAMPLE_DOMAIN_PACKS_CONTRACT = "domain_pack_examples.v1"


def example_domain_pack_root() -> Path:
    """Return the repository-local example Domain Pack root."""

    return EXAMPLE_DOMAIN_PACKS_ROOT


def discover_example_domain_pack_manifests(root: str | Path | None = None) -> tuple[Path, ...]:
    """Discover bundled example Domain Pack manifests deterministically."""

    base = Path(root) if root is not None else EXAMPLE_DOMAIN_PACKS_ROOT
    loader = DomainPackLoader()
    return tuple(loader.discover(base))


def load_example_domain_pack_manifests(root: str | Path | None = None) -> tuple[DomainPackManifest, ...]:
    """Parse bundled example Domain Pack manifests without loading runtime state."""

    return tuple(DomainPackManifest.from_file(path) for path in discover_example_domain_pack_manifests(root))


def example_domain_pack_catalog(root: str | Path | None = None) -> Dict[str, Any]:
    """Expose example Domain Pack metadata as a deterministic catalog."""

    manifests = load_example_domain_pack_manifests(root)
    return {
        "contract": EXAMPLE_DOMAIN_PACKS_CONTRACT,
        "root": (Path(root) if root is not None else EXAMPLE_DOMAIN_PACKS_ROOT).as_posix(),
        "pack_count": len(manifests),
        "packs": [
            {
                "name": manifest.name,
                "version": manifest.version,
                "domain": manifest.domain,
                "capabilities": list(manifest.capability_names()),
                "assets": [asset.to_dict() for asset in manifest.assets],
                "tags": list(manifest.tags),
                "metadata": dict(manifest.metadata),
            }
            for manifest in manifests
        ],
    }


def load_example_domain_packs(loader: DomainPackLoader, *, strict: bool = False) -> DomainPackLoaderSnapshot:
    """Load bundled example Domain Packs through an explicit loader boundary."""

    return loader.load(EXAMPLE_DOMAIN_PACKS_ROOT, strict=strict)
