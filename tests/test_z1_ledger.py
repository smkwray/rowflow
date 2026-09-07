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


@pytest.mark.parametrize("vintage", ["2026-03-19", "2026-06-11"])
def test_every_leaf_and_quarter_remains_visible_when_stock_inputs_missing(tmp_path: Path, monkeypatch, vintage) -> None:
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
    monkeypatch.setattr(ledger, "load_archive", lambda root: (cells, metadata, {"vintage": vintage, "archive_sha256": "fixture"}))
    (tmp_path / "data_dictionary").mkdir()
    (tmp_path / "data_dictionary" / (spec["ledger_tables"][vintage] + ".txt")).write_text("\n".join(series))
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
    assert summary["transaction_ledger_admissible"] is True
    assert summary["stock_source_consistency"] == "unavailable"
    assert summary["independent_stock_validation"] == "unavailable"
    assert summary["recent_external_position_change_check"] == "not_run_in_ledger_build"
    assert "certified" not in summary and "full_item3_certified" not in summary
    assert "independent_treasury_reconstruction" not in summary["checks"]
    spec["sample_end"] = "2025Q3"
    short_spec = tmp_path / "short.yml"
    short_spec.write_text(yaml.safe_dump(spec))
    short = ledger.build_ledger(tmp_path, short_spec, tmp_path / "short")
    assert short["transaction_checks_passed"] is True
    assert short["transaction_ledger_admissible"] is False  # The 96-quarter inventory is required.


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


@pytest.mark.parametrize("code", ["313011303", "263192305"])
@pytest.mark.parametrize("vintage,prefix", [("2026-03-19", "LM"), ("2026-06-11", "FL")])
def test_stock_mapping_uses_declared_vintage_even_when_both_prefixes_exist(code, vintage, prefix):
    import yaml

    from rowflow.z1_ledger import _stock_bridge, _stock_contracts_for_vintage

    spec = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/row_ledger.yml").read_text())
    contract = _stock_contracts_for_vintage(spec, vintage)[code]
    assert contract["level_series"] == prefix + code + ".Q"
    cells = {}
    for quarter, value in [("2024Q4", 10), ("2025Q1", 12)]:
        for candidate in ["FL", "LM"]:
            cells[(quarter, candidate + code + ".Q")] = {
                "value": value if candidate == prefix else value * 100,
                "rounding_increment": 0.01,
            }
    for candidate, value in [("FU", 2), ("FR", 0), ("FV", 0)]:
        cells[("2025Q1", candidate + code + ".Q")] = {"value": value, "rounding_increment": 0.01}
    row = _stock_bridge(code, "2025Q1", contract, cells)
    assert row["level_inputs_available"] is True
    assert row["gap_usd_millions"] == 0
    assert row["source_consistency_status"] == "pass"
    assert row["status"] == "unavailable"  # Unknown adjustment derivation is not independent evidence.
    del cells[("2025Q1", prefix + code + ".Q")]
    missing = _stock_bridge(code, "2025Q1", contract, cells)
    assert missing["level_inputs_available"] is False
    assert missing["status"] == "missing_inputs"  # Never substitute the other prefix.


@pytest.mark.parametrize("mutation", ["missing_vintage", "unknown_vintage", "cross_code"])
def test_stock_mapping_rejects_undeclared_vintage_or_cross_code(mutation):
    import yaml

    from rowflow.z1_ledger import _stock_contracts_for_vintage

    spec = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/row_ledger.yml").read_text())
    vintage = "2026-03-19"
    if mutation == "missing_vintage":
        del spec["stock_contracts"]["313011303"]["level_series_by_vintage"][vintage]
    elif mutation == "cross_code":
        spec["stock_contracts"]["263011105"]["level_series_by_vintage"][vintage] = "LM313111303.Q"
    else:
        vintage = "2026-09-11"
    with pytest.raises(ValueError):
        _stock_contracts_for_vintage(spec, vintage)


def test_sdr_allocation_stock_does_not_silently_fill_broader_gold_sdr_leaf():
    import yaml

    from rowflow.z1_ledger import _stock_bridge, _stock_contracts_for_vintage

    spec = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/row_ledger.yml").read_text())
    contract = _stock_contracts_for_vintage(spec, "2026-03-19")["263011105"]
    cells = {(quarter, series): {"value": 0, "rounding_increment": 1}
             for quarter in ["2024Q4", "2025Q1"]
             for series in ["LM313111303.Q", "FL313111303.Q", "FU263011105.Q", "FR263011105.Q", "FV263011105.Q"]}
    row = _stock_bridge("263011105", "2025Q1", contract, cells)
    assert row["level_series"] is None
    assert row["level_inputs_available"] is False
    assert row["status"] == "missing_inputs"
    assert row["gap_usd_millions"] is None
    assert "excludes monetary gold" in row["mapping_source"]


@pytest.mark.parametrize("gate,expected", [("transaction_ledger_admissible", 0), ("stock_source_consistency", 1), ("independent_stock_validation", 1)])
def test_cli_exit_uses_requested_gate(monkeypatch, gate, expected):
    import rowflow.cli as cli

    monkeypatch.setattr(cli, "build_ledger", lambda *args: {
        "transaction_ledger_admissible": True, "stock_source_consistency": "unavailable",
        "independent_stock_validation": "unavailable"})
    assert cli.main(["build-z1-ledger", "--input", "fixture", "--output", "fixture", "--gate", gate]) == expected


def test_failed_transaction_gate_is_not_rescued_by_passing_stock_check():
    from rowflow.z1_ledger import ledger_gate_passed

    assert not ledger_gate_passed({"transaction_ledger_admissible": False, "stock_source_consistency": "pass"}, "transaction_ledger_admissible")


def test_gold_sdr_composite_never_fills_missing_component_or_authenticates_alias():
    from rowflow.z1_ledger import gold_sdr_source_consistency

    q = "2025Q1"
    values = {(q, s): {"value": v, "rounding_increment": 1} for s, v in
              [("FU263011105.Q", 7), ("FU263011205.Q", 2), ("FU313111303.Q", 5), ("LM313111303.Q", 100)]}
    metadata = {s: {"units": "Millions of dollars; transactions, not seasonally adjusted"} for _, s in values}
    metadata["LM313111303.Q"]["units"] = "Millions of dollars; amounts outstanding end of period, market value, not seasonally adjusted"
    row = gold_sdr_source_consistency([q], values, metadata)[0]
    assert row["status"] == "pass"
    assert row["dated_level_alias_status"] == "unestablished"
    assert row["independent_stock_validation"] == "unavailable"
    assert row["previous_level_candidate_value"] is None
    del values[(q, "FU263011205.Q")]
    missing = gold_sdr_source_consistency([q], values, metadata)[0]
    assert missing["status"] == "missing_inputs" and missing["gap_usd_millions"] is None
    with pytest.raises(ValueError, match="units differ"):
        gold_sdr_source_consistency([q], values, {"LM313111303.Q": {"units": "billions"}})
