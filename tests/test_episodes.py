from __future__ import annotations

from pathlib import Path

import pandas as pd

from rowflow.episodes import write_episode_absorption


def test_episode_absorption_handles_iro_net_selling_and_denominators(tmp_path: Path) -> None:
    panel = tmp_path / "rowflow_panel.csv"
    panel.write_text(
        "\n".join(
            [
                "month,quarter,tic_source_regime,tic_treasury_flow_scope,tic_foreign_official_treasury_net_flow_usd_millions,tic_foreign_private_treasury_net_flow_usd_millions,tic_international_regional_organizations_treasury_net_flow_usd_millions,tic_foreign_total_treasury_net_flow_usd_millions,tic_foreign_total_with_iro_treasury_net_flow_usd_millions,tic_row_absorption_leader,net_issuance_usd_millions,marketable_debt_usd_millions",
                "2024-01,2024Q1,expanded_slt_2023_on,total_treasuries,10,30,5,40,45,private_led,100,1000",
                "2024-02,2024Q1,expanded_slt_2023_on,total_treasuries,-20,-10,2,-30,-28,net_selling_or_no_absorption,200,1100",
            ]
        ),
        encoding="utf-8",
    )
    z1 = tmp_path / "z1.csv"
    z1.write_text(
        "\n".join(
            [
                "quarter,z1_foreign_official_treasury_transaction_q_usd_millions,z1_foreign_private_treasury_transaction_q_usd_millions,z1_foreign_total_treasury_transaction_q_usd_millions,z1_row_absorption_leader",
                "2024Q1,7,9,16,private_led",
            ]
        ),
        encoding="utf-8",
    )
    episodes = tmp_path / "episodes.yml"
    episodes.write_text(
        "\n".join(
            [
                "version: 1",
                "episodes:",
                "  - id: tic_test",
                "    label: TIC test",
                "    source: tic",
                "    frequency: monthly",
                "    start: 2024-01",
                "    end: 2024-02",
                "    source_regime: expanded_slt_2023_on",
                "    flow_scope: total_treasuries",
                "  - id: z1_test",
                "    label: Z1 test",
                "    source: z1",
                "    frequency: quarterly",
                "    start: 2024Q1",
                "    end: 2024Q1",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "episode_absorption.csv"

    table = write_episode_absorption(panel, z1, episodes, output)
    assert output.exists()
    tic_row = table[table["episode_id"] == "tic_test"].iloc[0]
    assert tic_row["official_absorption_usd_millions"] == -10
    assert tic_row["private_absorption_usd_millions"] == 20
    assert tic_row["iro_absorption_usd_millions"] == 7
    assert tic_row["official_private_iro_absorption_usd_millions"] == 17
    assert tic_row["private_led_periods"] == 1
    assert tic_row["net_selling_or_no_absorption_periods"] == 1
    assert tic_row["private_share_of_net_issuance"] == 20 / 300
    assert tic_row["official_private_iro_share_of_marketable_debt"] == 17 / 1100

    z1_row = table[table["episode_id"] == "z1_test"].iloc[0]
    assert z1_row["official_private_absorption_usd_millions"] == 16


def test_episode_absorption_reports_missing_denominators(tmp_path: Path) -> None:
    panel = tmp_path / "rowflow_panel.csv"
    pd.DataFrame(
        {
            "month": ["2024-01"],
            "quarter": ["2024Q1"],
            "tic_source_regime": ["expanded_slt_2023_on"],
            "tic_treasury_flow_scope": ["total_treasuries"],
            "tic_foreign_official_treasury_net_flow_usd_millions": [10],
            "tic_foreign_private_treasury_net_flow_usd_millions": [20],
            "tic_foreign_total_treasury_net_flow_usd_millions": [30],
        }
    ).to_csv(panel, index=False)
    z1 = tmp_path / "z1.csv"
    pd.DataFrame(
        {
            "quarter": ["2024Q1"],
            "z1_foreign_official_treasury_transaction_q_usd_millions": [1],
            "z1_foreign_private_treasury_transaction_q_usd_millions": [2],
            "z1_foreign_total_treasury_transaction_q_usd_millions": [3],
        }
    ).to_csv(z1, index=False)
    episodes = tmp_path / "episodes.yml"
    episodes.write_text(
        "\n".join(
            [
                "version: 1",
                "episodes:",
                "  - id: tic_missing_denominator",
                "    source: tic",
                "    frequency: monthly",
                "    start: 2024-01",
                "    end: 2024-01",
            ]
        ),
        encoding="utf-8",
    )
    table = write_episode_absorption(panel, z1, episodes, tmp_path / "episode_absorption.csv")
    row = table.iloc[0]
    assert "net_issuance:unavailable" in row["denominator_status"]
    assert pd.isna(row["private_share_of_net_issuance"])


def test_episode_requires_every_period_and_finite_component_and_denominator() -> None:
    from rowflow.episodes import _tic_episode_row
    from rowflow.panels import TIC_IRO, TIC_OFFICIAL, TIC_PRIVATE, TIC_TOTAL, TIC_TOTAL_WITH_IRO

    columns = [TIC_OFFICIAL, TIC_PRIVATE, TIC_TOTAL, TIC_IRO, TIC_TOTAL_WITH_IRO]
    frame = pd.DataFrame({"month": ["2024-01", "2024-02", "2024-03"],
                          **{c: [1, 2, 3] for c in columns},
                          "net_issuance_usd_millions": [10, 20, 30],
                          "marketable_debt_usd_millions": [100, 200, 300]})
    episode = {"id": "fixed", "start": "2024-01", "end": "2024-03"}
    full = _tic_episode_row(frame, episode)
    assert full["n_expected"] == full["n_valid"] == 3
    assert full["official_absorption_usd_millions"] == 6
    for partial in [frame.iloc[:0], frame.iloc[:2], frame.iloc[[0, 2]],
                    frame.assign(**{TIC_OFFICIAL: [None, None, None]})]:
        row = _tic_episode_row(partial, episode)
        assert row["coverage_status"] == "incomplete"
        assert row["n_expected"] == 3
        assert pd.isna(row["official_absorption_usd_millions"])
        assert pd.isna(row["official_share_of_net_issuance"])
    for bad in [None, "bad", float("inf")]:
        broken = frame.assign(net_issuance_usd_millions=[10, bad, 30],
                              marketable_debt_usd_millions=[100, 200, bad])
        row = _tic_episode_row(broken, episode)
        assert row["net_issuance_n_valid"] == 2
        assert pd.isna(row["net_issuance_denominator_usd_millions"])
        assert pd.isna(row["marketable_debt_denominator_usd_millions"])
        assert pd.isna(row["private_share_of_net_issuance"])
