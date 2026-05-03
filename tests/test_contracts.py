from __future__ import annotations

from pathlib import Path

from conftest import fixture_path

from rowflow.contracts import copy_sibling_outputs, validate_sibling_sources


def test_validate_sibling_sources_with_fixture_root() -> None:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    messages = validate_sibling_sources(config_dir, fixture_path("sibling_root"), strict=True)
    required_errors = [m for m in messages if m["level"] == "error"]
    assert not required_errors
    assert any(m["project"] == "buycurve" and m["level"] == "ok" for m in messages)


def test_copy_sibling_outputs_with_fixture_root(tmp_path: Path) -> None:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    rows = copy_sibling_outputs(
        config_dir,
        project_root=tmp_path,
        sibling_root=fixture_path("sibling_root"),
        strict=True,
    )
    assert not [row for row in rows if row["level"] == "error"]
    assert (tmp_path / "data/imported/buycurve/monthly_issuance_maturity_panel.csv").exists()
    assert (tmp_path / "data/imported/source_copy_manifest.csv").exists()
