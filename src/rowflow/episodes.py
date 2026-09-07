from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from rowflow.io import read_csv_flexible, write_csv
from rowflow.panels import (
    TIC_IRO,
    TIC_OFFICIAL,
    TIC_PRIVATE,
    TIC_TOTAL,
    TIC_TOTAL_WITH_IRO,
    Z1_OFFICIAL_Q,
    Z1_PRIVATE_Q,
    Z1_TOTAL_Q,
)

FLOW_DENOMINATORS = {
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
}
STOCK_DENOMINATORS = {
    "marketable_debt": [
        "marketable_debt_usd_millions",
        "marketable_debt_outstanding_usd_millions",
        "marketable_treasury_debt_outstanding_usd_millions",
    ],
}


def load_episodes(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    episodes = payload.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("episodes.yml must contain a non-empty episodes list")
    return episodes


def _first_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _numeric_sum(df: pd.DataFrame, column: str) -> float | pd._libs.missing.NAType:
    if column not in df.columns:
        return pd.NA
    values = _numeric_values(df, column)
    return values.sum(min_count=1) if len(values) and values.notna().all() else pd.NA


def _numeric_values(df: pd.DataFrame, column: str) -> pd.Series:
    values = df[column] if column in df else pd.Series(index=df.index, dtype=float)
    return pd.to_numeric(values, errors="coerce").replace([float("inf"), -float("inf")], float("nan"))


def _complete_window(window: pd.DataFrame, episode: dict, column: str, freq: str) -> pd.DataFrame:
    """Materialize every expected period so omissions cannot become partial totals."""
    window = window.copy()
    window[column] = pd.PeriodIndex(window[column], freq=freq).astype(str)
    if window[column].duplicated().any():
        raise ValueError("Duplicate episode periods")
    start = episode.get("start") or (window[column].min() if len(window) else None)
    end = episode.get("end") or (window[column].max() if len(window) else None)
    if start is None or end is None:
        return window
    expected = pd.period_range(start, end, freq=freq).astype(str)
    return window.set_index(column).reindex(expected).rename_axis(column).reset_index()


def _coverage(row: dict, window: pd.DataFrame, columns: list[str]) -> None:
    row["n_expected"] = len(window)
    valid = pd.Series(True, index=window.index)
    for column in columns:
        count = int(_numeric_values(window, column).notna().sum())
        row[column + "_n_valid"] = count
        valid &= _numeric_values(window, column).notna()
    row["n_valid"] = int(valid.sum())
    row["n_observed"] = row["rows"]
    row["coverage_status"] = "complete" if len(window) and row["n_valid"] == len(window) else "incomplete"


def _period_mask(df: pd.DataFrame, column: str, start: str | None, end: str | None) -> pd.Series:
    mask = df[column].notna()
    if start is not None:
        mask &= df[column].astype(str) >= str(start)
    if end is not None:
        mask &= df[column].astype(str) <= str(end)
    return mask


def _safe_share(numerator: object, denominator: object) -> object:
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return pd.NA
    return float(numerator) / float(denominator)


def _add_denominator_columns(row: dict[str, object], window: pd.DataFrame) -> None:
    statuses: list[str] = []
    numerators = {
        "official": row["official_absorption_usd_millions"],
        "private": row["private_absorption_usd_millions"],
        "official_private": row["official_private_absorption_usd_millions"],
        "official_private_iro": row["official_private_iro_absorption_usd_millions"],
    }
    for denominator_name, candidates in FLOW_DENOMINATORS.items():
        column = _first_column(window, candidates)
        denominator = _numeric_sum(window, column) if column else pd.NA
        row[f"{denominator_name}_n_valid"] = int(_numeric_values(window, column).notna().sum()) if column else 0
        row[f"{denominator_name}_denominator_usd_millions"] = denominator
        for name, value in numerators.items():
            row[f"{name}_share_of_{denominator_name}"] = _safe_share(value, denominator)
        statuses.append(f"{denominator_name}:{column or 'unavailable'}")

    for denominator_name, candidates in STOCK_DENOMINATORS.items():
        column = _first_column(window, candidates)
        if column:
            values = _numeric_values(window, column)
            denominator = values.iloc[-1] if len(values) and values.notna().all() else pd.NA
        else:
            denominator = pd.NA
        row[f"{denominator_name}_n_valid"] = int(_numeric_values(window, column).notna().sum()) if column else 0
        row[f"{denominator_name}_denominator_usd_millions"] = denominator
        for name, value in numerators.items():
            row[f"{name}_share_of_{denominator_name}"] = _safe_share(value, denominator)
        statuses.append(f"{denominator_name}:{column or 'unavailable'}")
    row["denominator_status"] = "; ".join(statuses)


def _leader_counts(window: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in window.columns:
        return {}
    counts = window[column].value_counts()
    return {
        "official_led_periods": int(counts.get("official_led", 0)),
        "private_led_periods": int(counts.get("private_led", 0)),
        "net_selling_or_no_absorption_periods": int(counts.get("net_selling_or_no_absorption", 0)),
    }


def _tic_episode_row(panel: pd.DataFrame, episode: dict[str, Any]) -> dict[str, object]:
    mask = _period_mask(panel, "month", episode.get("start"), episode.get("end"))
    if episode.get("source_regime") and "tic_source_regime" in panel.columns:
        mask &= panel["tic_source_regime"].astype(str) == str(episode["source_regime"])
    elif episode.get("source_regime"):
        mask &= False
    if episode.get("flow_scope") and "tic_treasury_flow_scope" in panel.columns:
        mask &= panel["tic_treasury_flow_scope"].astype(str) == str(episode["flow_scope"])
    elif episode.get("flow_scope"):
        mask &= False
    selected = panel[mask]
    window = _complete_window(selected, episode, "month", "M")
    row: dict[str, object] = {
        "episode_id": episode["id"],
        "label": episode.get("label", episode["id"]),
        "source_family": "tic",
        "frequency": "monthly",
        "sample_start": selected["month"].min() if not selected.empty else "",
        "sample_end": selected["month"].max() if not selected.empty else "",
        "rows": len(selected),
        "source_regime": episode.get("source_regime") or "mixed_or_unrestricted",
        "flow_scope": episode.get("flow_scope") or "mixed_or_unrestricted",
        "transaction_or_position_concept": "TIC monthly source-defined net Treasury flow",
        "official_absorption_usd_millions": _numeric_sum(window, TIC_OFFICIAL),
        "private_absorption_usd_millions": _numeric_sum(window, TIC_PRIVATE),
        "iro_absorption_usd_millions": _numeric_sum(window, TIC_IRO),
        "official_private_absorption_usd_millions": _numeric_sum(window, TIC_TOTAL),
        "official_private_iro_absorption_usd_millions": _numeric_sum(window, TIC_TOTAL_WITH_IRO),
        "required_caveat": episode.get("required_caveat", ""),
    }
    _coverage(row, window, [TIC_OFFICIAL, TIC_PRIVATE, TIC_TOTAL, TIC_IRO, TIC_TOTAL_WITH_IRO])
    row.update(_leader_counts(window, "tic_row_absorption_leader"))
    _add_denominator_columns(row, window)
    return row


def _z1_episode_row(z1_panel: pd.DataFrame, episode: dict[str, Any]) -> dict[str, object]:
    mask = _period_mask(z1_panel, "quarter", episode.get("start"), episode.get("end"))
    selected = z1_panel[mask]
    window = _complete_window(selected, episode, "quarter", "Q")
    row: dict[str, object] = {
        "episode_id": episode["id"],
        "label": episode.get("label", episode["id"]),
        "source_family": "z1",
        "frequency": "quarterly",
        "sample_start": selected["quarter"].min() if not selected.empty else "",
        "sample_end": selected["quarter"].max() if not selected.empty else "",
        "rows": len(selected),
        "source_regime": "z1",
        "flow_scope": "treasury_securities",
        "transaction_or_position_concept": "Z.1 quarterly FU transactions",
        "official_absorption_usd_millions": _numeric_sum(window, Z1_OFFICIAL_Q),
        "private_absorption_usd_millions": _numeric_sum(window, Z1_PRIVATE_Q),
        "iro_absorption_usd_millions": pd.NA,
        "official_private_absorption_usd_millions": _numeric_sum(window, Z1_TOTAL_Q),
        "official_private_iro_absorption_usd_millions": pd.NA,
        "required_caveat": episode.get("required_caveat", ""),
    }
    _coverage(row, window, [Z1_OFFICIAL_Q, Z1_PRIVATE_Q, Z1_TOTAL_Q])
    row.update(_leader_counts(window, "z1_row_absorption_leader"))
    _add_denominator_columns(row, window)
    return row


def build_episode_absorption(
    panel_path: Path,
    z1_panel_path: Path,
    episodes_path: Path,
) -> pd.DataFrame:
    panel = read_csv_flexible(Path(panel_path))
    z1_panel = read_csv_flexible(Path(z1_panel_path))
    episodes = load_episodes(Path(episodes_path))

    rows = []
    for episode in episodes:
        source = episode.get("source")
        if source == "tic":
            rows.append(_tic_episode_row(panel, episode))
        elif source == "z1":
            rows.append(_z1_episode_row(z1_panel, episode))
    return pd.DataFrame(rows)


def write_episode_absorption(
    panel_path: Path,
    z1_panel_path: Path,
    episodes_path: Path,
    output_path: Path,
) -> pd.DataFrame:
    table = build_episode_absorption(panel_path, z1_panel_path, episodes_path)
    write_csv(table, Path(output_path))
    return table
