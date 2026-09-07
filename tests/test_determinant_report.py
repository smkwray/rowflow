from __future__ import annotations

from pathlib import Path

import pandas as pd

from rowflow.determinant_report import REQUIRED_DETERMINANT_REPORT_PHRASES, write_determinant_report
from rowflow.validation import _validate_determinant_report_text


def test_write_determinant_report_includes_boundaries(tmp_path: Path) -> None:
    panel = tmp_path / "panel.csv"
    pd.DataFrame({"month": ["2024-01"], "tic_source_regime": ["expanded_slt_2023_on"]}).to_csv(panel, index=False)
    ledger = tmp_path / "source_regime_ledger.csv"
    pd.DataFrame(
        {
            "source_family": ["tic_expanded_slt_2023_on"],
            "frequency": ["monthly"],
            "sample_start": ["2023-02"],
            "sample_end": ["2026-02"],
            "rows": [37],
            "flow_scope": ["total_treasuries"],
            "transaction_or_position_concept": ["TIC monthly source-defined net Treasury flow"],
            "pooling_allowed": [False],
        }
    ).to_csv(ledger, index=False)
    episodes = tmp_path / "episode_absorption.csv"
    pd.DataFrame(
        {
            "episode_id": ["tic_expanded_slt"],
            "source_family": ["tic"],
            "rows": [37],
            "official_absorption_usd_millions": [1.0],
            "private_absorption_usd_millions": [2.0],
            "iro_absorption_usd_millions": [0.5],
            "official_private_absorption_usd_millions": [3.0],
            "denominator_status": ["net_issuance:unavailable"],
        }
    ).to_csv(episodes, index=False)
    determinants = tmp_path / "monthly_tic_determinants.csv"
    pd.DataFrame(
        {
            "model_id": ["m"],
            "regressor": ["bill_share_z"],
            "coefficient": [1.0],
            "std_error": [0.1],
            "n_obs": [20],
            "inference": ["hac_newey_west_lag_3"],
            "model_status": ["estimated"],
        }
    ).to_csv(determinants, index=False)
    missingness = tmp_path / "determinant_panel_missingness.csv"
    pd.DataFrame({"variable": ["vix"], "status": ["unavailable"]}).to_csv(missingness, index=False)
    output = tmp_path / "foreign_absorption_determinants.md"

    write_determinant_report(panel, ledger, episodes, determinants, output)
    text = output.read_text(encoding="utf-8")
    for phrase in REQUIRED_DETERMINANT_REPORT_PHRASES:
        assert phrase in text
    assert "hac_newey_west_lag_3" in text
    assert not [message for message in _validate_determinant_report_text(output) if message["level"] == "error"]
