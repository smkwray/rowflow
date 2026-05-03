from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from rowflow.io import ensure_parent, sha256_file


def _manifest_entry(path: Path, root: Path) -> dict[str, object]:
    stat = path.stat()
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    return {
        "path": str(rel),
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    }


def write_output_manifest(root: Path, output_path: Path) -> dict[str, object]:
    root = Path(root)
    include_roots = [root / "config", root / "data/derived", root / "output"]
    files: list[dict[str, object]] = []
    for include_root in include_roots:
        if include_root.exists():
            for path in sorted(include_root.rglob("*")):
                if path.is_file() and path.name != ".gitkeep":
                    files.append(_manifest_entry(path, root))

    manifest: dict[str, object] = {
        "project": "rowflow",
        "created_utc": datetime.now(tz=UTC).isoformat(),
        "claim_boundary": "descriptive accounting only; no causal domestic liquidity effects are identified",
        "files": files,
    }
    ensure_parent(Path(output_path))
    Path(output_path).write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
