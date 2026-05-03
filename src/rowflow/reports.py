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

Z1_OFFICIAL_LEVEL = "z1_foreign_official_treasury_level_usd_millions"
Z1_PRIVATE_LEVEL = "z1_foreign_private_treasury_level_usd_millions"
Z1_OFFICIAL_Q = "z1_foreign_official_treasury_transaction_q_usd_millions"
Z1_PRIVATE_Q = "z1_foreign_private_treasury_transaction_q_usd_millions"


def _fmt_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{value:,.1f}"


def _write_figures(panel: pd.DataFrame, figure_dir: Path, z1_panel: pd.DataFrame | None = None) -> list[Path]:
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

    if (
        z1_panel is not None
        and {Z1_OFFICIAL_LEVEL, Z1_PRIVATE_LEVEL}.issubset(z1_panel.columns)
        and {TIC_OFFICIAL, TIC_PRIVATE}.issubset(work.columns)
    ):
        z1 = z1_panel.copy()
        z1["quarter_date"] = pd.PeriodIndex(z1["quarter"].astype(str), freq="Q").to_timestamp(how="end")
        recent = work[work["month"] >= "2023-02"].copy()
        if not recent.empty:
            fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=False)
            axes[0].plot(z1["quarter_date"], z1[Z1_OFFICIAL_LEVEL] / 1_000, label="Foreign official stock")
            axes[0].plot(z1["quarter_date"], z1[Z1_PRIVATE_LEVEL] / 1_000, label="Foreign private stock")
            axes[0].set_title("ROW Treasury stock base")
            axes[0].set_ylabel("USD billions")
            axes[0].legend()
            axes[1].bar(recent["month_date"], recent[TIC_OFFICIAL], width=20, label="Official TIC flow")
            axes[1].bar(recent["month_date"], recent[TIC_PRIVATE], width=20, bottom=recent[TIC_OFFICIAL], label="Private TIC flow")
            axes[1].axhline(0, linewidth=0.8)
            axes[1].set_title("Recent marginal TIC absorption")
            axes[1].set_ylabel("USD millions")
            axes[1].legend()
            fig.autofmt_xdate()
            fig.tight_layout()
            path = figure_dir / "stock_vs_flow.svg"
            fig.savefig(path)
            plt.close(fig)
            written.append(path)

    return written


def _summarize_tic_window(panel: pd.DataFrame, label: str, mask: pd.Series) -> dict[str, object]:
    window = panel[mask].copy()
    row: dict[str, object] = {
        "sample": label,
        "frequency": "monthly",
        "rows": len(window),
        "start": window["month"].min() if not window.empty else "",
        "end": window["month"].max() if not window.empty else "",
        "official_flow_usd_millions": window[TIC_OFFICIAL].sum() if TIC_OFFICIAL in window.columns else pd.NA,
        "private_flow_usd_millions": window[TIC_PRIVATE].sum() if TIC_PRIVATE in window.columns else pd.NA,
        "iro_flow_usd_millions": window[TIC_IRO].sum() if TIC_IRO in window.columns else pd.NA,
        "official_plus_private_flow_usd_millions": window[TIC_TOTAL].sum() if TIC_TOTAL in window.columns else pd.NA,
        "official_private_iro_flow_usd_millions": window[TIC_TOTAL_WITH_IRO].sum() if TIC_TOTAL_WITH_IRO in window.columns else pd.NA,
    }
    if "tic_row_absorption_leader" in window.columns:
        counts = window["tic_row_absorption_leader"].value_counts()
        row["private_led_periods"] = int(counts.get("private_led", 0))
        row["official_led_periods"] = int(counts.get("official_led", 0))
        row["net_selling_or_no_absorption_periods"] = int(counts.get("net_selling_or_no_absorption", 0))
    return row


def _summarize_z1_window(z1_panel: pd.DataFrame, label: str, mask: pd.Series) -> dict[str, object]:
    window = z1_panel[mask].copy()
    row: dict[str, object] = {
        "sample": label,
        "frequency": "quarterly",
        "rows": len(window),
        "start": window["quarter"].min() if not window.empty else "",
        "end": window["quarter"].max() if not window.empty else "",
        "official_flow_usd_millions": window[Z1_OFFICIAL_Q].sum() if Z1_OFFICIAL_Q in window.columns else pd.NA,
        "private_flow_usd_millions": window[Z1_PRIVATE_Q].sum() if Z1_PRIVATE_Q in window.columns else pd.NA,
        "iro_flow_usd_millions": pd.NA,
        "official_plus_private_flow_usd_millions": window[Z1_TOTAL_Q].sum() if Z1_TOTAL_Q in window.columns else pd.NA,
        "official_private_iro_flow_usd_millions": pd.NA,
    }
    if "z1_row_absorption_leader" in window.columns:
        counts = window["z1_row_absorption_leader"].value_counts()
        row["private_led_periods"] = int(counts.get("private_led", 0))
        row["official_led_periods"] = int(counts.get("official_led", 0))
        row["net_selling_or_no_absorption_periods"] = int(counts.get("net_selling_or_no_absorption", 0))
    return row


def _write_results_tables(panel: pd.DataFrame, table_dir: Path, z1_panel: pd.DataFrame | None = None) -> list[Path]:
    ensure_parent(table_dir / "placeholder")
    rows = [
        _summarize_tic_window(panel, "TIC full stitched panel", panel["month"].notna()),
    ]
    if "tic_source_regime" in panel.columns:
        rows.append(_summarize_tic_window(panel, "TIC expanded SLT regime", panel["tic_source_regime"] == "expanded_slt_2023_on"))
        rows.append(_summarize_tic_window(panel, "TIC legacy long-term regime", panel["tic_source_regime"] == "legacy_s_form_pre_2023"))
    if z1_panel is not None and "quarter" in z1_panel.columns:
        rows.append(_summarize_z1_window(z1_panel, "Z.1 transaction panel", z1_panel["quarter"].notna()))
        rows.append(_summarize_z1_window(z1_panel, "Z.1 recent transaction window", z1_panel["quarter"] >= "2023Q1"))
    table = pd.DataFrame(rows)
    path = table_dir / "rowflow_results_summary.csv"
    table.to_csv(path, index=False)
    return [path]


def write_rowflow_report(
    panel_path: Path,
    output_md: Path,
    figure_dir: Path,
    z1_panel_path: Path | None = None,
    table_dir: Path | None = None,
) -> dict[str, object]:
    panel = read_csv_flexible(Path(panel_path))
    if panel.empty:
        raise ValueError("Cannot write report for empty rowflow panel")

    z1_panel = None
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

    figures = _write_figures(panel, Path(figure_dir), z1_panel)
    tables = _write_results_tables(panel, Path(table_dir or Path(figure_dir).parent / "tables"), z1_panel)
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

    lines = [
        "# rowflow accounting report",
        "",
        "This report is descriptive accounting only and does not identify causal domestic liquidity effects.",
        "",
        "## Scope",
        "",
        "The report splits rest-of-world Treasury absorption into foreign official and foreign private components, then joins those components to maturity and liquidity diagnostics. TIC and Z.1 are treated as complementary source definitions, not interchangeable measures.",
        "",
        "The central empirical distinction is stock versus flow: foreign official institutions remain a large Treasury stock holder base, while recent marginal ROW transaction absorption is mostly private-led.",
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
            "## Results tables",
            "",
        ]
    )
    for path in tables:
        lines.append(f"- `{path.name}`")

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
    return {"report": str(output_md), "figures": [str(path) for path in figures], "tables": [str(path) for path in tables]}
