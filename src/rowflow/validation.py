from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from rowflow.config import load_all_configs, validate_config_dir
from rowflow.io import read_csv_flexible


def print_messages(messages: list[dict[str, str]]) -> None:
    for message in messages:
        level = message.get("level", "info").upper()
        text = message.get("message", "")
        print(f"[{level}] {text}")


def has_errors(messages: list[dict[str, str]]) -> bool:
    return any(message.get("level") == "error" for message in messages)


def validate_schema(df: pd.DataFrame, required_columns: list[str], name: str) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for column in required_columns:
        if column in df.columns:
            messages.append({"level": "ok", "check": "schema", "message": f"{name}: found {column}"})
        else:
            messages.append({"level": "error", "check": "schema", "message": f"{name}: missing {column}"})
    if not df.empty:
        messages.append({"level": "ok", "check": "rows", "message": f"{name}: {len(df):,} row(s)"})
    else:
        messages.append({"level": "error", "check": "rows", "message": f"{name}: empty"})
    return messages


def _validate_report_text(report_path: Path, configs: dict[str, dict]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    text = Path(report_path).read_text(encoding="utf-8").lower()
    requirements = configs["schemas"].get("report_requirements", {})
    for phrase in requirements.get("required_phrases", []):
        if phrase.lower() in text:
            messages.append({"level": "ok", "check": "report_phrase", "message": f"report includes: {phrase}"})
        else:
            messages.append({"level": "error", "check": "report_phrase", "message": f"report missing: {phrase}"})
    for phrase in requirements.get("disallowed_unqualified_phrases", []):
        if phrase.lower() in text:
            messages.append({"level": "error", "check": "report_claim", "message": f"report contains disallowed phrase: {phrase}"})
        else:
            messages.append({"level": "ok", "check": "report_claim", "message": f"report avoids: {phrase}"})
    return messages


def validate_rowflow_package(
    root: Path,
    config_dir: Path,
    panel_path: Path,
    report_path: Path,
    manifest_path: Path,
    strict: bool = False,
) -> list[dict[str, str]]:
    messages = validate_config_dir(config_dir)
    configs = load_all_configs(config_dir)

    schemas = configs["schemas"].get("schemas", {})
    panel_path = Path(panel_path)
    if panel_path.exists():
        panel = read_csv_flexible(panel_path)
        messages.extend(validate_schema(panel, schemas["rowflow_panel"]["required_columns"], "rowflow_panel"))
    else:
        messages.append({"level": "error" if strict else "warning", "check": "artifact", "message": f"missing panel {panel_path}"})

    report_path = Path(report_path)
    if report_path.exists():
        messages.append({"level": "ok", "check": "artifact", "message": f"found report {report_path}"})
        messages.extend(_validate_report_text(report_path, configs))
    else:
        messages.append({"level": "error" if strict else "warning", "check": "artifact", "message": f"missing report {report_path}"})

    manifest_path = Path(manifest_path)
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("project") == "rowflow":
                messages.append({"level": "ok", "check": "manifest", "message": "manifest project is rowflow"})
            else:
                messages.append({"level": "error", "check": "manifest", "message": "manifest project is not rowflow"})
        except json.JSONDecodeError as exc:
            messages.append({"level": "error", "check": "manifest", "message": f"manifest JSON parse failed: {exc}"})
    else:
        messages.append({"level": "error" if strict else "warning", "check": "manifest", "message": f"missing manifest {manifest_path}"})

    gitignore = Path(root) / ".gitignore"
    if gitignore.exists():
        text = gitignore.read_text(encoding="utf-8")
        if "do/" in text:
            messages.append({"level": "ok", "check": "gitignore", "message": ".gitignore excludes do/"})
        else:
            messages.append({"level": "error", "check": "gitignore", "message": ".gitignore must exclude do/"})
    else:
        messages.append({"level": "warning", "check": "gitignore", "message": ".gitignore not found at validation root"})
    return messages
