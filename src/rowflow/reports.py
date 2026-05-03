from __future__ import annotations

from pathlib import Path

import pandas as pd

from rowflow.io import ensure_parent, read_csv_flexible
from rowflow.panels import (
    TIC_IRO,
    TIC_OFFICIAL,
    TIC_OFFICIAL_SHARE,
    TIC_PRIVATE,
    TIC_TOTAL,
    TIC_TOTAL_WITH_IRO,
    Z1_TOTAL_LEVEL_CHANGE_Q,
    Z1_TOTAL_Q,
)


def _fmt_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:,.1f}"


def _write_figures(panel: pd.DataFrame, figure_dir: Path) -> list[Path]:
    ensure_parent(figure_dir / "placeholder")
    written: list[Path] = []
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:  # noqa: BLE001 - report can still be written without figures.
        return written

    work = panel.copy()
    work["month_date"] = pd.to_datetime(work["month"].astype(str) + "-01")

    if {TIC_OFFICIAL, TIC_PRIVATE}.issubset(work.columns):
        fig = plt.figure(figsize=(8, 4.5))
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(work["month_date"], work[TIC_OFFICIAL], label="Foreign official")
        ax.plot(work["month_date"], work[TIC_PRIVATE], label="Foreign private")
        ax.axhline(0, linewidth=0.8)
        ax.set_title("Foreign official/private Treasury net flows")
        ax.set_ylabel("USD millions")
        ax.legend()
        fig.autofmt_xdate()
        fig.tight_layout()
        path = figure_dir / "foreign_official_private_flows.svg"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)

    if TIC_OFFICIAL_SHARE in work.columns:
        fig = plt.figure(figsize=(8, 4.5))
        ax = fig.add_subplot(1, 1, 1)
        ax.plot(work["month_date"], work[TIC_OFFICIAL_SHARE])
        ax.axhline(0.5, linewidth=0.8, linestyle="--")
        ax.set_title("Official share of TIC net Treasury flow")
        ax.set_ylabel("Share of net flow")
        fig.autofmt_xdate()
        fig.tight_layout()
        path = figure_dir / "official_share.svg"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)

    if "tic_row_absorption_leader" in work.columns:
        counts = work["tic_row_absorption_leader"].value_counts().sort_index()
        fig = plt.figure(figsize=(8, 4.5))
        ax = fig.add_subplot(1, 1, 1)
        ax.bar(counts.index.astype(str), counts.values)
        ax.set_title("Official-led versus private-led months")
        ax.set_ylabel("Month count")
        ax.tick_params(axis="x", labelrotation=30)
        fig.tight_layout()
        path = figure_dir / "leader_counts.svg"
        fig.savefig(path)
        plt.close(fig)
        written.append(path)

    return written


