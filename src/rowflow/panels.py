from __future__ import annotations

import re
from io import StringIO
from pathlib import Path

import pandas as pd

from rowflow.io import read_csv_flexible, read_fred_observations_json, read_text_source, write_csv
from rowflow.periods import month_to_quarter, normalize_month, normalize_quarter

TIC_OFFICIAL = "tic_foreign_official_treasury_net_flow_usd_millions"
TIC_PRIVATE = "tic_foreign_private_treasury_net_flow_usd_millions"
TIC_IRO = "tic_international_regional_organizations_treasury_net_flow_usd_millions"
TIC_TOTAL = "tic_foreign_total_treasury_net_flow_usd_millions"
TIC_TOTAL_WITH_IRO = "tic_foreign_total_with_iro_treasury_net_flow_usd_millions"
TIC_SOURCE_TOTAL = "tic_source_total_treasury_net_flow_usd_millions"
TIC_OFFICIAL_SHARE = "tic_foreign_official_share_of_net_flow"
TIC_PRIVATE_SHARE = "tic_foreign_private_share_of_net_flow"

Z1_OFFICIAL_Q = "z1_foreign_official_treasury_transaction_q_usd_millions"
Z1_PRIVATE_Q = "z1_foreign_private_treasury_transaction_q_usd_millions"
Z1_TOTAL_Q = "z1_foreign_total_treasury_transaction_q_usd_millions"
Z1_OFFICIAL_SHARE = "z1_foreign_official_share_of_transaction"
Z1_PRIVATE_SHARE = "z1_foreign_private_share_of_transaction"
Z1_OFFICIAL_LEVEL_CHANGE_Q = "z1_foreign_official_treasury_level_change_q_usd_millions"
Z1_PRIVATE_LEVEL_CHANGE_Q = "z1_foreign_private_treasury_level_change_q_usd_millions"
Z1_TOTAL_LEVEL_CHANGE_Q = "z1_foreign_total_treasury_level_change_q_usd_millions"
Z1_OFFICIAL_SHARE_LEVEL_CHANGE = "z1_foreign_official_share_of_level_change"
Z1_PRIVATE_SHARE_LEVEL_CHANGE = "z1_foreign_private_share_of_level_change"

TIC_OFFICIAL_ALIASES = [
    TIC_OFFICIAL,
    "foreign_official_treasury_net_flow_usd_millions",
    "official_treasury_net_flow_usd_millions",
    "foreign_official_treasury_purchases_usd_millions",
    "official_net_purchases_usd_millions",
]
TIC_PRIVATE_ALIASES = [
    TIC_PRIVATE,
    "foreign_private_treasury_net_flow_usd_millions",
    "private_treasury_net_flow_usd_millions",
    "foreign_private_treasury_purchases_usd_millions",
    "private_net_purchases_usd_millions",
]

Z1_OFFICIAL_SAAR_ALIASES = [
    "z1_foreign_official_treasury_transactions_saar_usd_millions",
    "BOGZ1FA263061130Q",
    "BOGZ1FU263061130Q",
]
Z1_PRIVATE_SAAR_ALIASES = [
    "z1_foreign_private_treasury_transactions_saar_usd_millions",
    "BOGZ1FA263061145Q",
    "BOGZ1FU263061145Q",
]
Z1_OFFICIAL_Q_ALIASES = [Z1_OFFICIAL_Q, "z1_official_transaction_q_usd_millions"]
Z1_PRIVATE_Q_ALIASES = [Z1_PRIVATE_Q, "z1_private_transaction_q_usd_millions"]
Z1_OFFICIAL_LEVEL_ALIASES = [
    "z1_foreign_official_treasury_level_usd_millions",
    "BOGZ1FL263061130Q",
]
Z1_PRIVATE_LEVEL_ALIASES = [
    "z1_foreign_private_treasury_level_usd_millions",
    "BOGZ1FL263061145Q",
]
Z1_FRED_TRANSACTION_SERIES = {
    "BOGZ1FU263061130Q": "official",
    "BOGZ1FU263061145Q": "private",
    "BOGZ1FL263061130Q": "official_level",
    "BOGZ1FL263061145Q": "private_level",
}
FRED_GRAPH_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"


def _first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    return None


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.replace({"n.a.": None, "NA": None, "": None}), errors="coerce")


