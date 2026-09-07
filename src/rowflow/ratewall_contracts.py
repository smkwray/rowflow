from __future__ import annotations

from pathlib import Path

import pandas as pd

CONTRACT_VERSION = "rowflow_ratewall_foreign_route_support_v1"
BLOCKED_USE = "final_current_demand;domestic_private_route_split;beneficial_owner_exactness"

FIELDS = [
    "support_row_id",
    "contract_version",
    "producer_project",
    "producer_artifact",
    "route_component_id",
    "source_family",
    "object_family",
    "native_frequency",
    "contract_frequency",
    "period_start",
    "period_end",
    "ref_quarter",
    "amount_usd_millions",
    "denominator_usd_millions",
    "share_of_foreign_total",
    "source_regime",
    "pooling_allowed",
    "evidence_tier",
    "measurement_stage",
    "mapping_burden",
    "assumption_status",
    "admissible_use",
    "blocked_use",
    "claim_boundary",
]

TIC_COMPONENTS = {
    "foreign_official": "tic_foreign_official_treasury_net_flow_usd_millions",
    "foreign_private": "tic_foreign_private_treasury_net_flow_usd_millions",
    "foreign_iro": "tic_international_regional_organizations_treasury_net_flow_usd_millions",
    "foreign_total": "tic_foreign_total_with_iro_treasury_net_flow_usd_millions",
}

Z1_COMPONENTS = {
    "foreign_official": "z1_foreign_official_treasury_transaction_q_usd_millions",
    "foreign_private": "z1_foreign_private_treasury_transaction_q_usd_millions",
    "foreign_total": "z1_foreign_total_treasury_transaction_q_usd_millions",
}


def _num(row: pd.Series, column: str) -> float:
    value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(value) else float(value)


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _tic_rows(panel: pd.DataFrame, producer_artifact: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, row in panel.iterrows():
        month = str(row.get("month", ""))
        if not month:
            continue
        denominator = _num(row, "tic_foreign_total_with_iro_treasury_net_flow_usd_millions")
        for component, column in TIC_COMPONENTS.items():
            amount = _num(row, column)
            share = amount / denominator if denominator else 0.0
            rows.append(
                {
                    "support_row_id": f"rowflow::tic::{month}::{component}",
                    "contract_version": CONTRACT_VERSION,
                    "producer_project": "rowflow",
                    "producer_artifact": producer_artifact,
                    "route_component_id": component,
                    "source_family": "tic_expanded_slt"
                    if str(row.get("tic_source_regime", "")).startswith("expanded")
                    else "tic_legacy_s_form",
                    "object_family": "foreign_treasury_absorption",
                    "native_frequency": "monthly",
                    "contract_frequency": "monthly",
                    "period_start": month,
                    "period_end": month,
                    "ref_quarter": str(row.get("quarter", "")),
                    "amount_usd_millions": _fmt(amount),
                    "denominator_usd_millions": _fmt(denominator),
                    "share_of_foreign_total": _fmt(share),
                    "source_regime": str(row.get("tic_source_regime", "")),
                    "pooling_allowed": "false",
                    "evidence_tier": "source_backed_measurement",
                    "measurement_stage": "foreign_holder_flow",
                    "mapping_burden": "mechanical_aggregation_only",
                    "assumption_status": "none_source_observed",
                    "admissible_use": "assumption_mode_support_ledger",
                    "blocked_use": BLOCKED_USE,
                    "claim_boundary": (
                        "foreign_absorption_support_not_domestic_current_demand"
                    ),
                }
            )
    return rows


def _z1_rows(panel: pd.DataFrame, producer_artifact: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for _, row in panel.iterrows():
        quarter = str(row.get("quarter", ""))
        if not quarter:
            continue
        denominator = _num(row, "z1_foreign_total_treasury_transaction_q_usd_millions")
        for component, column in Z1_COMPONENTS.items():
            amount = _num(row, column)
            share = amount / denominator if denominator else 0.0
            rows.append(
                {
                    "support_row_id": f"rowflow::z1::{quarter}::{component}",
                    "contract_version": CONTRACT_VERSION,
                    "producer_project": "rowflow",
                    "producer_artifact": producer_artifact,
                    "route_component_id": component,
                    "source_family": "z1_rest_of_world",
                    "object_family": "foreign_treasury_absorption",
                    "native_frequency": "quarterly",
                    "contract_frequency": "quarterly",
                    "period_start": quarter,
                    "period_end": quarter,
                    "ref_quarter": quarter,
                    "amount_usd_millions": _fmt(amount),
                    "denominator_usd_millions": _fmt(denominator),
                    "share_of_foreign_total": _fmt(share),
                    "source_regime": "z1_quarterly_rest_of_world",
                    "pooling_allowed": "false",
                    "evidence_tier": "source_backed_measurement",
                    "measurement_stage": "foreign_holder_flow",
                    "mapping_burden": "mechanical_aggregation_only",
                    "assumption_status": "none_source_observed",
                    "admissible_use": "assumption_mode_support_ledger",
                    "blocked_use": BLOCKED_USE + ";iro_not_observed_in_z1",
                    "claim_boundary": (
                        "foreign_absorption_support_not_domestic_current_demand"
                    ),
                }
            )
    return rows


def build_ratewall_foreign_route_support_contract(
    *,
    rowflow_panel: pd.DataFrame,
    z1_panel: pd.DataFrame | None = None,
    producer_artifact: str = "rowflow_panel.csv",
    z1_producer_artifact: str = "z1_row_quarterly_real.csv",
) -> pd.DataFrame:
    rows = _tic_rows(rowflow_panel, producer_artifact)
    if z1_panel is not None and not z1_panel.empty:
        rows.extend(_z1_rows(z1_panel, z1_producer_artifact))
    return pd.DataFrame(rows, columns=FIELDS)


def write_ratewall_foreign_route_support_contract(
    *,
    rowflow_panel_path: Path | str,
    output_path: Path | str,
    z1_panel_path: Path | str | None = None,
) -> tuple[Path, pd.DataFrame]:
    rowflow_panel_path = Path(rowflow_panel_path)
    z1_frame = pd.read_csv(z1_panel_path) if z1_panel_path is not None else None
    frame = build_ratewall_foreign_route_support_contract(
        rowflow_panel=pd.read_csv(rowflow_panel_path),
        z1_panel=z1_frame,
        producer_artifact=rowflow_panel_path.name,
        z1_producer_artifact=Path(z1_panel_path).name if z1_panel_path else "",
    )
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    return target, frame
