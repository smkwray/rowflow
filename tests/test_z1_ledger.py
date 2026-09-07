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


def test_every_leaf_and_quarter_remains_visible_when_stock_inputs_missing(tmp_path: Path, monkeypatch) -> None:
    import yaml

    import rowflow.z1_ledger as ledger

    spec_path = Path(__file__).resolve().parents[1] / "config/row_ledger.yml"
    spec = yaml.safe_load(spec_path.read_text())
    leaves = spec["asset_leaves"] + spec["liability_leaves"] + spec["equity_leaves"]
    codes = set(leaves + list(spec["totals"].values()) + list(spec["resources"].values())
                + list(spec["subtotals"].values()) + [d["code"] for d in spec["deposit_series"].values()])
    series = ["FU" + c + ".Q" for c in codes]
    quarters = pd.period_range(spec["sample_start"], spec["sample_end"], freq="Q").astype(str)
    cells = {(q, s): {"value": 0, "rounding_increment": 1, "raw": "0", "source_sha256": "fixture"}
             for q in quarters for s in series}
    metadata = {s: {"description": "fixture", "units": "Millions of dollars; transactions, not seasonally adjusted"} for s in series}
    monkeypatch.setattr(ledger, "load_archive", lambda root: (cells, metadata, {"vintage": "2026-03-19", "archive_sha256": "fixture"}))
    (tmp_path / "data_dictionary").mkdir()
    (tmp_path / "data_dictionary/fu133.txt").write_text("\n".join(series))
    (tmp_path / "receipt.json").write_text("{}")
    summary = ledger.build_ledger(tmp_path, spec_path, tmp_path / "out")
    stock = pd.read_csv(tmp_path / "out/stock_bridges.csv", dtype={"leaf_code": str})
    assert len(stock) == 36 * 96
    assert stock.groupby("leaf_code").size().eq(96).all()
    assert stock.loc[stock.leaf_code.eq("263011105"), "missing_series"].str.contains("unmapped_level:263011105").all()
    assert stock.other_volume_provenance.eq("missing").all()
    assert summary["transaction_checks_passed"] is True
    assert summary["stock_expected_leaves"] == 36
    assert summary["stock_complete_leaves"] == 0
    assert summary["stock_certification"] == "unavailable"
    assert summary["full_item3_certified"] is summary["certified"] is False
    assert "independent_treasury_reconstruction" not in summary["checks"]


def test_stock_bridge_never_falls_back_or_certifies_residual_adjustments() -> None:
    from rowflow.z1_ledger import _stock_bridge

    code = "263061105"
    contract = {"level_series": "LM263061105.Q", "valuation_basis": "fixture matched basis",
                "mapping_source": "fixture", "revaluation_series": "FR263061105.Q",
                "revaluation_derivation": "fed_computed_residual", "other_volume_series": "FV263061105.Q",
                "other_volume_derivation": "fed_computed_residual"}
    cell = {"value": 0, "rounding_increment": 1, "source_sha256": "fixture"}
    cells = {(q, p + code + ".Q"): cell for q in ["2024Q4", "2025Q1"] for p in ["FL", "FU", "FR", "FV"]}
    missing = _stock_bridge(code, "2025Q1", contract, cells)
    assert missing["status"] == "missing_inputs"
    assert "LM263061105.Q" in missing["missing_series"]
    assert missing["gap_usd_millions"] is None
    cells.update({(q, "LM" + code + ".Q"): cell for q in ["2024Q4", "2025Q1"]})
    present = _stock_bridge(code, "2025Q1", contract, cells)
    assert present["source_consistency_status"] == "pass"
    assert present["status"] == "unavailable"
    assert present["independent_stock_check_available"] is False
    del cells[("2025Q1", "FV263061105.Q")]
    absent = _stock_bridge(code, "2025Q1", contract, cells)
    assert absent["other_volume_provenance"] == "missing"
    assert absent["other_volume_value_usd_millions"] is None
    assert absent["gap_usd_millions"] is None
