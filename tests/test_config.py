from __future__ import annotations

from pathlib import Path

from rowflow.config import load_all_configs, validate_config_dir


def test_config_bundle_loads() -> None:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    configs = load_all_configs(config_dir)
    assert configs["project"]["project"]["name"] == "rowflow"
    assert "sibling_artifacts" in configs["source_contracts"]


def test_validate_config_has_no_errors() -> None:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    messages = validate_config_dir(config_dir)
    assert not [m for m in messages if m["level"] == "error"]
