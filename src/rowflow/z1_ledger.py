"""Dated, unadjusted ROW sources-and-uses ledger with explicit failed checks."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from rowflow.io import sha256_file, write_csv


def load_archive(root: Path) -> tuple[dict, dict, dict]:
    """Verify the receipt and retain source precision; reject contradictory duplicates."""
    receipt = json.loads((root / "receipt.json").read_text())
    values, metadata = {}, {}
    for item in receipt["retained_files"]:
        path = root / item["path"]
        if sha256_file(path) != item["sha256"]:
            raise ValueError(f"Source hash mismatch: {path}")
        if path.suffix == ".txt":
            for row in csv.reader(path.read_text().splitlines(), delimiter="\t"):
                if len(row) < 5 or not re.fullmatch(r"[A-Z]{2}\d{9}\.Q", row[0]):
                    continue
                metadata.setdefault(row[0], {"description": row[1], "units": row[4]})
        elif path.suffix == ".csv":
            rows = csv.reader(path.read_text().splitlines())
            columns = next(rows)
            for row in rows:
                quarter = row[0].replace(":", "")
                for series, raw in zip(columns[1:], row[1:], strict=True):
                    if not re.fullmatch(r"[A-Z]{2}\d{9}\.Q", series):
                        continue
                    key = (quarter, series)
                    try:
                        number = Decimal(raw)
                    except InvalidOperation:
                        number = None
                    if number is not None and not number.is_finite():
                        raise ValueError(f"Nonfinite numeric source value: {key}")
                    delta = float(Decimal(10) ** number.as_tuple().exponent) if number is not None else None
                    cell = {"value": float(number) if number is not None else None,
                            "rounding_increment": delta, "raw": raw,
                            "source_file": item["path"], "source_sha256": item["sha256"]}
                    if key in values and values[key]["raw"] != raw:
                        raise ValueError(f"Contradictory source duplicate: {key}")
                    values.setdefault(key, cell)
    sidecar_root = root / "alfred"
    if (sidecar_root / "receipt.json").exists():
        supplemental = json.loads((sidecar_root / "receipt.json").read_text())
        if supplemental["vintage"] != receipt["vintage"]:
            raise ValueError("Supplemental vintage mismatch")
        for item in supplemental["retained_files"]:
            path = sidecar_root / item["path"]
            if sha256_file(path) != item["sha256"]:
                raise ValueError(f"Source hash mismatch: {path}")
            series = item["series_id"].removeprefix("BOGZ1")[:-1] + ".Q"
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
            expected = item["series_id"] + "_" + receipt["vintage"].replace("-", "")
            if list(frame.columns) != ["observation_date", expected]:
                raise ValueError("Supplemental series/vintage header mismatch")
            for date, raw in frame.itertuples(index=False, name=None):
                quarter = str(pd.Period(date, freq="Q"))
                number = None if raw == "." else Decimal(raw)
                cell = {"value": float(number) if number is not None else None, "raw": raw,
                        "rounding_increment": float(Decimal(10) ** number.as_tuple().exponent) if number is not None else None,
                        "source_file": "alfred/" + item["path"], "source_sha256": item["sha256"]}
                key = (quarter, series)
                if key in values and values[key]["raw"] != raw:
                    raise ValueError(f"Archive and ALFRED vintage disagree: {key}")
                values.setdefault(key, cell)
    return values, metadata, receipt


def check_identity(name: str, quarter: str, terms: dict[str, float], values: dict) -> dict:
    """Each independent rounded input contributes its own half-increment bound."""
    cells = [(coefficient, values.get((quarter, series))) for series, coefficient in terms.items()]
    missing = [series for series in terms if values.get((quarter, series), {}).get("value") is None]
    result = {"quarter": quarter, "check": name, "gap_usd_millions": None,
              "rounding_bound_usd_millions": None, "fp_allowance_usd_millions": None,
              "bound_usd_millions": None, "missing_series": ";".join(missing)}
    if missing:
        return result | {"status": "missing_inputs"}
    gap = sum(a * cell["value"] for a, cell in cells)
    rounding = 0.5 * sum(abs(a) * cell["rounding_increment"] for a, cell in cells)
    # Conservative forward error allowance for this short sum, declared before evaluation.
    fp = 8 * np.finfo(float).eps * max(1, len(cells)) * max(1, sum(abs(a * cell["value"]) for a, cell in cells))
    return result | {"gap_usd_millions": gap, "rounding_bound_usd_millions": rounding,
                     "fp_allowance_usd_millions": fp, "bound_usd_millions": rounding + fp,
                     "status": "pass" if abs(gap) <= rounding + fp else "fail"}


def _terms(*blocks: tuple[list[str], float]) -> dict[str, float]:
    coefficients = Counter()
    for codes, coefficient in blocks:
        for code in codes:
            coefficients[f"FU{code}.Q"] += coefficient
    return {series: value for series, value in coefficients.items() if value}


def _stock_contracts_for_vintage(spec: dict, vintage: str) -> dict:
    """Resolve only the declared dated identifiers; never substitute another prefix."""
    if vintage not in spec["ledger_tables"]:
        raise ValueError(f"Unsupported stock mapping vintage: {vintage}")
    contracts = spec["stock_contracts"]
    resolved = {}
    for code, contract in contracts.items():
        for field in ["level_series_by_vintage", "valuation_basis", "mapping_source", "revaluation_series",
                      "revaluation_derivation", "other_volume_series", "other_volume_derivation"]:
            if field not in contract or not contract[field]:
                raise ValueError(f"Missing stock contract field: {code} {field}")
        levels = contract["level_series_by_vintage"]
        if not isinstance(levels, dict) or set(levels) != set(spec["ledger_tables"]):
            raise ValueError(f"Stock level mapping must name every supported vintage: {code}")
        if any(level is not None and (not isinstance(level, str) or not re.fullmatch(r"(?:FL|LM)" + code + r"\.Q", level))
               for level in levels.values()):
            raise ValueError(f"Invalid explicit stock level series: {code}")
        for name, prefix in [("revaluation", "FR"), ("other_volume", "FV")]:
            if contract[name + "_series"] != prefix + code + ".Q":
                raise ValueError(f"Invalid leaf adjustment series: {code}")
            if contract[name + "_derivation"] not in {"unestablished", "fed_computed_residual", "independently_source_derived"}:
                raise ValueError(f"Invalid adjustment provenance: {code}")
        resolved[code] = contract | {"level_series": levels[vintage]}
    return resolved


def _stock_bridge(code: str, quarter: str, contract: dict, values: dict) -> dict:
    level = contract["level_series"]
    previous = str(pd.Period(quarter, freq="Q") - 1)
    level_key = level or "unmapped_level:" + code
    previous_key = level_key + "@" + previous
    fr, fv = contract["revaluation_series"], contract["other_volume_series"]
    terms = {level_key: 1, previous_key: -1, "FU" + code + ".Q": -1, fr: -1, fv: -1}
    expanded = {(quarter, series): values[(quarter, series)] for series in terms if (quarter, series) in values}
    if level and (previous, level) in values:
        expanded[(quarter, previous_key)] = values[(previous, level)]
    result = check_identity("stock_bridge_" + code, quarter, terms, expanded)
    result.update({"leaf_code": code, "level_series": level, "previous_quarter": previous,
                   "level_inputs_available": all(expanded.get((quarter, key), {}).get("value") is not None for key in [level_key, previous_key]),
                   "valuation_basis": contract["valuation_basis"], "mapping_source": contract["mapping_source"],
                   "source_consistency_status": result["status"]})
    for name, series in [("revaluation", fr), ("other_volume", fv)]:
        cell = values.get((quarter, series), {})
        result.update({name + "_series": series, name + "_value_usd_millions": cell.get("value"),
                       name + "_source_sha256": cell.get("source_sha256"),
                       name + "_provenance": contract[name + "_derivation"] if cell.get("value") is not None else "missing"})
    independent = (contract["valuation_basis"] != "unestablished"
                   and all(result[name + "_provenance"] == "independently_source_derived"
                           for name in ["revaluation", "other_volume"]))
    result["independent_stock_check_available"] = independent and result["status"] != "missing_inputs"
    if result["status"] == "pass" and not independent:
        result["status"] = "unavailable"
    return result


def gold_sdr_source_consistency(quarters: list[str], values: dict, metadata: dict) -> list[dict]:
    """Check a documented composite against frozen cells without inventing a dated alias."""
    terms = {"FU263011105.Q": 1, "FU263011205.Q": -1, "FU313111303.Q": -1}
    level = "LM313111303.Q"  # Dated tables name SDR allocations, excluding monetary gold.
    expected_flow_units = "Millions of dollars; transactions, not seasonally adjusted"
    expected_level_units = "Millions of dollars; amounts outstanding end of period, market value, not seasonally adjusted"
    for series in [*terms, level]:
        expected = expected_level_units if series == level else expected_flow_units
        present = any(s == series and cell.get("value") is not None for (_, s), cell in values.items())
        if (present or series in metadata) and metadata.get(series, {}).get("units") != expected:
            raise ValueError(f"Gold/SDR source-check units differ: {series}")
    rows = []
    for quarter in quarters:
        row = check_identity("gold_sdr_transaction_composite", quarter, terms, values)
        previous = str(pd.Period(quarter, freq="Q") - 1)
        row.update({"scope": "stock_source_consistency_only", "dated_level_alias_status": "unestablished",
                    "formula_scope": "current Fed definition applied to frozen cells; dated formula not authenticated",
                    "level_candidate": level, "level_candidate_units": metadata.get(level, {}).get("units"),
                    "level_candidate_description": metadata.get(level, {}).get("description"),
                    "level_candidate_value": values.get((quarter, level), {}).get("value"),
                    "previous_level_candidate_value": values.get((previous, level), {}).get("value"),
                    "level_candidate_source_sha256": values.get((quarter, level), {}).get("source_sha256"),
                    "independent_stock_validation": "unavailable",
                    "adjustment_concepts": "FR and FV are complementary Fed-computed residual concepts; neither manufactured here",
                    "claim_boundary": "SDR-allocation level excludes monetary gold; composite-flow equality cannot establish the dated level alias"})
        for series in terms:
            cell = values.get((quarter, series), {})
            row[series + "_value"] = cell.get("value")
            row[series + "_source_sha256"] = cell.get("source_sha256")
        rows.append(row)
    return rows


def ledger_gate_passed(summary: dict, gate: str) -> bool:
    """An unavailable stock check cannot veto the separate transaction measure."""
    if gate == "transaction_ledger_admissible":
        return summary[gate] is True
    if gate in {"stock_source_consistency", "independent_stock_validation"}:
        return summary[gate] == "pass"
    raise ValueError(f"Unsupported ledger gate: {gate}")


def build_ledger(root: Path, spec_path: Path, output: Path) -> dict:
    spec = yaml.safe_load(spec_path.read_text())
    values, metadata, receipt = load_archive(root)
    vintage = receipt["vintage"]
    table = spec["ledger_tables"][vintage]
    dictionary = root / "data_dictionary" / f"{table}.txt"
    table_series = list(dict.fromkeys(row[0] for row in csv.reader(dictionary.read_text().splitlines(), delimiter="\t")))
    if any(not series.startswith("FU") or not series.endswith(".Q") for series in table_series):
        raise ValueError("Ledger requires actual FU quarterly transaction series")
    if any(metadata[s]["units"] != "Millions of dollars; transactions, not seasonally adjusted" for s in table_series):
        raise ValueError("Ledger units or adjustment status do not match the FU contract")
    quarters = pd.period_range(spec["sample_start"], spec["sample_end"], freq="Q").astype(str).tolist()
    assets, liabilities, equity = (spec[key] for key in ("asset_leaves", "liability_leaves", "equity_leaves"))
    if len(set(assets + liabilities + equity)) != len(assets + liabilities + equity):
        raise ValueError("Ledger leaves overlap")
    contracts = spec["stock_contracts"]
    if set(contracts) != set(assets + liabilities + equity):
        raise ValueError("Stock contracts must explicitly cover every ledger leaf")
    contracts = _stock_contracts_for_vintage(spec, vintage)
    totals, resources = spec["totals"], spec["resources"]
    roles = {code: role for role, codes in [("asset_leaf", assets), ("liability_leaf", liabilities), ("equity_leaf", equity)] for code in codes}
    roles.update(dict.fromkeys(totals.values(), "total"))
    roles.update(dict.fromkeys(spec["subtotals"].values(), "subtotal"))
    roles.update(dict.fromkeys(resources.values(), "resource_or_discrepancy"))
    independent_other_assets = [code for code in assets if code != "263061105"]
    identities = {
        "asset_leaves_to_total": _terms((assets, 1), ([totals["assets"]], -1)),
        "liability_leaves_to_total": _terms((liabilities, 1), ([totals["liabilities"]], -1)),
        "equity_leaves_to_total": _terms((equity, 1), ([totals["equity"]], -1)),
        "liability_and_equity_leaves_to_total": _terms((liabilities + equity, 1), ([totals["liabilities_and_equity"]], -1)),
        "published_net_lending": _terms(([totals["assets"]], 1), ([totals["liabilities_and_equity"], totals["net_lending"]], -1)),
        "published_discrepancy": _terms(([resources["us_current_account"], resources["capital_transfers_paid"], resources["nonproduced_acquisitions"], totals["assets"], resources["discrepancy"]], -1), ([totals["liabilities_and_equity"]], 1)),
        "treasury_cross_equation_reconstruction_independent_of_asset_total": _terms(([resources["us_current_account"], resources["capital_transfers_paid"], resources["nonproduced_acquisitions"], resources["discrepancy"], "263061105"] + independent_other_assets, -1), (liabilities + equity, 1)),
        "currency_split": _terms((["263025003", "263027003"], 1), (["263020005"], -1)),
        "checkable_issuer_bridge": _terms((["263027003"], 1), (["763122605", "753122603", "713122605"], -1)),
        "time_deposit_issuer_bridge": _terms((["263030005"], 1), (["763135265", "753135263"], -1)),
        "interbank_issuer_bridge": _terms((["764116005", "754116005"], 1), (["264016005"], -1)),
    }
    rows, checks, deposits, stock_checks, crosswalk, quarterly = [], [], [], [], [], []
    for series in table_series:
        crosswalk.append({"source_series_id": series, "source_provider": "Federal Reserve",
                          "code": series[2:11], "role": roles.get(series[2:11], "memo"),
                          "prefix": "FU", "vintage": vintage, **metadata[series]})
    for quarter in quarters:
        thin = {"quarter": quarter, "vintage": vintage, "units": "USD millions", "adjustment_status": "not seasonally adjusted",
                "source_archive_sha256": receipt["archive_sha256"]}
        export_codes = totals | resources | {"treasury_transactions": "263061105", "covered_checkable_deposits": "763122605", "covered_time_deposits": "763135265"}
        for name, code in export_codes.items():
            thin[name] = values.get((quarter, "FU" + code + ".Q"), {}).get("value")
        thin["current_resources"] = -thin["us_current_account"] if thin["us_current_account"] is not None else None
        quarterly.append(thin)
        for series in table_series:
            cell = values.get((quarter, series), {})
            rows.append({"quarter": quarter, "vintage": vintage, "series_id": series,
                         "role": roles.get(series[2:11], "memo"), "value_usd_millions": cell.get("value"),
                         "units": "USD millions", "adjustment_status": "not seasonally adjusted",
                         "missing": cell.get("value") is None, "rounding_increment_usd_millions": cell.get("rounding_increment"),
                         "source_file": cell.get("source_file"), "source_sha256": cell.get("source_sha256")})
        for name, terms in identities.items():
            checks.append(check_identity(name, quarter, terms, values))
        for name, item in spec["deposit_series"].items():
            series = "FU" + item["code"] + ".Q"
            cell = values.get((quarter, series), {})
            deposits.append({"quarter": quarter, "vintage": vintage, "claim": name,
                             "series_id": series, "value_usd_millions": cell.get("value"),
                             "issuer": item["issuer"], "eligibility": item["eligibility"],
                             "missing": cell.get("value") is None,
                             "perimeter_outcome": spec["perimeter_outcome"],
                             "interpretation": "holder_composition_or_memo",
                             "source_sha256": cell.get("source_sha256")})
        for code in assets + liabilities + equity:
            stock_checks.append(_stock_bridge(code, quarter, contracts[code], values))
    transaction_passed = bool(checks) and all(row["status"] == "pass" for row in checks)
    complete_leaves = sum(all(row["source_consistency_status"] != "missing_inputs" for row in stock_checks if row["leaf_code"] == code)
                          for code in contracts)
    stock_certified = bool(stock_checks) and all(row["status"] == "pass" for row in stock_checks)
    source_counts = dict(Counter(row["source_consistency_status"] for row in stock_checks))
    source_status = ("fail" if source_counts.get("fail") else "pass" if source_counts.get("pass") == len(stock_checks)
                     else "partial" if source_counts.get("pass") else "unavailable")
    gold_checks = gold_sdr_source_consistency(quarters, values, metadata)
    output.mkdir(parents=True, exist_ok=True)
    for filename, records in [("ledger.csv", rows), ("quarterly.csv", quarterly), ("crosswalk.csv", crosswalk), ("certification.csv", checks),
                              ("deposit_bridge.csv", deposits), ("stock_bridges.csv", stock_checks), ("gold_sdr_source_consistency.csv", gold_checks)]:
        write_csv(pd.DataFrame(records), output / filename)
    summary = {
        "vintage": vintage, "sample_start": quarters[0], "sample_end": quarters[-1], "quarters": len(quarters),
        "source_archive_sha256": receipt["archive_sha256"], "spec_sha256": sha256_file(spec_path),
        "input_receipt_sha256": sha256_file(root / "receipt.json"),
        "alfred_receipt_sha256": sha256_file(root / "alfred/receipt.json") if (root / "alfred/receipt.json").exists() else None,
        "producer_source_sha256": sha256_file(Path(__file__)),
        "checks": {name: dict(Counter(row["status"] for row in checks if row["check"] == name)) for name in identities},
        "stock_checks": dict(Counter(row["status"] for row in stock_checks)),
        "transaction_checks_passed": transaction_passed,
        "transaction_ledger_admissible": transaction_passed and len(identities) == 11 and quarters == pd.period_range("2002Q1", "2025Q4", freq="Q").astype(str).tolist(),
        "transaction_admission_scope": "this vintage and configured sample; system admission requires both frozen vintages",
        "stock_source_consistency": source_status,
        "stock_source_consistency_counts": source_counts,
        "independent_stock_validation": "pass" if stock_certified else "unavailable",
        "recent_external_position_change_check": "not_run_in_ledger_build",
        "gold_sdr_source_consistency": {
            "transaction_composite_counts": dict(Counter(row["status"] for row in gold_checks)),
            "dated_level_alias_status": "unestablished",
            "claim_boundary": "Current composite formula and retained SDR-allocation levels do not establish a dated gold/SDR stock alias",
        },
        "stock_expected_leaves": len(contracts), "stock_complete_leaves": complete_leaves,
        "stock_level_complete_rows": sum(row["level_inputs_available"] for row in stock_checks),
        "stock_level_complete_leaves": sum(all(row["level_inputs_available"] for row in stock_checks if row["leaf_code"] == code)
                                           for code in contracts),
        "deposit_coverage": "Checkable and time-deposit issuer bridges explicitly tested; interbank claims remain a separate claim class",
        "claim_boundary": spec["claim_boundary"],
        "pending_final_vintage": spec["pending_vintage"],
        "files": {p.name: sha256_file(p) for p in output.glob("*.csv")},
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def write_revision_bridge(frozen: Path, revised: Path, output: Path) -> pd.DataFrame:
    """Compare stable source IDs on identical quarters without overwriting either vintage."""
    columns = ["quarter", "series_id", "vintage", "value_usd_millions", "source_sha256"]
    first = pd.read_csv(frozen / "ledger.csv")[columns]
    second = pd.read_csv(revised / "ledger.csv")[columns]
    joined = first.merge(second, on=["quarter", "series_id"], how="outer", suffixes=("_frozen", "_revised"), validate="one_to_one", indicator=True)
    joined["revision_usd_millions"] = joined["value_usd_millions_revised"] - joined["value_usd_millions_frozen"]
    joined["comparison_status"] = np.where(joined["_merge"] != "both", "series_code_not_shared",
                                            np.where(joined["revision_usd_millions"].isna(), "missing_value", "matched"))
    joined = joined.drop(columns="_merge")
    write_csv(joined, output)
    return joined
