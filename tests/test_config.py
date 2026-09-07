from __future__ import annotations

import shutil
from pathlib import Path

from rowflow.config import load_all_configs, validate_config_dir


def test_config_bundle_loads() -> None:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    configs = load_all_configs(config_dir)
    assert configs["project"]["project"]["name"] == "rowflow"
    assert "sibling_artifacts" in configs["source_contracts"]
    assert configs["determinant_specs"]["claim_boundary"] == "descriptive_association_not_causal_demand_curve"
    assert configs["episodes"]["episodes"]


def test_validate_config_has_no_errors() -> None:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    messages = validate_config_dir(config_dir)
    assert not [m for m in messages if m["level"] == "error"]


def test_validate_config_rejects_malformed_episode_range(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "config"
    config_dir = tmp_path / "config"
    shutil.copytree(source, config_dir)
    (config_dir / "episodes.yml").write_text(
        "\n".join(
            [
                "version: 1",
                "episodes:",
                "  - id: bad_range",
                "    source: tic",
                "    frequency: monthly",
                "    start: 2024-03",
                "    end: 2024-01",
            ]
        ),
        encoding="utf-8",
    )
    messages = validate_config_dir(config_dir)
    assert [message for message in messages if message["level"] == "error" and "start is after end" in message["message"]]
