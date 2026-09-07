from __future__ import annotations

from pathlib import Path

import pandas as pd

from rowflow.regressions import (
    build_compact_determinant_table,
    build_determinant_tables,
    write_compact_determinant_markdown,
    write_determinant_tables,
)


def test_write_determinant_tables_uses_hac_label_and_source_labels(tmp_path: Path) -> None:
    panel = tmp_path / "foreign_absorption_determinants_monthly.csv"
    rows = []
    for index in range(12):
        x = float(index)
        rows.append(
            {
                "month": f"2024-{index + 1:02d}",
                "quarter": "2024Q1",
                "tic_source_regime": "expanded_slt_2023_on",
                "tic_treasury_flow_scope": "total_treasuries",
                "tic_foreign_official_treasury_net_flow_usd_millions": 2.0 * x + 1.0,
                "tic_foreign_private_treasury_net_flow_usd_millions": -1.0 * x + 10.0,
                "bill_share_z": x,
            }
        )
    pd.DataFrame(rows).to_csv(panel, index=False)
    spec = tmp_path / "determinant_specs.yml"
    spec.write_text(
        "\n".join(
            [
                "version: 1",
                "claim_boundary: descriptive_association_not_causal_demand_curve",
                "samples:",
                "  tic_expanded_slt:",
                "    frequency: monthly",
                "    source_regime: expanded_slt_2023_on",
                "    flow_scope: total_treasuries",
                "outcomes:",
                "  - tic_foreign_official_treasury_net_flow_usd_millions",
                "  - tic_foreign_private_treasury_net_flow_usd_millions",
                "baseline_blocks:",
                "  supply:",
                "    - bill_share",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "monthly_tic_determinants.csv"

    table = write_determinant_tables(panel, spec, output)
    assert output.exists()
    assert not table.empty
    official_bill = table[
        (table["outcome"] == "tic_foreign_official_treasury_net_flow_usd_millions")
        & (table["regressor"] == "bill_share_z")
    ].iloc[0]
    assert official_bill["coefficient"] > 0
    assert official_bill["source_regime"] == "expanded_slt_2023_on"
    assert official_bill["flow_scope"] == "total_treasuries"
    assert official_bill["inference"] == "hac_newey_west_lag_3"
    assert official_bill["claim_boundary"] == "descriptive_association_not_causal_demand_curve"


def test_determinant_tables_report_insufficient_sample(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    pd.DataFrame(
        {
            "month": ["2024-01", "2024-02"],
            "tic_source_regime": ["expanded_slt_2023_on", "expanded_slt_2023_on"],
            "tic_treasury_flow_scope": ["total_treasuries", "total_treasuries"],
            "tic_foreign_official_treasury_net_flow_usd_millions": [1, 2],
            "tic_foreign_private_treasury_net_flow_usd_millions": [2, 1],
            "bill_share_z": [0.0, 1.0],
        }
    ).to_csv(panel, index=False)
    spec = Path(__file__).resolve().parents[1] / "config" / "determinant_specs.yml"
    table = build_determinant_tables(panel, spec)
    assert "insufficient_complete_observations" in set(table["model_status"])


def test_compact_determinant_table_pivots_official_private_coefficients(tmp_path: Path) -> None:
    determinants = tmp_path / "monthly_tic_determinants.csv"
    pd.DataFrame(
        [
            {
                "model_id": "official",
                "outcome": "tic_foreign_official_treasury_net_flow_usd_millions",
                "sample_label": "tic expanded slt",
                "source_regime": "expanded_slt_2023_on",
                "flow_scope": "total_treasuries",
                "regressor": "bill_share_z",
                "coefficient": 10.0,
                "std_error": 2.0,
                "t_stat": 5.0,
                "p_value": 0.01,
                "n_obs": 37,
                "inference": "hac_newey_west_lag_3",
                "claim_boundary": "descriptive_association_not_causal_demand_curve",
                "model_status": "estimated",
            },
            {
                "model_id": "private",
                "outcome": "tic_foreign_private_treasury_net_flow_usd_millions",
                "sample_label": "tic expanded slt",
                "source_regime": "expanded_slt_2023_on",
                "flow_scope": "total_treasuries",
                "regressor": "bill_share_z",
                "coefficient": -3.0,
                "std_error": 1.5,
                "t_stat": -2.0,
                "p_value": 0.05,
                "n_obs": 37,
                "inference": "hac_newey_west_lag_3",
                "claim_boundary": "descriptive_association_not_causal_demand_curve",
                "model_status": "estimated",
            },
            {
                "model_id": "official",
                "outcome": "tic_foreign_official_treasury_net_flow_usd_millions",
                "sample_label": "tic expanded slt",
                "source_regime": "expanded_slt_2023_on",
                "flow_scope": "total_treasuries",
                "regressor": "intercept",
                "coefficient": 1.0,
                "std_error": 1.0,
                "t_stat": 1.0,
                "p_value": 0.3,
                "n_obs": 37,
                "inference": "hac_newey_west_lag_3",
                "claim_boundary": "descriptive_association_not_causal_demand_curve",
                "model_status": "estimated",
            },
        ]
    ).to_csv(determinants, index=False)

    compact = build_compact_determinant_table(determinants)

    assert len(compact) == 1
    row = compact.iloc[0]
    assert row["regressor"] == "bill_share_z"
    assert row["official_coefficient"] == 10.0
    assert row["private_coefficient"] == -3.0
    assert row["private_minus_official_coefficient"] == -13.0
    assert row["max_abs_t_stat"] == 5.0
    assert row["presentation_note"] == "descriptive association; not a causal demand curve"


def test_compact_determinant_markdown_includes_boundaries(tmp_path: Path) -> None:
    compact = tmp_path / "compact.csv"
    pd.DataFrame(
        {
            "sample_label": ["tic expanded slt"],
            "regressor": ["broad_dollar_z"],
            "official_coefficient": [-10.0],
            "official_t_stat": [-0.5],
            "private_coefficient": [20.0],
            "private_t_stat": [2.0],
            "private_minus_official_coefficient": [30.0],
            "max_abs_t_stat": [2.0],
            "inference": ["hac_newey_west_lag_3"],
        }
    ).to_csv(compact, index=False)
    output = tmp_path / "compact.md"

    write_compact_determinant_markdown(compact, output)

    text = output.read_text(encoding="utf-8")
    assert "Compact TIC determinant summary" in text
    assert "broad_dollar_z" in text
    assert "not causal demand-curve estimates" in text
    assert "Do not describe these rows as causal" in text
