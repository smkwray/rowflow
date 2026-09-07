from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from rowflow.io import sha256_file
from rowflow.z1_ledger import check_identity, load_archive, write_revision_bridge


def test_rounding_bound_is_source_precision_and_missing_is_not_zero() -> None:
    cells = {("2025Q1", "a"): {"value": 10, "rounding_increment": 1},
             ("2025Q1", "b"): {"value": 10.7, "rounding_increment": 1}}
    check = check_identity("rounded_equal", "2025Q1", {"a": 1, "b": -1}, cells)
    assert check["status"] == "pass"
    assert check["rounding_bound_usd_millions"] == 1
    cells[("2025Q1", "b")]["value"] = 12
    assert check_identity("not_equal", "2025Q1", {"a": 1, "b": -1}, cells)["status"] == "fail"
    assert check_identity("missing", "2025Q1", {"a": 1, "c": -1}, cells)["status"] == "missing_inputs"


def test_archive_checks_source_hash_and_rejects_duplicate_values(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_text("date,FU263061105.Q,FU263061105.Q\n2025:Q1,100,101\n")
    receipt = {"retained_files": [{"path": path.name, "sha256": sha256_file(path)}]}
    (tmp_path / "receipt.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="Contradictory source duplicate"):
        load_archive(tmp_path)
    path.write_text("date,FU263061105.Q\n2025:Q1,100\n")
    with pytest.raises(ValueError, match="Source hash mismatch"):
        load_archive(tmp_path)


def test_archive_retains_decimal_precision_and_missingness(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_text("date,FU263061105.Q\n2025:Q1,100.25\n2025:Q2,ND\n")
    (tmp_path / "receipt.json").write_text(json.dumps({"retained_files": [{"path": path.name, "sha256": sha256_file(path)}]}))
    values, _, _ = load_archive(tmp_path)
    assert values[("2025Q1", "FU263061105.Q")]["rounding_increment"] == 0.01
    assert values[("2025Q2", "FU263061105.Q")]["value"] is None


def test_revision_bridge_does_not_fill_absent_series(tmp_path: Path) -> None:
    old, new = tmp_path / "old", tmp_path / "new"
    old.mkdir()
    new.mkdir()
    columns = ["quarter", "series_id", "vintage", "value_usd_millions", "source_sha256"]
    pd.DataFrame([["2025Q1", "FU263061105.Q", "2026-03-19", 100, "old"],
                  ["2025Q1", "FU264123005.Q", "2026-03-19", 5, "old"]], columns=columns).to_csv(old / "ledger.csv", index=False)
    pd.DataFrame([["2025Q1", "FU263061105.Q", "2026-06-11", 110, "new"]], columns=columns).to_csv(new / "ledger.csv", index=False)
    bridge = write_revision_bridge(old, new, tmp_path / "bridge.csv")
    assert bridge.loc[bridge.series_id == "FU263061105.Q", "revision_usd_millions"].item() == 10
    absent = bridge.loc[bridge.series_id == "FU264123005.Q"].iloc[0]
    assert absent.comparison_status == "series_code_not_shared"
    assert pd.isna(absent.revision_usd_millions)
