from __future__ import annotations

from pathlib import Path

from conftest import fixture_path

from rowflow.panels import (
    TIC_IRO,
    TIC_TOTAL,
    TIC_TOTAL_WITH_IRO,
    Z1_TOTAL_LEVEL_CHANGE_Q,
    Z1_TOTAL_Q,
    build_rowflow_panel,
    build_tic_row_panel,
    build_z1_row_panel,
    build_z1_row_panel_from_fred_levels,
    combine_tic_row_panels,
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
    assert panel.loc[0, TIC_IRO] == 3
    assert panel.loc[0, TIC_TOTAL_WITH_IRO] == 38
    assert panel.loc[0, "tic_source_regime"] == "expanded_slt_2023_on"
    assert "tic_foreign_official_short_treasury_net_flow_usd_millions" in panel.columns


def test_build_tic_row_panel_from_legacy_tressect_fixture(tmp_path: Path) -> None:
    panel = build_tic_row_panel(fixture_path("tic", "tressect_minimal.txt"), tmp_path / "tic_legacy.csv")
    assert len(panel) == 2
    assert panel.loc[0, "month"] == "2022-12"
    assert panel.loc[0, TIC_TOTAL] == 20245
    assert panel.loc[0, TIC_IRO] == -267
    assert panel.loc[0, TIC_TOTAL_WITH_IRO] == 19978
    assert panel.loc[0, "tic_source_regime"] == "legacy_s_form_pre_2023"
    assert panel.loc[0, "tic_treasury_flow_scope"] == "long_term_treasury_bonds_notes"


def test_combine_tic_row_panels_prefers_later_inputs(tmp_path: Path) -> None:
    legacy = build_tic_row_panel(fixture_path("tic", "tressect_minimal.txt"), tmp_path / "legacy.csv")
    current = build_tic_row_panel(fixture_path("tic", "slt_table3_minimal.txt"), tmp_path / "current.csv")
    assert len(legacy) == 2
    assert len(current) == 2
    combined = combine_tic_row_panels([tmp_path / "legacy.csv", tmp_path / "current.csv"], tmp_path / "combined.csv")
    assert list(combined["month"]) == ["2022-12", "2023-01", "2024-01", "2024-02"]


def test_build_z1_row_panel_converts_saar_to_quarterly(tmp_path: Path) -> None:
    panel = build_z1_row_panel(fixture_path("z1", "z1_row_official_private_quarterly.csv"), tmp_path / "z1.csv")
    assert len(panel) == 2
    assert panel.loc[0, Z1_TOTAL_Q] == 75
    assert panel.loc[1, "z1_row_absorption_leader"] == "private_led"


def test_build_z1_row_panel_uses_fred_fu_transactions_without_saar_division(tmp_path: Path) -> None:
    panel = build_z1_row_panel(
        fixture_path("z1", "z1_row_official_private_fred_transactions.csv"),
        tmp_path / "z1_fu.csv",
    )
    assert len(panel) == 2
    assert panel.loc[0, Z1_TOTAL_Q] == 300
    assert panel.loc[1, Z1_TOTAL_Q] == 300
    assert panel.loc[0, "z1_foreign_official_treasury_level_usd_millions"] == 3800000


def test_build_z1_row_panel_from_fred_levels_labels_level_changes(tmp_path: Path) -> None:
    panel = build_z1_row_panel_from_fred_levels(
        fixture_path("z1", "BOGZ1FL263061130Q.observations.json"),
        fixture_path("z1", "BOGZ1FL263061145Q.observations.json"),
        tmp_path / "z1_levels.csv",
    )
    assert len(panel) == 3
    assert panel.loc[0, "quarter"] == "2024Q1"
    assert panel.loc[1, Z1_TOTAL_LEVEL_CHANGE_Q] == 60000
    assert panel.loc[1, "z1_row_level_change_leader"] == "private_led"
    assert panel.loc[1, "z1_flow_measure"] == "level_change_from_fred_levels"
    assert "z1_foreign_total_treasury_transaction_q_usd_millions" not in panel.columns


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


def test_build_rowflow_panel_curates_real_sibling_style_columns(tmp_path: Path) -> None:
    tic = build_tic_row_panel(fixture_path("tic", "tic_official_private_monthly.csv"), tmp_path / "tic.csv")
    assert len(tic) == 6
    diagnostics = tmp_path / "diagnostics.csv"
    diagnostics.write_text(
        "\n".join(
            [
                "month,bill_share,weighted_maturity_years,tga,reserves,deposits,total_mmf_assets,on_rrp,extra_raw",
                "2024-01-01,0.25,5.8,800,3500,17000,6100,600,drop_me",
                "2024-02-01,0.30,5.7,750,3520,17050,6150,580,drop_me",
            ]
        ),
        encoding="utf-8",
    )
    tdc = tmp_path / "tdc.csv"
    tdc.write_text(
        "\n".join(
            [
                "date,tdc_tier2_interest_corrected_bank_only_ru_flow,tdc_base_bank_only_ru_flow,extra_raw",
                "2024-03-31,45,50,drop_me",
                "2024-06-30,-25,-20,drop_me",
            ]
        ),
        encoding="utf-8",
    )
    panel = build_rowflow_panel(
        tmp_path / "tic.csv",
        output_path=tmp_path / "rowflow.csv",
        diagnostics_path=diagnostics,
        tdc_context_path=tdc,
    )
    assert "extra_raw" not in panel.columns
    assert panel.loc[0, "wam_years"] == 5.8
    assert panel.loc[0, "tga_usd_millions"] == 800
    assert panel.loc[0, "tdc_bank_only_qoq_usd_millions"] == 45
