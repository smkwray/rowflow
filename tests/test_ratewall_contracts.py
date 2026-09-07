from __future__ import annotations

import pandas as pd
import pytest

from rowflow.ratewall_contracts import build_ratewall_foreign_route_support_contract


def test_foreign_route_support_keeps_tic_and_z1_regimes_separate() -> None:
    tic = pd.DataFrame(
        [
            {
                "month": "2025-01",
                "quarter": "2025Q1",
                "tic_foreign_official_treasury_net_flow_usd_millions": 10.0,
                "tic_foreign_private_treasury_net_flow_usd_millions": 20.0,
                "tic_international_regional_organizations_treasury_net_flow_usd_millions": 5.0,
                "tic_foreign_total_with_iro_treasury_net_flow_usd_millions": 35.0,
                "tic_source_regime": "expanded_slt_2023_on",
            }
        ]
    )
    z1 = pd.DataFrame(
        [
            {
                "quarter": "2025Q1",
                "z1_foreign_official_treasury_transaction_q_usd_millions": 12.0,
                "z1_foreign_private_treasury_transaction_q_usd_millions": 18.0,
                "z1_foreign_total_treasury_transaction_q_usd_millions": 30.0,
            }
        ]
    )

    rows = build_ratewall_foreign_route_support_contract(
        rowflow_panel=tic,
        z1_panel=z1,
    )

    assert set(rows["source_family"]) == {"tic_expanded_slt", "z1_rest_of_world"}
    assert set(rows["pooling_allowed"]) == {"false"}
    assert set(rows["evidence_tier"]) == {"source_backed_measurement"}
    assert "foreign_iro" in set(rows["route_component_id"])
    assert not rows.loc[
        rows["source_family"].eq("z1_rest_of_world"), "route_component_id"
    ].eq("foreign_iro").any()
    assert rows["blocked_use"].str.contains("final_current_demand").all()
    assert rows["blocked_use"].str.contains("domestic_private_route_split").all()


@pytest.mark.parametrize("value", [None, "", "not a number", float("nan"), float("inf")])
def test_foreign_route_support_rejects_missing_observations(value) -> None:
    panel = pd.DataFrame([{"month": "2025-01", "tic_foreign_total_with_iro_treasury_net_flow_usd_millions": value}])
    with pytest.raises(ValueError, match="Missing or nonfinite source value"):
        build_ratewall_foreign_route_support_contract(rowflow_panel=panel)


def test_zero_net_flow_does_not_imply_zero_component_shares() -> None:
    panel = pd.DataFrame([{
        "month": "2025-01", "quarter": "2025Q1",
        "tic_foreign_official_treasury_net_flow_usd_millions": 10.0,
        "tic_foreign_private_treasury_net_flow_usd_millions": -10.0,
        "tic_international_regional_organizations_treasury_net_flow_usd_millions": 0.0,
        "tic_foreign_total_with_iro_treasury_net_flow_usd_millions": 0.0,
        "tic_source_regime": "expanded_slt_2023_on",
    }])
    rows = build_ratewall_foreign_route_support_contract(rowflow_panel=panel)
    assert rows["share_of_foreign_total"].eq("").all()
    assert rows["amount_usd_millions"].tolist() == ["10", "-10", "0", "0"]


@pytest.mark.parametrize("quarter", [None, "", "2024Q4", "malformed"])
def test_month_derives_reference_quarter(quarter) -> None:
    from rowflow.ratewall_contracts import TIC_COMPONENTS

    row = {"month": "2025-04", "quarter": quarter}
    row.update(dict.fromkeys(TIC_COMPONENTS.values(), 1.0))
    out = build_ratewall_foreign_route_support_contract(rowflow_panel=pd.DataFrame([row]))
    assert out.ref_quarter.eq("2025Q2").all()
