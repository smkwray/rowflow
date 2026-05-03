from __future__ import annotations

from pathlib import Path

from conftest import fixture_path

from rowflow.cli import main


def test_cli_fixture_pipeline(tmp_path: Path) -> None:
    config_dir = Path(__file__).resolve().parents[1] / "config"
    assert main(["validate-config", "--config-dir", str(config_dir)]) == 0

    tic = tmp_path / "data/derived/tic_row_monthly.csv"
    z1 = tmp_path / "data/derived/z1_row_quarterly.csv"
    panel = tmp_path / "data/derived/rowflow_panel.csv"
    report = tmp_path / "output/reports/rowflow_accounting_report.md"
    figures = tmp_path / "output/figures"
    tables = tmp_path / "output/tables"
    manifest = tmp_path / "output/manifests/rowflow_manifest.json"

    assert main(["build-tic-row-panel", "--input", str(fixture_path("tic", "tic_official_private_monthly.csv")), "--output", str(tic)]) == 0
    assert main(["build-z1-row-panel", "--input", str(fixture_path("z1", "z1_row_official_private_quarterly.csv")), "--output", str(z1)]) == 0
    assert main([
        "build-z1-row-panel-from-fred-levels",
        "--official-level-json", str(fixture_path("z1", "BOGZ1FL263061130Q.observations.json")),
        "--private-level-json", str(fixture_path("z1", "BOGZ1FL263061145Q.observations.json")),
        "--output", str(tmp_path / "data/derived/z1_row_quarterly_from_levels.csv"),
    ]) == 0
    assert main([
        "build-rowflow-panel",
        "--tic-panel", str(tic),
        "--z1-panel", str(z1),
        "--diagnostics", str(fixture_path("diagnostics", "monthly_diagnostics.csv")),
        "--tdc-context", str(fixture_path("tdcest", "tdc_quarterly_context.csv")),
        "--output", str(panel),
    ]) == 0
    assert main([
        "write-rowflow-report",
        "--panel", str(panel),
        "--z1-panel", str(z1),
        "--output-md", str(report),
        "--figure-dir", str(figures),
        "--table-dir", str(tables),
    ]) == 0
    assert main(["write-output-manifest", "--root", str(tmp_path), "--output", str(manifest)]) == 0
    assert main([
        "validate-rowflow-package",
        "--root", str(Path(__file__).resolve().parents[1]),
        "--config-dir", str(config_dir),
        "--panel", str(panel),
        "--report", str(report),
        "--manifest", str(manifest),
        "--strict",
    ]) == 0
    assert report.exists()
    assert (figures / "foreign_official_private_flows.svg").exists()
    assert (tables / "rowflow_results_summary.csv").exists()
