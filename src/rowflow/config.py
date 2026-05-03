from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_CONFIG_FILES = (
    "project.yml",
    "source_contracts.yml",
    "variables.yml",
    "schemas.yml",
)


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return an empty dict for an empty document."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_all_configs(config_dir: Path) -> dict[str, dict[str, Any]]:
    """Load the public rowflow config bundle."""
    config_dir = Path(config_dir)
    configs: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_CONFIG_FILES:
        path = config_dir / name
        if not path.exists():
            raise FileNotFoundError(f"Missing required config file: {path}")
        configs[path.stem] = load_yaml(path)
    optional_report = config_dir / "report.yml"
    if optional_report.exists():
        configs["report"] = load_yaml(optional_report)
    return configs


def validate_config_dir(config_dir: Path) -> list[dict[str, str]]:
    """Return validation messages for the config directory."""
    messages: list[dict[str, str]] = []
    config_dir = Path(config_dir)
    for name in REQUIRED_CONFIG_FILES:
        path = config_dir / name
        if path.exists():
            messages.append({"level": "ok", "check": "config_file", "message": f"found {name}"})
        else:
            messages.append({"level": "error", "check": "config_file", "message": f"missing {name}"})

    try:
        configs = load_all_configs(config_dir)
    except Exception as exc:  # noqa: BLE001 - config validation should surface any parse failure.
        messages.append({"level": "error", "check": "config_parse", "message": str(exc)})
        return messages

    project = configs["project"].get("project", {})
    if project.get("name") == "rowflow":
        messages.append({"level": "ok", "check": "project_name", "message": "project.name is rowflow"})
    else:
        messages.append({"level": "error", "check": "project_name", "message": "project.name must be rowflow"})

    boundary = configs["project"].get("claim_boundary", {})
    phrase = boundary.get("required_report_phrase")
    if phrase and "does not identify causal" in phrase:
        messages.append({"level": "ok", "check": "claim_boundary", "message": "required descriptive boundary phrase configured"})
    else:
        messages.append({"level": "error", "check": "claim_boundary", "message": "missing required descriptive boundary phrase"})

    schemas = configs["schemas"].get("schemas", {})
    for schema_name in ("tic_row_panel", "z1_row_panel", "rowflow_panel"):
        if schema_name in schemas and schemas[schema_name].get("required_columns"):
            messages.append({"level": "ok", "check": "schema", "message": f"{schema_name} has required columns"})
        else:
            messages.append({"level": "error", "check": "schema", "message": f"{schema_name} missing required columns"})

    return messages


def config_dir_from_root(root: Path) -> Path:
    return Path(root) / "config"
