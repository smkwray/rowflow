from __future__ import annotations

from pathlib import Path

import pandas as pd

from rowflow.determinants import build_determinant_panel


def test_build_determinant_panel_preserves_source_labels_lags_and_standardizes(tmp_path: Path) -> None:
    panel = tmp_path / "rowflow_panel.csv"
    pd.DataFrame(
        {
            "month": ["2024-01", "2024-02", "2024-03", "2024-04"],
            "quarter": ["2024Q1", "2024Q1", "2024Q1", "2024Q2"],
            "tic_source_regime": ["expanded_slt_2023_on"] * 4,
            "tic_treasury_flow_scope": ["total_treasuries"] * 4,
            "tic_foreign_official_treasury_net_flow_usd_millions": [10, 20, 30, 40],
            "tic_foreign_private_treasury_net_flow_usd_millions": [40, 30, 20, 10],
            "bill_share": [0.1, 0.2, 0.3, 0.4],
            "wam_years": [5.0, 5.5, 6.0, 6.5],
            "reserves_usd_millions": [100, 110, 120, 130],
        }
    ).to_csv(panel, index=False)
    spec = Path(__file__).resolve().parents[1] / "config" / "determinant_specs.yml"
    output = tmp_path / "foreign_absorption_determinants_monthly.csv"
    missingness = tmp_path / "determinant_panel_missingness.csv"

    out = build_determinant_panel(panel, spec, output, missingness)
    assert output.exists()
    assert missingness.exists()
    assert out["tic_source_regime"].eq("expanded_slt_2023_on").all()
    lag_col = "tic_foreign_official_treasury_net_flow_usd_millions_lag1"
    assert out.loc[1, lag_col] == 10
    assert "bill_share_z" in out.columns
    assert round(float(out["bill_share_z"].mean()), 12) == 0

    audit = pd.read_csv(missingness)
    assert "unavailable" in set(audit["status"])
    assert "available_now" in set(audit["status"])


def test_missingness_counts_only_finite_numeric_values(tmp_path: Path) -> None:
    panel, spec, audit = (tmp_path / name for name in ["panel.csv", "spec.yml", "audit.csv"])
    pd.DataFrame({"month": ["2024-01", "2024-02", "2024-03", "2024-04"],
                  "bill_share": [1, 3, "bad", float("inf")],
                  "wam_years": ["bad"] * 4}).to_csv(panel, index=False)
    spec.write_text("baseline_blocks:\n  supply: [bill_share, wam_or_duration_proxy]\n")
    out = build_determinant_panel(panel, spec, missingness_output_path=audit)
    rows = pd.read_csv(audit).set_index("variable")
    assert rows.loc["bill_share", "non_null"] == 2
    assert rows.loc["bill_share", "missing"] == 2
    assert out["bill_share_z"].notna().sum() == 2
    assert rows.loc["wam_or_duration_proxy", "status"] == "unavailable"
    assert rows.loc["wam_or_duration_proxy", "non_null"] == 0
