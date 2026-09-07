from __future__ import annotations

from pathlib import Path

import pandas as pd

from rowflow.io import ensure_parent, read_csv_flexible

REQUIRED_DETERMINANT_REPORT_PHRASES = [
    "The determinant tables are descriptive associations, not causal demand curves.",
    "TIC monthly source-defined flows and Z.1 quarterly transactions are separate source concepts.",
    "Auction allotments, if used, are primary-market allocation signals rather than final-holder measures.",
    "Country-level TIC data, if later added, should be interpreted as source-location data rather than beneficial-owner evidence.",
]


def _fmt(value: object) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if isinstance(value, float):
        return f"{value:,.3f}"
    return str(value)


def write_determinant_report(
    panel_path: Path,
    ledger_path: Path,
    episodes_path: Path,
    determinants_path: Path,
    output_md: Path,
) -> Path:
    panel = read_csv_flexible(Path(panel_path))
    ledger = read_csv_flexible(Path(ledger_path))
    episodes = read_csv_flexible(Path(episodes_path))
    determinants = read_csv_flexible(Path(determinants_path))

    estimated = determinants[determinants.get("model_status", pd.Series(dtype=str)).astype(str).eq("estimated")]
    unavailable_controls = []
    missingness_path = Path(determinants_path).parent / "determinant_panel_missingness.csv"
    if missingness_path.exists():
        missingness = read_csv_flexible(missingness_path)
        unavailable_controls = missingness[missingness["status"].astype(str).eq("unavailable")]["variable"].astype(str).tolist()

    inference_labels = sorted(determinants["inference"].dropna().astype(str).unique()) if "inference" in determinants.columns else []
    inference_label = ", ".join(inference_labels) if inference_labels else "not available"

    lines = [
        "# Foreign absorption determinants",
        "",
        "This report extends the rowflow accounting package into a first-pass determinant layer for foreign official and foreign private Treasury absorption.",
        "",
        *REQUIRED_DETERMINANT_REPORT_PHRASES,
        "",
        f"The current estimates use OLS coefficients with Newey-West/HAC covariance where reported and are labeled `{inference_label}`.",
        "",
        "## Source ledger",
        "",
        "| source_family | frequency | sample_start | sample_end | rows | flow_scope | concept | pooling_allowed |",
        "|---|---:|---:|---:|---:|---|---|---:|",
    ]
    for row in ledger.to_dict("records"):
        lines.append(
            f"| {row.get('source_family')} | {row.get('frequency')} | {row.get('sample_start')} | {row.get('sample_end')} | {row.get('rows')} | {row.get('flow_scope')} | {row.get('transaction_or_position_concept')} | {row.get('pooling_allowed')} |"
        )

    lines.extend(
        [
            "",
            "## Episode absorption",
            "",
            "| episode | source | rows | official | private | IRO sidecar | official plus private | denominator status |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in episodes.to_dict("records"):
        lines.append(
            f"| {row.get('episode_id')} | {row.get('source_family')} | {row.get('rows')} | {_fmt(row.get('official_absorption_usd_millions'))} | {_fmt(row.get('private_absorption_usd_millions'))} | {_fmt(row.get('iro_absorption_usd_millions'))} | {_fmt(row.get('official_private_absorption_usd_millions'))} | {row.get('denominator_status', '')} |"
        )

    lines.extend(
        [
            "",
            "## Determinant table status",
            "",
            f"- Determinant panel rows: {len(panel):,}",
            f"- Estimated coefficient rows: {len(estimated):,}",
            f"- Inference label: {inference_label}",
            f"- Unavailable baseline controls: {', '.join(unavailable_controls) if unavailable_controls else 'none'}",
            "",
            "| model_id | regressor | coefficient | standard error | n_obs | status |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    preview = determinants.head(24)
    for row in preview.to_dict("records"):
        lines.append(
            f"| {row.get('model_id')} | {row.get('regressor')} | {_fmt(row.get('coefficient'))} | {_fmt(row.get('std_error'))} | {_fmt(row.get('n_obs'))} | {row.get('model_status')} |"
        )

    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "These tables summarize associations within labeled source regimes. They do not identify a causal demand curve or a domestic liquidity mechanism.",
            "International and regional organizations remain a sidecar category rather than part of private foreign absorption.",
            "TIC legacy long-term and expanded SLT total-Treasury evidence are not pooled as a single measurement regime.",
            "",
        ]
    )

    ensure_parent(Path(output_md))
    Path(output_md).write_text("\n".join(lines), encoding="utf-8")
    return Path(output_md)