def write_rowflow_report(
    panel_path: Path,
    output_md: Path,
    figure_dir: Path,
    z1_panel_path: Path | None = None,
) -> dict[str, object]:
    panel = read_csv_flexible(Path(panel_path))
    if panel.empty:
        raise ValueError("Cannot write report for empty rowflow panel")
    figures = _write_figures(panel, Path(figure_dir))

    latest = panel.sort_values("month").iloc[-1]
    official_sum = panel[TIC_OFFICIAL].sum() if TIC_OFFICIAL in panel.columns else None
    private_sum = panel[TIC_PRIVATE].sum() if TIC_PRIVATE in panel.columns else None
    total_sum = panel[TIC_TOTAL].sum() if TIC_TOTAL in panel.columns else None
    iro_sum = panel[TIC_IRO].sum() if TIC_IRO in panel.columns else None
    total_with_iro_sum = panel[TIC_TOTAL_WITH_IRO].sum() if TIC_TOTAL_WITH_IRO in panel.columns else None
    source_regimes = sorted(panel["tic_source_regime"].dropna().astype(str).unique()) if "tic_source_regime" in panel.columns else []
    flow_scopes = sorted(panel["tic_treasury_flow_scope"].dropna().astype(str).unique()) if "tic_treasury_flow_scope" in panel.columns else []
    leader_counts = (
        panel["tic_row_absorption_leader"].value_counts().to_dict()
        if "tic_row_absorption_leader" in panel.columns
        else {}
    )

    z1_rows = 0
    z1_measure = "not supplied"
    if z1_panel_path is not None and Path(z1_panel_path).exists():
        z1_panel = read_csv_flexible(Path(z1_panel_path))
        z1_rows = len(z1_panel)
        if "z1_flow_measure" in z1_panel.columns:
            z1_measure = str(z1_panel["z1_flow_measure"].dropna().iloc[-1])
        elif Z1_TOTAL_Q in z1_panel.columns:
            z1_measure = "transaction_flow"
        elif Z1_TOTAL_LEVEL_CHANGE_Q in z1_panel.columns:
            z1_measure = "level_change"

    lines = [
        "# rowflow accounting report",
        "",
        "This report is descriptive accounting only and does not identify causal domestic liquidity effects.",
        "",
        "## Scope",
        "",
        "The report splits rest-of-world Treasury absorption into foreign official and foreign private components, then joins those components to maturity and liquidity diagnostics. TIC and Z.1 are treated as complementary source definitions, not interchangeable measures.",
        "",
        "## Current build summary",
        "",
        f"- Monthly panel rows: {len(panel):,}",
        f"- Latest month: {latest['month']}",
        f"- Latest TIC total net flow: {_fmt_number(latest.get(TIC_TOTAL))} USD millions",
        f"- Sum of official TIC flows in panel: {_fmt_number(official_sum)} USD millions",
        f"- Sum of private TIC flows in panel: {_fmt_number(private_sum)} USD millions",
        f"- Sum of total TIC flows in panel: {_fmt_number(total_sum)} USD millions",
        f"- Sum of IRO TIC flows in panel: {_fmt_number(iro_sum)} USD millions",
        f"- Sum of TIC flows including IRO sidecar: {_fmt_number(total_with_iro_sum)} USD millions",
        f"- TIC source regimes: {', '.join(source_regimes) if source_regimes else 'not labeled'}",
        f"- TIC Treasury flow scopes: {', '.join(flow_scopes) if flow_scopes else 'not labeled'}",
        f"- Z.1 comparison rows supplied: {z1_rows:,}",
        f"- Z.1 comparison measure: {z1_measure}",
        "",
        "## Evidence layers",
        "",
        "- TIC monthly evidence is transaction-flow evidence under the TIC source sign convention.",
        "- Pre-2023 TIC legacy evidence covers long-term Treasury bonds and notes; February 2023 forward SLT evidence covers total Treasuries in the expanded file layout.",
        "- International and regional organizations are carried as a separate TIC sidecar rather than folded into private foreign absorption.",
        "- Z.1 quarterly evidence is accounting context. The primary real build uses FRED transaction series; when transaction series are unavailable, the package labels level changes separately from transactions.",
        "- Sibling diagnostics from buycurve, liqsub, tdcest, and tdcpass are interpretation sidecars, not causal controls or structural parameters.",
        "",
        "## Official-led versus private-led classification",
        "",
    ]
    if leader_counts:
        for leader, count in sorted(leader_counts.items()):
            lines.append(f"- {leader}: {count:,} month(s)")
    else:
        lines.append("- No leader classification was available.")

    lines.extend(
        [
            "",
            "## Figures",
            "",
        ]
    )
    if figures:
        for path in figures:
            lines.append(f"- `{path.name}`")
    else:
        lines.append("- Figure generation skipped because matplotlib was unavailable.")

    lines.extend(
        [
            "",
            "## Boundaries",
            "",
            "This accounting package refines who absorbed Treasury supply. It does not claim that foreign official or foreign private absorption caused changes in deposits, reserves, MMFs, ON RRP, or yields. Any causal interpretation requires a separate identification design.",
            "",
        ]
    )

    ensure_parent(Path(output_md))
    Path(output_md).write_text("\n".join(lines), encoding="utf-8")
    return {"report": str(output_md), "figures": [str(path) for path in figures]}
