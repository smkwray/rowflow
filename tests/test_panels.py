from __future__ import annotations

from pathlib import Path

from conftest import fixture_path

from rowflow.panels import (
    TIC_TOTAL,
    Z1_TOTAL_Q,
    build_rowflow_panel,
    build_tic_row_panel,
    build_z1_row_panel,
)


def test_build_tic_row_panel_from_wide_fixture(tmp_path: Path) -> None:
    out = tmp_path / "tic.csv"
    panel = build_tic_row_panel(fixture_path("tic", "tic_official_private_monthly.csv"), out)
    assert out.exists()
    assert len(panel) == 6
    assert panel.loc[0, TIC_TOTAL] == 35
    assert panel.loc[0, "tic_row_absorption_leader"] == "private_led"
    assert panel.loc[3, "tic_row_absorption_leader"] == "official_led"


def test_build_tic_row_panel_from_slt_table3_fixture(tmp_path: Path) -> None:
    panel = build_tic_row_panel(fixture_path("tic", "slt_table3_minimal.txt"), tmp_path / "tic_slt.csv")
    assert len(panel) == 2
    assert panel.loc[0, TIC_TOTAL] == 35
    assert "tic_foreign_official_short_treasury_net_flow_usd_millions" in panel.columns


def test_build_z1_row_panel_converts_saar_to_quarterly(tmp_path: Path) -> None:
    panel = build_z1_row_panel(fixture_path("z1", "z1_row_official_private_quarterly.csv"), tmp_path / "z1.csv")
    assert len(panel) == 2
    assert panel.loc[0, Z1_TOTAL_Q] == 75
    assert panel.loc[1, "z1_row_absorption_leader"] == "private_led"


def test_build_rowflow_panel_merges_sidecars(tmp_path: Path) -> None:
    tic = build_tic_row_panel(fixture_path("tic", "tic_official_private_monthly.csv"), tmp_path / "tic.csv")
    z1 = build_z1_row_panel(fixture_path("z1", "z1_row_official_private_quarterly.csv"), tmp_path / "z1.csv")
    assert len(tic) == 6
    assert len(z1) == 2
    panel = build_rowflow_panel(
        tmp_path / "tic.csv",
        output_path=tmp_path / "rowflow.csv",
        z1_panel_path=tmp_path / "z1.csv",
        diagnostics_path=fixture_path("diagnostics", "monthly_diagnostics.csv"),
        tdc_context_path=fixture_path("tdcest", "tdc_quarterly_context.csv"),
    )
    assert len(panel) == 6
    assert "bill_share" in panel.columns
    assert "tdc_bank_only_qoq_usd_millions" in panel.columns
    assert "tic_minus_z1_total_quarterly_flow_gap_usd_millions" in panel.columns
    assert panel.loc[0, "tic_quarterly_foreign_total_treasury_net_flow_usd_millions"] == 70
