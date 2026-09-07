from __future__ import annotations

from pathlib import Path

import pandas as pd

from rowflow.io import ensure_parent, read_csv_flexible, write_csv
from rowflow.panels import Z1_TOTAL_LEVEL_CHANGE_Q, Z1_TOTAL_Q


def _required_tic_caveat(source_regime: str, flow_scope: str) -> str:
    if source_regime == "legacy_s_form_pre_2023":
        return "Legacy TIC covers long-term Treasury bonds and notes; do not pool with expanded SLT total-Treasury data without labels."
    if source_regime == "expanded_slt_2023_on":
        return "From February 2023, Treasury totals combine reported SLT notes/bonds transactions with bills estimated from BL2 position changes; keep separate from the legacy long-term bridge."
    return f"TIC source regime {source_regime} and flow scope {flow_scope} must remain explicit."


def build_source_regime_ledger(tic_panel_path: Path, z1_panel_path: Path | None = None) -> pd.DataFrame:
    """Summarize source regimes, flow scopes, coverage, and non-pooling caveats."""
    tic = read_csv_flexible(Path(tic_panel_path))
    if "month" not in tic.columns:
        raise ValueError("TIC panel must include month")

    tic_work = tic.copy()
    if "tic_source_regime" not in tic_work.columns:
        tic_work["tic_source_regime"] = "unlabeled_tic"
    if "tic_treasury_flow_scope" not in tic_work.columns:
        tic_work["tic_treasury_flow_scope"] = "unlabeled_treasury_scope"

    rows: list[dict[str, object]] = []
    for (source_regime, flow_scope), group in tic_work.groupby(
        ["tic_source_regime", "tic_treasury_flow_scope"],
        dropna=False,
    ):
        source_regime = str(source_regime)
        flow_scope = str(flow_scope)
        rows.append(
            {
                "source_family": f"tic_{source_regime}",
                "frequency": "monthly",
                "sample_start": group["month"].min(),
                "sample_end": group["month"].max(),
                "rows": len(group),
                "flow_scope": flow_scope,
                "transaction_or_position_concept": "TIC monthly source-defined net Treasury flow",
                "pooling_allowed": False,
                "required_caveat": _required_tic_caveat(source_regime, flow_scope),
            }
        )

    if z1_panel_path is not None and Path(z1_panel_path).exists():
        z1 = read_csv_flexible(Path(z1_panel_path))
        if "quarter" not in z1.columns:
            raise ValueError("Z.1 panel must include quarter")
        if Z1_TOTAL_Q in z1.columns:
            concept = "Z.1 quarterly FU transactions"
        elif Z1_TOTAL_LEVEL_CHANGE_Q in z1.columns:
            concept = "Z.1 quarterly level-change accounting context"
        else:
            concept = "Z.1 quarterly source concept unavailable"
        rows.append(
            {
                "source_family": "z1_row_official_private",
                "frequency": "quarterly",
                "sample_start": z1["quarter"].min(),
                "sample_end": z1["quarter"].max(),
                "rows": len(z1),
                "flow_scope": "treasury_securities",
                "transaction_or_position_concept": concept,
                "pooling_allowed": False,
                "required_caveat": "Z.1 quarterly transactions and TIC monthly source-defined flows are separate source concepts.",
            }
        )

    return pd.DataFrame(rows).sort_values(["frequency", "source_family"]).reset_index(drop=True)


def write_source_regime_ledger(
    tic_panel_path: Path,
    output_csv: Path,
    z1_panel_path: Path | None = None,
    output_md: Path | None = None,
) -> pd.DataFrame:
    ledger = build_source_regime_ledger(tic_panel_path, z1_panel_path)
    write_csv(ledger, Path(output_csv))
    if output_md is not None:
        ensure_parent(Path(output_md))
        lines = [
            "# Source-regime ledger",
            "",
            "This ledger keeps TIC source regimes and Z.1 source concepts explicit before any determinant or episode accounting work.",
            "",
            "| source_family | frequency | sample_start | sample_end | rows | flow_scope | transaction_or_position_concept | pooling_allowed | required_caveat |",
            "|---|---:|---:|---:|---:|---|---|---:|---|",
        ]
        for row in ledger.to_dict("records"):
            lines.append(
                "| {source_family} | {frequency} | {sample_start} | {sample_end} | {rows} | {flow_scope} | {transaction_or_position_concept} | {pooling_allowed} | {required_caveat} |".format(
                    **row
                )
            )
        Path(output_md).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return ledger
