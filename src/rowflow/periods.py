from __future__ import annotations

import pandas as pd


def normalize_month(series: pd.Series) -> pd.Series:
    periods = pd.to_datetime(series.astype(str), errors="coerce").dt.to_period("M")
    if periods.isna().any():
        bad = series[periods.isna()].head(5).tolist()
        raise ValueError(f"Could not parse month/date values: {bad}")
    return periods.astype(str)


def month_to_quarter(month: pd.Series) -> pd.Series:
    return pd.PeriodIndex(month.astype(str), freq="M").asfreq("Q").astype(str)


def normalize_quarter(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip()
    parsed = []
    for value in text:
        if "Q" in value.upper():
            parsed.append(str(pd.Period(value.upper().replace("-", ""), freq="Q")))
        else:
            parsed.append(str(pd.Timestamp(value).to_period("Q")))
    return pd.Series(parsed, index=series.index)


def quarter_to_month_end(quarter: pd.Series) -> pd.Series:
    return pd.PeriodIndex(quarter.astype(str), freq="Q").to_timestamp(how="end").normalize()