def _safe_share(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.where(denominator != 0) / denominator.where(denominator != 0)


def _leader(official: float, private: float, total: float) -> str:
    if pd.isna(total) or total <= 0:
        return "net_selling_or_no_absorption"
    if official > 0 and private > 0:
        return "official_led" if official >= private else "private_led"
    if official > 0 >= private:
        return "official_led"
    if private > 0 >= official:
        return "private_led"
    return "mixed"


def _normalize_tic_from_slt_table3(df: pd.DataFrame) -> pd.DataFrame:
    required = {"country_code", "date", "for_treas_net"}
    if not required.issubset(df.columns):
        missing = sorted(required - set(df.columns))
        raise ValueError(f"SLT Table 3 input missing columns: {missing}")

    work = df.copy()
    work["country_code"] = pd.to_numeric(work["country_code"], errors="coerce").astype("Int64")
    sector_codes = [99990, 99991, 79995]
    work = work[work["country_code"].isin(sector_codes)].copy()
    if work.empty:
        raise ValueError("SLT Table 3 input did not contain sector rows 99990/99991/79995")

    metric_columns = ["for_treas_net", "for_lt_treas_net", "for_st_treas_net"]
    for column in metric_columns:
        if column in work.columns:
            work[column] = _numeric(work[column])

    frames: list[pd.DataFrame] = []
    mapping = {99990: "official", 99991: "private", 79995: "international_regional_organizations"}
    for code, label in mapping.items():
        subset = work[work["country_code"] == code].copy()
        if subset.empty:
            continue
        subset["month"] = normalize_month(subset["date"])
        if label == "international_regional_organizations":
            prefix = "tic_international_regional_organizations"
        else:
            prefix = f"tic_foreign_{label}"
        rename = {"for_treas_net": f"{prefix}_treasury_net_flow_usd_millions"}
        if "for_lt_treas_net" in subset.columns:
            rename["for_lt_treas_net"] = f"{prefix}_long_treasury_net_flow_usd_millions"
        if "for_st_treas_net" in subset.columns:
            rename["for_st_treas_net"] = f"{prefix}_short_treasury_net_flow_usd_millions"
        keep = ["month", *rename]
        frames.append(subset[keep].rename(columns=rename))

    if not frames:
        raise ValueError("SLT Table 3 input did not contain usable official/private/IRO sector rows")
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="month", how="outer")
    out["tic_source_regime"] = "expanded_slt_2023_on"
    out["tic_treasury_flow_scope"] = "total_treasuries"
    return out


def _normalize_tic_from_tressect_text(text: str) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    row_pattern = re.compile(
        r"^\s*(?P<month>\d{4}-\d{2})\s+"
        r"(?P<total>-?[\d,]+)\s+"
        r"(?P<official>-?[\d,]+)\s+"
        r"(?P<private>-?[\d,]+)\s+"
        r"(?P<iro>-?[\d,]+)\s*$"
    )
    for line in text.splitlines():
        match = row_pattern.match(line)
        if not match:
            continue
        rows.append(
            {
                "month": match.group("month"),
                TIC_SOURCE_TOTAL: match.group("total"),
                TIC_OFFICIAL: match.group("official"),
                TIC_PRIVATE: match.group("private"),
                TIC_IRO: match.group("iro"),
                "tic_source_regime": "legacy_s_form_pre_2023",
                "tic_treasury_flow_scope": "long_term_treasury_bonds_notes",
            }
        )
    if not rows:
        raise ValueError("Legacy TIC tressect input contained no monthly sector rows")
    out = pd.DataFrame(rows)
    for column in [TIC_SOURCE_TOTAL, TIC_OFFICIAL, TIC_PRIVATE, TIC_IRO]:
        out[column] = _numeric(out[column].astype(str).str.replace(",", "", regex=False))
    out["month"] = normalize_month(out["month"])
    return out


