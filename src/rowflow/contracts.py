from __future__ import annotations

import csv
import os
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rowflow.config import load_yaml
from rowflow.io import ensure_parent, sha256_file


@dataclass(frozen=True)
class ArtifactContract:
    project: str
    artifact: str
    root: Path
    relative_path: Path
    destination: Path
    required: bool
    notes: str = ""

    @property
    def source_path(self) -> Path:
        return self.root / self.relative_path


def _resolve_project_root(project_cfg: dict[str, Any], sibling_root: Path | None) -> Path:
    env_name = project_cfg.get("root_env")
    if env_name and os.environ.get(env_name):
        return Path(os.environ[env_name]).expanduser()
    default_root = Path(project_cfg.get("default_root", ""))
    if sibling_root is not None and not default_root.is_absolute():
        # source_contracts defaults look like ../buycurve. With --sibling-root pointing
        # to a directory that contains sibling repos, use the basename as the child dir.
        return Path(sibling_root).expanduser() / default_root.name
    return default_root.expanduser()


def iter_artifact_contracts(config_dir: Path, sibling_root: Path | None = None) -> Iterable[ArtifactContract]:
    contracts = load_yaml(Path(config_dir) / "source_contracts.yml")
    for project, project_cfg in contracts.get("sibling_artifacts", {}).items():
        root = _resolve_project_root(project_cfg, sibling_root)
        for artifact, artifact_cfg in project_cfg.get("artifacts", {}).items():
            yield ArtifactContract(
                project=project,
                artifact=artifact,
                root=root,
                relative_path=Path(artifact_cfg["relative_path"]),
                destination=Path(artifact_cfg["destination"]),
                required=bool(artifact_cfg.get("required", False)),
                notes=str(artifact_cfg.get("notes", "")),
            )


def validate_sibling_sources(
    config_dir: Path,
    sibling_root: Path | None = None,
    strict: bool = False,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for contract in iter_artifact_contracts(config_dir, sibling_root):
        exists = contract.source_path.exists()
        if exists:
            level = "ok"
            message = f"found {contract.project}:{contract.artifact}"
        elif contract.required and strict:
            level = "error"
            message = f"missing required {contract.project}:{contract.artifact} at {contract.source_path}"
        elif contract.required:
            level = "warning"
            message = f"missing required {contract.project}:{contract.artifact} at {contract.source_path}"
        else:
            level = "info"
            message = f"optional missing {contract.project}:{contract.artifact} at {contract.source_path}"
        messages.append(
            {
                "level": level,
                "check": "sibling_source",
                "project": contract.project,
                "artifact": contract.artifact,
                "source_path": str(contract.source_path),
                "message": message,
            }
        )
    return messages


def copy_sibling_outputs(
    config_dir: Path,
    project_root: Path,
    sibling_root: Path | None = None,
    overwrite: bool = False,
    strict: bool = False,
    manifest_path: Path | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    project_root = Path(project_root)
    for contract in iter_artifact_contracts(config_dir, sibling_root):
        source = contract.source_path
        destination = project_root / contract.destination
        if not source.exists():
            status = "missing_required" if contract.required else "missing_optional"
            if strict and contract.required:
                level = "error"
            elif contract.required:
                level = "warning"
            else:
                level = "info"
            rows.append(
                {
                    "level": level,
                    "status": status,
                    "project": contract.project,
                    "artifact": contract.artifact,
                    "source_path": str(source),
                    "destination": str(destination),
                    "sha256": "",
                }
            )
            continue
        if destination.exists() and not overwrite:
            status = "exists_skipped"
        else:
            ensure_parent(destination)
            shutil.copy2(source, destination)
            status = "copied"
        rows.append(
            {
                "level": "ok",
                "status": status,
                "project": contract.project,
                "artifact": contract.artifact,
                "source_path": str(source),
                "destination": str(destination),
                "sha256": sha256_file(destination) if destination.exists() else "",
            }
        )

    if manifest_path is None:
        manifest_path = project_root / "data/imported/source_copy_manifest.csv"
    ensure_parent(manifest_path)
    with Path(manifest_path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["level", "status", "project", "artifact", "source_path", "destination", "sha256"],
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows
