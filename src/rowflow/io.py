from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

import pandas as pd


def ensure_parent(path: Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def read_csv_flexible(path: Path) -> pd.DataFrame:
    """Read CSV/TSV/TXT inputs with a small amount of format tolerance."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".tsv", ".txt"}:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        for row_number, line in enumerate(lines):
            normalized = line.strip().lower()
            if normalized.startswith("country\tcountry_code\tdate"):
                return pd.read_csv(path, sep="\t", skiprows=row_number)
        return pd.read_csv(path, sep=None, engine="python")
    return pd.read_csv(path)


def read_fred_observations_json(path: Path, value_name: str) -> pd.DataFrame:
    """Read a FRED observations JSON payload into date/value columns."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    observations = payload.get("observations") if isinstance(payload, dict) else payload
    if not isinstance(observations, list):
        raise ValueError(f"FRED JSON input does not contain an observations list: {path}")
    rows = []
    for observation in observations:
        rows.append(
            {
                "date": observation.get("date"),
                value_name: observation.get("value"),
            }
        )
    out = pd.DataFrame(rows)
    if out.empty:
        raise ValueError(f"FRED JSON input contains no observations: {path}")
    out[value_name] = pd.to_numeric(out[value_name].replace({".": None, "": None}), errors="coerce")
    return out


def write_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_parent(path)
    df.to_csv(path, index=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_existing_files(paths: Iterable[Path]) -> list[Path]:
    return [Path(path) for path in paths if Path(path).exists() and Path(path).is_file()]
