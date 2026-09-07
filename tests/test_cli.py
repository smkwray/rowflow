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
    source_ledger_csv = tmp_path / "output/tables/source_regime_ledger.csv"
    source_ledger_md = tmp_path / "output/reports/source_regime_ledger.md"
    episode_absorption = tmp_path / "output/tables/episode_absorption.csv"
    determinant_panel = tmp_path / "data/derived/foreign_absorption_determinants_monthly.csv"
    determinant_missingness = tmp_path / "output/tables/determinant_panel_missingness.csv"
    determinant_tables = tmp_path / "output/tables/monthly_tic_determinants.csv"
    compact_determinant_table = tmp_path / "output/tables/monthly_tic_determinants_compact.csv"
    compact_determinant_report = tmp_path / "output/reports/monthly_tic_determinants_compact.md"
    determinant_report = tmp_path / "output/reports/foreign_absorption_determinants.md"
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
        "--issuance-diagnostics", str(fixture_path("sibling_root", "buycurve", "data", "clean", "monthly_issuance_maturity_panel.csv")),
        "--debt-denominators", str(fixture_path("mspd", "mspd_table_1.csv")),
        "--fred-diagnostics", str(fixture_path("fred", "core_wide.csv")),
        "--fred-diagnostics", str(fixture_path("fred", "dtwexbgs.csv")),
        "--tdc-context", str(fixture_path("tdcest", "tdc_quarterly_context.csv")),
        "--output", str(panel),
    ]) == 0
    assert main([
        "write-source-regime-ledger",
        "--tic-panel", str(tic),
        "--z1-panel", str(z1),
        "--output-csv", str(source_ledger_csv),
        "--output-md", str(source_ledger_md),
    ]) == 0
    assert main([
        "write-episode-absorption",
        "--panel", str(panel),
        "--z1-panel", str(z1),
        "--episodes", str(config_dir / "episodes.yml"),
        "--output", str(episode_absorption),
    ]) == 0
    assert main([
        "build-determinant-panel",
        "--panel", str(panel),
        "--spec", str(config_dir / "determinant_specs.yml"),
        "--output", str(determinant_panel),
        "--missingness-output", str(determinant_missingness),
    ]) == 0
    assert main([
        "write-determinant-tables",
        "--panel", str(determinant_panel),
        "--spec", str(config_dir / "determinant_specs.yml"),
        "--output", str(determinant_tables),
    ]) == 0
    assert main([
        "write-compact-determinant-table",
        "--determinants", str(determinant_tables),
        "--output", str(compact_determinant_table),
    ]) == 0
    assert main([
        "write-compact-determinant-markdown",
        "--compact", str(compact_determinant_table),
        "--output-md", str(compact_determinant_report),
    ]) == 0
    assert main([
        "write-determinant-report",
        "--panel", str(determinant_panel),
        "--ledger", str(source_ledger_csv),
        "--episodes", str(episode_absorption),
        "--determinants", str(determinant_tables),
        "--output-md", str(determinant_report),
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
    assert source_ledger_csv.exists()
    assert episode_absorption.exists()
    assert determinant_panel.exists()
    assert determinant_missingness.exists()
    assert determinant_tables.exists()
    assert compact_determinant_table.exists()
    assert compact_determinant_report.exists()
    assert determinant_report.exists()
