from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from rowflow.determinants import VARIABLE_MAP
from rowflow.io import ensure_parent, read_csv_flexible, write_csv

CLAIM_BOUNDARY = "descriptive_association_not_causal_demand_curve"
COMPACT_PRESENTATION_NOTE = "descriptive association; not a causal demand curve"
COMPACT_COLUMNS = [
    "sample_label",
    "source_regime",
    "flow_scope",
    "regressor",
    "official_coefficient",
    "official_std_error",
    "official_t_stat",
    "official_p_value",
    "official_n_obs",
    "private_coefficient",
    "private_std_error",
    "private_t_stat",
    "private_p_value",
    "private_n_obs",
    "private_minus_official_coefficient",
    "max_abs_t_stat",
    "inference",
    "claim_boundary",
    "presentation_note",
]


def _load_spec(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("determinant spec must be a mapping")
    return payload


def _candidate_regressors(panel: pd.DataFrame, spec: dict[str, Any]) -> list[str]:
    regressors: list[str] = []
    blocks = spec.get("baseline_blocks", {})
    if not isinstance(blocks, dict):
        return regressors
    for values in blocks.values():
        if not isinstance(values, list):
            continue
        for variable in values:
            variable = str(variable)
            standardized = f"{variable}_z"
            if standardized in panel.columns:
                regressors.append(standardized)
                continue
            for candidate in VARIABLE_MAP.get(variable, [variable]):
                if candidate in panel.columns:
                    regressors.append(candidate)
                    break
    return list(dict.fromkeys(regressors))


def _sample_definitions(spec: dict[str, Any]) -> list[dict[str, str]]:
    samples = spec.get("samples", {})
    if not isinstance(samples, dict):
        return []
    out = []
    for sample_id, sample in samples.items():
        if not isinstance(sample, dict) or sample.get("frequency") != "monthly":
            continue
        source_regime = sample.get("source_regime")
        flow_scope = sample.get("flow_scope")
        if source_regime and flow_scope:
            out.append(
                {
                    "sample_id": str(sample_id),
                    "sample_label": str(sample_id).replace("_", " "),
                    "source_regime": str(source_regime),
                    "flow_scope": str(flow_scope),
                }
            )
    return out


def _normal_p_value(t_stat: float) -> float:
    if pd.isna(t_stat):
        return math.nan
    return math.erfc(abs(float(t_stat)) / math.sqrt(2.0))


def _hac_covariance(x: np.ndarray, residuals: np.ndarray, lag: int) -> np.ndarray:
    xtx_inv = np.linalg.pinv(x.T @ x)
    xu = x * residuals[:, None]
    meat = xu.T @ xu
    max_lag = min(max(int(lag), 0), max(len(x) - 1, 0))
    for step in range(1, max_lag + 1):
        weight = 1.0 - step / (max_lag + 1.0)
        gamma = xu[step:].T @ xu[:-step]
        meat += weight * (gamma + gamma.T)
    return xtx_inv @ meat @ xtx_inv


def _fit_ols(
    frame: pd.DataFrame,
    outcome: str,
    regressors: list[str],
    hac_lag: int,
) -> list[dict[str, float | str | int]]:
    columns = [outcome, *regressors]
    work = frame[columns].apply(pd.to_numeric, errors="coerce").dropna()
    if work.empty or len(work) < len(regressors) + 3:
        return []

    x = np.column_stack([np.ones(len(work)), work[regressors].to_numpy(dtype=float)])
    y = work[outcome].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(x, y, rcond=None)
    residuals = y - x @ beta
    rank = int(np.linalg.matrix_rank(x))
    dof = len(work) - rank
    if dof <= 0:
        return []
    covariance = _hac_covariance(x, residuals, hac_lag)
    std_errors = np.sqrt(np.maximum(np.diag(covariance), 0))

    rows: list[dict[str, float | str | int]] = []
    for index, regressor in enumerate(["intercept", *regressors]):
        coefficient = float(beta[index])
        std_error = float(std_errors[index])
        t_stat = coefficient / std_error if std_error else math.nan
        rows.append(
            {
                "regressor": regressor,
                "coefficient": coefficient,
                "std_error": std_error,
                "t_stat": t_stat,
                "p_value": _normal_p_value(t_stat),
                "n_obs": int(len(work)),
            }
        )
    return rows


def build_determinant_tables(panel_path: Path, spec_path: Path) -> pd.DataFrame:
    panel = read_csv_flexible(Path(panel_path)).copy()
    spec = _load_spec(Path(spec_path))
    inference = spec.get("inference", {}) if isinstance(spec.get("inference"), dict) else {}
    monthly_lags = inference.get("lags_monthly", [3])
    hac_lag = int(monthly_lags[0]) if isinstance(monthly_lags, list) and monthly_lags else 3
    inference_label = f"hac_newey_west_lag_{hac_lag}"
    outcomes = [outcome for outcome in spec.get("outcomes", []) if isinstance(outcome, str) and outcome.startswith("tic_")]
    outcomes = [outcome for outcome in outcomes if outcome in panel.columns]
    regressors = _candidate_regressors(panel, spec)
    samples = _sample_definitions(spec)
    if not regressors or not outcomes or not samples:
        return pd.DataFrame(
            columns=[
                "model_id",
                "outcome",
                "sample_label",
                "source_regime",
                "flow_scope",
                "scaling",
                "regressor",
                "coefficient",
                "std_error",
                "t_stat",
                "p_value",
                "n_obs",
                "inference",
                "controls_included",
                "claim_boundary",
                "model_status",
            ]
        )

    rows: list[dict[str, object]] = []
    for sample in samples:
        mask = pd.Series(True, index=panel.index)
        if "tic_source_regime" in panel.columns:
            mask &= panel["tic_source_regime"].astype(str).eq(sample["source_regime"])
        else:
            mask &= False
        if "tic_treasury_flow_scope" in panel.columns:
            mask &= panel["tic_treasury_flow_scope"].astype(str).eq(sample["flow_scope"])
        else:
            mask &= False
        sample_panel = panel[mask].copy()
        available_regressors = [
            regressor for regressor in regressors if regressor in sample_panel.columns and sample_panel[regressor].notna().any()
        ]
        for outcome in outcomes:
            model_id = f"{sample['sample_id']}__{outcome}"
            fitted = _fit_ols(sample_panel, outcome, available_regressors, hac_lag)
            if not fitted:
                rows.append(
                    {
                        "model_id": model_id,
                        "outcome": outcome,
                        "sample_label": sample["sample_label"],
                        "source_regime": sample["source_regime"],
                        "flow_scope": sample["flow_scope"],
                        "scaling": "raw_usd_millions",
                        "regressor": "",
                        "coefficient": pd.NA,
                        "std_error": pd.NA,
                        "t_stat": pd.NA,
                        "p_value": pd.NA,
                        "n_obs": int(sample_panel[outcome].notna().sum()) if outcome in sample_panel.columns else 0,
                        "inference": inference_label,
                        "controls_included": ", ".join(available_regressors),
                        "claim_boundary": CLAIM_BOUNDARY,
                        "model_status": "insufficient_complete_observations",
                    }
                )
                continue
            for row in fitted:
                rows.append(
                    {
                        "model_id": model_id,
                        "outcome": outcome,
                        "sample_label": sample["sample_label"],
                        "source_regime": sample["source_regime"],
                        "flow_scope": sample["flow_scope"],
                        "scaling": "raw_usd_millions",
                        **row,
                        "inference": inference_label,
                        "controls_included": ", ".join(available_regressors),
                        "claim_boundary": CLAIM_BOUNDARY,
                        "model_status": "estimated",
                    }
                )
    return pd.DataFrame(rows)


def write_determinant_tables(panel_path: Path, spec_path: Path, output_path: Path) -> pd.DataFrame:
    table = build_determinant_tables(panel_path, spec_path)
    write_csv(table, Path(output_path))
    return table


def build_compact_determinant_table(determinants_path: Path) -> pd.DataFrame:
    determinants = read_csv_flexible(Path(determinants_path)).copy()
    if determinants.empty:
        return pd.DataFrame(columns=COMPACT_COLUMNS)
    work = determinants[
        determinants.get("model_status", pd.Series(dtype=str)).astype(str).eq("estimated")
        & determinants.get("regressor", pd.Series(dtype=str)).astype(str).ne("intercept")
    ].copy()
    if work.empty:
        return pd.DataFrame(columns=COMPACT_COLUMNS)

    work["outcome_group"] = "other"
    work.loc[work["outcome"].astype(str).str.contains("official", case=False, na=False), "outcome_group"] = "official"
    work.loc[work["outcome"].astype(str).str.contains("private", case=False, na=False), "outcome_group"] = "private"
    work = work[work["outcome_group"].isin(["official", "private"])].copy()
    id_columns = ["sample_label", "source_regime", "flow_scope", "regressor", "inference", "claim_boundary"]
    metric_columns = ["coefficient", "std_error", "t_stat", "p_value", "n_obs"]
    wide = work.pivot_table(index=id_columns, columns="outcome_group", values=metric_columns, aggfunc="first").reset_index()
    wide.columns = [
        "_".join(str(part) for part in column if part) if isinstance(column, tuple) else str(column)
        for column in wide.columns
    ]
    rename = {
        "coefficient_official": "official_coefficient",
        "coefficient_private": "private_coefficient",
        "std_error_official": "official_std_error",
        "std_error_private": "private_std_error",
        "t_stat_official": "official_t_stat",
        "t_stat_private": "private_t_stat",
        "p_value_official": "official_p_value",
        "p_value_private": "private_p_value",
        "n_obs_official": "official_n_obs",
        "n_obs_private": "private_n_obs",
    }
    wide = wide.rename(columns=rename)
    for column in ["official_coefficient", "private_coefficient", "official_t_stat", "private_t_stat"]:
        if column in wide.columns:
            wide[column] = pd.to_numeric(wide[column], errors="coerce")
    wide["private_minus_official_coefficient"] = wide.get("private_coefficient") - wide.get("official_coefficient")
    wide["max_abs_t_stat"] = pd.concat(
        [
            wide.get("official_t_stat", pd.Series(dtype=float)).abs(),
            wide.get("private_t_stat", pd.Series(dtype=float)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    wide["presentation_note"] = COMPACT_PRESENTATION_NOTE
    existing_columns = [column for column in COMPACT_COLUMNS if column in wide.columns]
    return wide[existing_columns].sort_values(["sample_label", "max_abs_t_stat", "regressor"], ascending=[True, False, True]).reset_index(drop=True)


def write_compact_determinant_table(determinants_path: Path, output_path: Path) -> pd.DataFrame:
    table = build_compact_determinant_table(determinants_path)
    write_csv(table, Path(output_path))
    return table


def _fmt_number(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    numeric = float(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.3f}"


def write_compact_determinant_markdown(compact_path: Path, output_md: Path, max_rows: int = 12) -> Path:
    compact = read_csv_flexible(Path(compact_path))
    preview = compact.head(max(max_rows, 0)).copy()
    lines = [
        "# Compact TIC determinant summary",
        "",
        "This table is a presentation summary derived from `monthly_tic_determinants.csv`.",
        "The rows are descriptive associations within labeled TIC source regimes, not causal demand-curve estimates or model-selection proof.",
        "",
        f"- Rows in compact CSV: {len(compact):,}",
        f"- Rows shown below: {len(preview):,}",
    ]
    if "inference" in compact.columns:
        inference = ", ".join(sorted(compact["inference"].dropna().astype(str).unique()))
        lines.append(f"- Inference label: {inference if inference else 'not available'}")
    lines.extend(
        [
            f"- Claim boundary: {COMPACT_PRESENTATION_NOTE}",
            "",
            "| sample | regressor | official coef | official t | private coef | private t | private-official | max abs t |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in preview.to_dict("records"):
        lines.append(
            "| "
            f"{row.get('sample_label', '')} | "
            f"{row.get('regressor', '')} | "
            f"{_fmt_number(row.get('official_coefficient'))} | "
            f"{_fmt_number(row.get('official_t_stat'))} | "
            f"{_fmt_number(row.get('private_coefficient'))} | "
            f"{_fmt_number(row.get('private_t_stat'))} | "
            f"{_fmt_number(row.get('private_minus_official_coefficient'))} | "
            f"{_fmt_number(row.get('max_abs_t_stat'))} |"
        )
    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "- TIC legacy long-term and expanded SLT total-Treasury rows remain separate source regimes.",
            "- TIC and Z.1 are separate source concepts.",
            "- International and regional organizations remain a sidecar.",
            "- Do not describe these rows as causal deposit, reserve, MMF, yield, exchange-rate, final-holder, or beneficial-owner evidence.",
            "",
        ]
    )
    ensure_parent(Path(output_md))
    Path(output_md).write_text("\n".join(lines), encoding="utf-8")
    return Path(output_md)
