from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from rowflow.io import read_csv_flexible, write_csv

VARIABLE_MAP = {
    "net_issuance": [
        "net_issuance_usd_millions",
        "marketable_net_issuance_usd_millions",
        "treasury_net_issuance_usd_millions",
    ],
    "gross_issuance": [
        "gross_issuance_usd_millions",
        "marketable_gross_issuance_usd_millions",
        "treasury_gross_issuance_usd_millions",
    ],
    "bill_share": ["bill_share"],
    "wam_or_duration_proxy": ["wam_years", "weighted_average_maturity_years"],
    "treasury_yield_or_term_premium": ["treasury_yield_or_term_premium", "treasury_10y_yield_pct", "term_premium_10y_pct", "dgs10"],
    "treasury_2y_yield": ["treasury_2y_yield_pct", "DGS2", "dgs2"],
    "treasury_10y_yield": ["treasury_10y_yield_pct", "DGS10", "dgs10"],
    "treasury_30y_yield": ["treasury_30y_yield_pct", "DGS30", "dgs30"],
    "term_premium_10y": ["term_premium_10y_pct", "THREEFYTP10", "threefytp10"],
    "broad_dollar": ["broad_dollar", "broad_dollar_index"],
    "vix": ["vix", "vix_index", "VIXCLS"],
    "reserves": ["reserves_usd_millions"],
    "on_rrp": ["on_rrp_usd_millions"],
    "tga": ["tga_usd_millions"],
    "fed_treasury_holdings": ["fed_treasury_holdings_usd_millions", "TREAST"],
}


def _load_spec(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("determinant spec must be a mapping")
    return payload


def _first_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _standardize(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    std = numeric.std(ddof=0)
    if pd.isna(std) or std == 0:
        return pd.Series(pd.NA, index=series.index, dtype="Float64")
    return (numeric - numeric.mean()) / std


def _candidate_variables(spec: dict[str, Any]) -> list[str]:
    blocks = spec.get("baseline_blocks", {})
    variables: list[str] = []
    if isinstance(blocks, dict):
        for values in blocks.values():
            if isinstance(values, list):
                variables.extend(str(value) for value in values)
    return variables


def build_determinant_panel(
    panel_path: Path,
    spec_path: Path,
    output_path: Path | None = None,
    missingness_output_path: Path | None = None,
) -> pd.DataFrame:
    panel = read_csv_flexible(Path(panel_path)).copy()
    if "month" not in panel.columns:
        raise ValueError("rowflow panel must include month")
    spec = _load_spec(Path(spec_path))
    out = panel.sort_values("month").reset_index(drop=True)

    outcomes = [outcome for outcome in spec.get("outcomes", []) if isinstance(outcome, str)]
    monthly_outcomes = [outcome for outcome in outcomes if outcome in out.columns and outcome.startswith("tic_")]
    for outcome in monthly_outcomes:
        for lag in range(1, 4):
            out[f"{outcome}_lag{lag}"] = pd.to_numeric(out[outcome], errors="coerce").shift(lag)

    audit_rows: list[dict[str, object]] = []
    for variable in _candidate_variables(spec):
        source_column = _first_column(out, VARIABLE_MAP.get(variable, [variable]))
        if source_column is None:
            audit_rows.append(
                {
                    "variable": variable,
                    "status": "unavailable",
                    "source_column": "",
                    "non_null": 0,
                    "missing": len(out),
                }
            )
            continue
        z_column = f"{variable}_z"
        out[z_column] = _standardize(out[source_column])
        non_null = int(out[source_column].notna().sum())
        audit_rows.append(
            {
                "variable": variable,
                "status": "available_now",
                "source_column": source_column,
                "standardized_column": z_column,
                "non_null": non_null,
                "missing": int(len(out) - non_null),
            }
        )

    if missingness_output_path is not None:
        write_csv(pd.DataFrame(audit_rows), Path(missingness_output_path))
    if output_path is not None:
        write_csv(out, Path(output_path))
    return out