def _normalize_tic_wide(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    date_column = "month" if "month" in work.columns else "date" if "date" in work.columns else None
    if date_column is None:
        raise ValueError("TIC input must include a month or date column")
    official_column = _first_existing_column(work, TIC_OFFICIAL_ALIASES)
    private_column = _first_existing_column(work, TIC_PRIVATE_ALIASES)
    if official_column is None or private_column is None:
        raise ValueError("TIC input must include official and private Treasury flow columns")

    out = pd.DataFrame(
        {
            "month": normalize_month(work[date_column]),
            TIC_OFFICIAL: _numeric(work[official_column]),
            TIC_PRIVATE: _numeric(work[private_column]),
        }
    )
    for optional in (
        TIC_IRO,
        TIC_TOTAL_WITH_IRO,
        TIC_SOURCE_TOTAL,
        "tic_source_regime",
        "tic_treasury_flow_scope",
        "tic_foreign_official_long_treasury_net_flow_usd_millions",
        "tic_foreign_private_long_treasury_net_flow_usd_millions",
        "tic_international_regional_organizations_long_treasury_net_flow_usd_millions",
        "tic_foreign_official_short_treasury_net_flow_usd_millions",
        "tic_foreign_private_short_treasury_net_flow_usd_millions",
        "tic_international_regional_organizations_short_treasury_net_flow_usd_millions",
    ):
        if optional in work.columns:
            if optional in {"tic_source_regime", "tic_treasury_flow_scope"}:
                out[optional] = work[optional]
            else:
                out[optional] = _numeric(work[optional])
    return out


def build_tic_row_panel(input_path: Path, output_path: Path | None = None) -> pd.DataFrame:
    """Build the monthly TIC official/private ROW Treasury absorption panel."""
    text = read_text_source(input_path)
    normalized_text = text.upper().replace("&", "AND")
    if "INTERNATIONAL AND REGIONAL ORGANIZATIONS" in normalized_text and "FOREIGN OFFICIAL INSTITUTIONS" in normalized_text:
        out = _normalize_tic_from_tressect_text(text)
    else:
        df = read_csv_flexible(Path(input_path))
        if {"country_code", "date", "for_treas_net"}.issubset(df.columns):
            out = _normalize_tic_from_slt_table3(df)
        else:
            out = _normalize_tic_wide(df)

    out[TIC_OFFICIAL] = _numeric(out[TIC_OFFICIAL])
    out[TIC_PRIVATE] = _numeric(out[TIC_PRIVATE])
    if TIC_IRO in out.columns:
        out[TIC_IRO] = _numeric(out[TIC_IRO])
    out = out.dropna(subset=[TIC_OFFICIAL, TIC_PRIVATE], how="all").copy()
    out[TIC_TOTAL] = out[TIC_OFFICIAL] + out[TIC_PRIVATE]
    if TIC_IRO in out.columns:
        out[TIC_TOTAL_WITH_IRO] = out[TIC_TOTAL] + out[TIC_IRO].fillna(0)
    out[TIC_OFFICIAL_SHARE] = _safe_share(out[TIC_OFFICIAL], out[TIC_TOTAL])
    out[TIC_PRIVATE_SHARE] = _safe_share(out[TIC_PRIVATE], out[TIC_TOTAL])
    out["quarter"] = month_to_quarter(out["month"])
    out["tic_row_absorption_leader"] = [
        _leader(official, private, total)
        for official, private, total in zip(out[TIC_OFFICIAL], out[TIC_PRIVATE], out[TIC_TOTAL], strict=True)
    ]
    out = out.sort_values("month").reset_index(drop=True)
    cols = [
        "month",
        "quarter",
        TIC_OFFICIAL,
        TIC_PRIVATE,
        *( [TIC_IRO, TIC_TOTAL_WITH_IRO] if TIC_IRO in out.columns else [] ),
        TIC_TOTAL,
        TIC_OFFICIAL_SHARE,
        TIC_PRIVATE_SHARE,
        "tic_row_absorption_leader",
    ]
    optional_cols = [c for c in out.columns if c not in cols]
    out = out[cols + optional_cols]
    if output_path is not None:
        write_csv(out, Path(output_path))
    return out


def combine_tic_row_panels(input_paths: list[Path], output_path: Path | None = None) -> pd.DataFrame:
    """Combine monthly TIC panels, preferring later inputs for overlapping months."""
    frames = []
    for priority, input_path in enumerate(input_paths):
        frame = read_csv_flexible(Path(input_path)).copy()
        if "month" not in frame.columns:
            raise ValueError(f"TIC panel does not include month: {input_path}")
        frame["month"] = normalize_month(frame["month"])
        frame["_rowflow_source_priority"] = priority
        frames.append(frame)
    if not frames:
        raise ValueError("At least one TIC panel input is required")
    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined = combined.sort_values(["month", "_rowflow_source_priority"]).drop_duplicates(subset=["month"], keep="last")
    combined = combined.drop(columns=["_rowflow_source_priority"]).sort_values("month").reset_index(drop=True)
    if output_path is not None:
        write_csv(combined, Path(output_path))
    return combined


def build_z1_row_panel(
    input_path: Path,
    output_path: Path | None = None,
    transactions_are_saar: bool = True,
) -> pd.DataFrame:
    """Build quarterly Z.1 official/private ROW Treasury comparison panel."""
    df = read_csv_flexible(Path(input_path))
    work = df.copy()
    date_column = "quarter" if "quarter" in work.columns else "date" if "date" in work.columns else None
    if date_column is None:
        raise ValueError("Z.1 input must include a quarter or date column")

    official_q_col = _first_existing_column(work, Z1_OFFICIAL_Q_ALIASES)
    private_q_col = _first_existing_column(work, Z1_PRIVATE_Q_ALIASES)
    if official_q_col is not None and private_q_col is not None:
        official_q = _numeric(work[official_q_col])
        private_q = _numeric(work[private_q_col])
    else:
        official_saar_col = _first_existing_column(work, Z1_OFFICIAL_SAAR_ALIASES)
        private_saar_col = _first_existing_column(work, Z1_PRIVATE_SAAR_ALIASES)
        if official_saar_col is None or private_saar_col is None:
            raise ValueError("Z.1 input must include official/private transaction columns")
        uses_native_z1_transaction = official_saar_col.startswith("BOGZ1FU") and private_saar_col.startswith("BOGZ1FU")
        divisor = 1.0 if uses_native_z1_transaction or not transactions_are_saar else 4.0
        official_q = _numeric(work[official_saar_col]) / divisor
        private_q = _numeric(work[private_saar_col]) / divisor

    out = pd.DataFrame(
        {
            "quarter": normalize_quarter(work[date_column]),
            Z1_OFFICIAL_Q: official_q,
            Z1_PRIVATE_Q: private_q,
        }
    )
    official_level = _first_existing_column(work, Z1_OFFICIAL_LEVEL_ALIASES)
    private_level = _first_existing_column(work, Z1_PRIVATE_LEVEL_ALIASES)
    if official_level is not None:
        out["z1_foreign_official_treasury_level_usd_millions"] = _numeric(work[official_level])
    if private_level is not None:
        out["z1_foreign_private_treasury_level_usd_millions"] = _numeric(work[private_level])

    out = out.dropna(subset=[Z1_OFFICIAL_Q, Z1_PRIVATE_Q], how="all").copy()
    out[Z1_TOTAL_Q] = out[Z1_OFFICIAL_Q] + out[Z1_PRIVATE_Q]
    out[Z1_OFFICIAL_SHARE] = _safe_share(out[Z1_OFFICIAL_Q], out[Z1_TOTAL_Q])
    out[Z1_PRIVATE_SHARE] = _safe_share(out[Z1_PRIVATE_Q], out[Z1_TOTAL_Q])
    out["z1_row_absorption_leader"] = [
        _leader(official, private, total)
        for official, private, total in zip(out[Z1_OFFICIAL_Q], out[Z1_PRIVATE_Q], out[Z1_TOTAL_Q], strict=True)
    ]
    out = out.sort_values("quarter").reset_index(drop=True)
    if output_path is not None:
        write_csv(out, Path(output_path))
    return out


def download_z1_fred_transactions(output_path: Path, series_ids: list[str] | None = None) -> pd.DataFrame:
    """Download and merge public FRED graph CSVs for Z.1 transaction series."""
    selected = series_ids or list(Z1_FRED_TRANSACTION_SERIES)
    frames = []
    for series_id in selected:
        url = FRED_GRAPH_CSV_URL.format(series_id=series_id)
        frame = pd.read_csv(StringIO(read_text_source(url)))
        if "observation_date" in frame.columns:
            frame = frame.rename(columns={"observation_date": "date"})
        if "date" not in frame.columns or series_id not in frame.columns:
            raise ValueError(f"FRED graph CSV for {series_id} did not contain date and value columns")
        frames.append(frame[["date", series_id]])
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="date", how="outer")
    out = out.sort_values("date").reset_index(drop=True)
    write_csv(out, Path(output_path))
    return out


