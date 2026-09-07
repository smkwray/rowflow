from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_CONFIG_FILES = (
    "project.yml",
    "source_contracts.yml",
    "variables.yml",
    "schemas.yml",
    "determinant_specs.yml",
    "episodes.yml",
)

VALID_EPISODE_SOURCES = {"tic", "z1"}
VALID_EPISODE_FREQUENCIES = {"monthly", "quarterly"}


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


def _valid_month(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and len(value) == 7 and value[4] == "-"


def _valid_quarter(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and len(value) == 6 and value[4].upper() == "Q" and value[-1] in "1234"


def _validate_determinant_specs(specs: dict[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if specs.get("version") == 1:
        messages.append({"level": "ok", "check": "determinant_specs", "message": "determinant_specs.yml version is 1"})
    else:
        messages.append({"level": "error", "check": "determinant_specs", "message": "determinant_specs.yml version must be 1"})

    if specs.get("claim_boundary") == "descriptive_association_not_causal_demand_curve":
        messages.append({"level": "ok", "check": "determinant_specs", "message": "determinant claim boundary configured"})
    else:
        messages.append({"level": "error", "check": "determinant_specs", "message": "determinant claim boundary missing"})

    outcomes = specs.get("outcomes")
    if isinstance(outcomes, list) and len(outcomes) >= 4:
        messages.append({"level": "ok", "check": "determinant_specs", "message": "determinant outcomes configured"})
    else:
        messages.append({"level": "error", "check": "determinant_specs", "message": "determinant outcomes missing"})

    samples = specs.get("samples")
    if isinstance(samples, dict) and {"tic_expanded_slt", "tic_legacy_long_term", "z1_quarterly"}.issubset(samples):
        messages.append({"level": "ok", "check": "determinant_specs", "message": "determinant samples configured"})
    else:
        messages.append({"level": "error", "check": "determinant_specs", "message": "determinant samples missing"})
    return messages


def _validate_episodes(episodes_config: dict[str, Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    episodes = episodes_config.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        return [{"level": "error", "check": "episodes", "message": "episodes.yml must define a non-empty episodes list"}]

    seen: set[str] = set()
    for index, episode in enumerate(episodes, start=1):
        if not isinstance(episode, dict):
            messages.append({"level": "error", "check": "episodes", "message": f"episode {index} must be a mapping"})
            continue
        episode_id = episode.get("id")
        source = episode.get("source")
        frequency = episode.get("frequency")
        start = episode.get("start")
        end = episode.get("end")
        prefix = f"episode {episode_id or index}"

        if isinstance(episode_id, str) and episode_id and episode_id not in seen:
            seen.add(episode_id)
        else:
            messages.append({"level": "error", "check": "episodes", "message": f"{prefix}: id missing or duplicated"})

        if source not in VALID_EPISODE_SOURCES:
            messages.append({"level": "error", "check": "episodes", "message": f"{prefix}: source must be tic or z1"})
        if frequency not in VALID_EPISODE_FREQUENCIES:
            messages.append({"level": "error", "check": "episodes", "message": f"{prefix}: frequency must be monthly or quarterly"})

        valid_range = _valid_month(start) and _valid_month(end) if frequency == "monthly" else _valid_quarter(start) and _valid_quarter(end)
        if not valid_range:
            messages.append({"level": "error", "check": "episodes", "message": f"{prefix}: malformed {frequency} range"})
        elif start is not None and end is not None and str(start) > str(end):
            messages.append({"level": "error", "check": "episodes", "message": f"{prefix}: start is after end"})

    if not [message for message in messages if message["level"] == "error"]:
        messages.append({"level": "ok", "check": "episodes", "message": f"{len(episodes):,} episode(s) configured"})
    return messages


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

    messages.extend(_validate_determinant_specs(configs["determinant_specs"]))
    messages.extend(_validate_episodes(configs["episodes"]))

    return messages


def config_dir_from_root(root: Path) -> Path:
    return Path(root) / "config"