def build_z1_row_panel_from_fred_levels(
    official_level_json_path: Path,
    private_level_json_path: Path,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Build quarterly Z.1 official/private ROW panel from local FRED level JSONs.

    This fallback is an accounting context, not a transaction-flow source: flow-like
    comparison columns are labeled as level changes so they are not confused with
    Z.1 transaction series.
    """
    official = read_fred_observations_json(
        Path(official_level_json_path),
        "z1_foreign_official_treasury_level_usd_millions",
    )
    private = read_fred_observations_json(
        Path(private_level_json_path),
        "z1_foreign_private_treasury_level_usd_millions",
    )
    official["quarter"] = normalize_quarter(official["date"])
    private["quarter"] = normalize_quarter(private["date"])
    out = official.drop(columns=["date"]).merge(private.drop(columns=["date"]), on="quarter", how="outer")
    out = out.sort_values("quarter").reset_index(drop=True)
    out[Z1_OFFICIAL_LEVEL_CHANGE_Q] = out["z1_foreign_official_treasury_level_usd_millions"].diff()
    out[Z1_PRIVATE_LEVEL_CHANGE_Q] = out["z1_foreign_private_treasury_level_usd_millions"].diff()
    out[Z1_TOTAL_LEVEL_CHANGE_Q] = out[Z1_OFFICIAL_LEVEL_CHANGE_Q] + out[Z1_PRIVATE_LEVEL_CHANGE_Q]
    out[Z1_OFFICIAL_SHARE_LEVEL_CHANGE] = _safe_share(out[Z1_OFFICIAL_LEVEL_CHANGE_Q], out[Z1_TOTAL_LEVEL_CHANGE_Q])
    out[Z1_PRIVATE_SHARE_LEVEL_CHANGE] = _safe_share(out[Z1_PRIVATE_LEVEL_CHANGE_Q], out[Z1_TOTAL_LEVEL_CHANGE_Q])
    out["z1_row_level_change_leader"] = [
        _leader(official_change, private_change, total_change)
        for official_change, private_change, total_change in zip(
            out[Z1_OFFICIAL_LEVEL_CHANGE_Q],
            out[Z1_PRIVATE_LEVEL_CHANGE_Q],
            out[Z1_TOTAL_LEVEL_CHANGE_Q],
            strict=True,
        )
    ]
    out["z1_flow_measure"] = "level_change_from_fred_levels"
    if output_path is not None:
        write_csv(out, Path(output_path))
    return out


def _coalesce_numeric(df: pd.DataFrame, candidates: list[str]) -> pd.Series:
    result = pd.Series(pd.NA, index=df.index, dtype="Float64")
    for candidate in candidates:
        if candidate in df.columns:
            result = result.fillna(_numeric(df[candidate]))
    return result


def _normalize_diagnostics(input_path: Path) -> pd.DataFrame:
    diagnostics = read_csv_flexible(input_path)
    date_column = "month" if "month" in diagnostics.columns else "date" if "date" in diagnostics.columns else None
    if date_column is None:
        raise ValueError("Diagnostics input must include month or date")
    diagnostics = diagnostics.copy()
    out = pd.DataFrame({"month": normalize_month(diagnostics[date_column])})
    out["bill_share"] = _coalesce_numeric(diagnostics, ["bill_share", "bill_share_by_accepted_amount"])
    out["wam_years"] = _coalesce_numeric(diagnostics, ["wam_years", "weighted_maturity_years", "weighted_average_maturity_years"])
    out["tga_usd_millions"] = _coalesce_numeric(diagnostics, ["tga_usd_millions", "tga", "tga_wednesday", "tga_week_average"])
    out["reserves_usd_millions"] = _coalesce_numeric(diagnostics, ["reserves_usd_millions", "reserves"])
    out["deposits_usd_millions"] = _coalesce_numeric(diagnostics, ["deposits_usd_millions", "deposits", "domestic_deposits"])
    mmf_assets = _coalesce_numeric(diagnostics, ["mmf_assets_usd_millions", "total_mmf_assets", "mmf_assets"])
    if mmf_assets.isna().all() and {"retail_mmf_assets", "institutional_mmf_assets"}.issubset(diagnostics.columns):
        mmf_assets = _numeric(diagnostics["retail_mmf_assets"]) + _numeric(diagnostics["institutional_mmf_assets"])
    out["mmf_assets_usd_millions"] = mmf_assets
    out["on_rrp_usd_millions"] = _coalesce_numeric(diagnostics, ["on_rrp_usd_millions", "on_rrp"])
    return out.drop_duplicates(subset=["month"]).sort_values("month")


def _normalize_tdc_context(input_path: Path) -> pd.DataFrame:
    tdc = read_csv_flexible(input_path)
    date_column = "quarter" if "quarter" in tdc.columns else "date" if "date" in tdc.columns else None
    if date_column is None:
        raise ValueError("TDC context input must include quarter or date")
    tdc = tdc.copy()
    out = pd.DataFrame({"quarter": normalize_quarter(tdc[date_column])})
    out["tdc_bank_only_qoq_usd_millions"] = _coalesce_numeric(
        tdc,
        [
            "tdc_bank_only_qoq_usd_millions",
            "tdc_tier2_interest_corrected_bank_only_ru_flow",
            "tdc_tier2_bank_only_qoq",
            "tdc_bank_only_qoq",
            "tdc_base_bank_only_ru_flow",
        ],
    )
    out["tdc_tier2_interest_corrected_bank_only_qoq_usd_millions"] = _coalesce_numeric(
        tdc,
        [
            "tdc_tier2_interest_corrected_bank_only_qoq_usd_millions",
            "tdc_tier2_interest_corrected_bank_only_ru_flow",
            "tdc_tier2_bank_only_qoq",
        ],
    )
    out["tdc_source"] = "tdcest"
    if "tdc_source" in tdc.columns:
        out["tdc_source"] = tdc["tdc_source"].fillna("tdcest")
    return out.drop_duplicates(subset=["quarter"]).sort_values("quarter")


def build_rowflow_panel(
    tic_panel_path: Path,
    output_path: Path | None = None,
    z1_panel_path: Path | None = None,
    diagnostics_path: Path | None = None,
    tdc_context_path: Path | None = None,
) -> pd.DataFrame:
    """Merge TIC ROW flows with optional quarterly and diagnostic sidecars."""
    panel = read_csv_flexible(Path(tic_panel_path)).copy()
    if "month" not in panel.columns:
        raise ValueError("TIC panel must include month")
    panel["month"] = normalize_month(panel["month"])
    if "quarter" not in panel.columns:
        panel["quarter"] = month_to_quarter(panel["month"])

    if diagnostics_path is not None and Path(diagnostics_path).exists():
        diagnostics = _normalize_diagnostics(Path(diagnostics_path))
        panel = panel.merge(diagnostics, on="month", how="left")

    if z1_panel_path is not None and Path(z1_panel_path).exists():
        z1 = read_csv_flexible(Path(z1_panel_path)).copy()
        z1["quarter"] = normalize_quarter(z1["quarter"])
        panel = panel.merge(z1, on="quarter", how="left", suffixes=("", "_z1"))

    if tdc_context_path is not None and Path(tdc_context_path).exists():
        tdc = _normalize_tdc_context(Path(tdc_context_path))
        panel = panel.merge(tdc, on="quarter", how="left", suffixes=("", "_tdc"))

    if TIC_TOTAL in panel.columns:
        panel["tic_quarterly_foreign_total_treasury_net_flow_usd_millions"] = panel.groupby("quarter")[TIC_TOTAL].transform("sum")
    if TIC_OFFICIAL in panel.columns:
        panel["tic_quarterly_foreign_official_treasury_net_flow_usd_millions"] = panel.groupby("quarter")[TIC_OFFICIAL].transform("sum")
    if TIC_PRIVATE in panel.columns:
        panel["tic_quarterly_foreign_private_treasury_net_flow_usd_millions"] = panel.groupby("quarter")[TIC_PRIVATE].transform("sum")
    if Z1_TOTAL_Q in panel.columns:
        panel["tic_minus_z1_total_quarterly_flow_gap_usd_millions"] = (
            panel.get("tic_quarterly_foreign_total_treasury_net_flow_usd_millions") - panel[Z1_TOTAL_Q]
        )

    panel = panel.sort_values("month").reset_index(drop=True)
    if output_path is not None:
        write_csv(panel, Path(output_path))
    return panel
