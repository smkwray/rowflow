"""Compare a pinned BEA IIP Table 1.3 response with dated Z.1 source cells."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import pandas as pd
import yaml

from rowflow.io import sha256_file
from rowflow.z1_ledger import load_archive

COMPONENTS = (
    "position", "change in position", "financial-account transactions", "other changes",
    "price changes", "exchange-rate changes", "changes in volume and valuation n.i.e.",
)


def normalize_bea(payload: dict, categories: list[str]) -> tuple[pd.DataFrame, dict]:
    """Read exact public iTable chart cells; absent/suppressed values stay missing."""
    prompts = [p for s in payload["Steps"] for p in s["Prompts"] if p["UIControl"] == "Table"]
    if len(prompts) != 1:
        raise ValueError("Expected exactly one BEA table")
    wrapped = json.loads(prompts[0]["PromtData"])
    table, chart = json.loads(wrapped["Table"]), json.loads(wrapped["Chart"])
    title = "Table 1.3. Change in the U.S. Net International Investment Position"
    if table["Title"] != title or chart["CHARTNAME"] != title:
        raise ValueError("Expected BEA IIP Table 1.3")
    if table["Sub_Title"] != "[Millions of dollars]" or chart["YAXISLABEL"] != "[Millions of dollars]":
        raise ValueError("Unexpected BEA units")
    rows = []
    for series in chart["series"]:
        name = series["name"].strip()
        if not name.endswith(" (QNSA)"):
            raise ValueError("Only quarterly not seasonally adjusted BEA data are supported")
        for category in categories:
            for component in COMPONENTS:
                if name != f"{category} ({component}) (QNSA)":
                    continue
                points = series["DATAPOINT"]
                for point in points if isinstance(points, list) else [points]:
                    quarter = point["time_period"].replace("-", "")
                    if not re.fullmatch(r"\d{4}Q[1-4]", quarter):
                        raise ValueError("Invalid BEA quarter")
                    raw = point.get("value")
                    value = None if raw in (None, "", "n.a.", ".....", "(*)") else float(raw)
                    if value is not None and not math.isfinite(value):
                        raise ValueError("Nonfinite BEA value")
                    rows.append({"quarter": quarter, "category": category, "component": component,
                                 "value_usd_millions": value, "raw_value": raw,
                                 "source_row_id": series["rowid"], "seasonal_adjustment": "QNSA"})
    frame = pd.DataFrame(rows)
    if frame.empty or set(frame.category) != set(categories):
        raise ValueError("Required BEA category unavailable")
    if frame.duplicated(["quarter", "category", "component"]).any():
        raise ValueError("Duplicate BEA source cell")
    return frame, {"title": title, "release": table["Description"], "units": "USD_millions",
                   "footnotes": table["TN"]}


def _sum_required(values: list[float | None]) -> float | None:
    return None if not values or any(v is None or pd.isna(v) for v in values) else sum(values)


def checked_z1_units(cells: dict, metadata: dict, spec: dict) -> tuple[dict, dict]:
    """Reject incompatible units; source cells lacking unit metadata are unavailable."""
    checked, status = cells.copy(), {}
    fields = {"z1_flow": ("FU", "transactions, not seasonally adjusted"),
              "z1_level": (("LM", "FL"), "amounts outstanding end of period"),
              "z1_revaluation": ("FR", "revaluation"),
              "z1_other_volume": ("FV", "volume")}
    for mapping in spec["categories"].values():
        if not mapping["bea_categories"]:
            raise ValueError("BEA category mapping must be nonempty")
        for field, (prefix, concept) in fields.items():
            series = mapping[field]
            if not series.startswith(prefix):
                raise ValueError(f"Invalid mapped source prefix: {series}")
            units = metadata.get(series, {}).get("units")
            status[series] = {"source_units": units, "status": "validated" if units else "unavailable_source_units"}
            if units and (not units.startswith("Millions of dollars;") or concept not in units
                          or "annual" in units.lower()):
                raise ValueError(f"Incompatible Z.1 source units: {series}")
            if not units:
                for key, cell in cells.items():
                    if key[1] == series:
                        checked[key] = cell | {"value": None}
    return checked, status


def compare(bea: pd.DataFrame, cells: dict, spec: dict, vintage: str) -> pd.DataFrame:
    """Show gaps and unavailable components without turning comparisons into gates."""
    index = bea.set_index(["quarter", "category", "component"])["value_usd_millions"]
    rows = []
    for quarter in pd.period_range(spec["start_quarter"], spec["end_quarter"], freq="Q"):
        q, previous = str(quarter), str(quarter - 1)
        for category, mapping in spec["categories"].items():
            if not mapping["bea_categories"]:
                raise ValueError("BEA category mapping must be nonempty")
            def value(series: str, period: str = q) -> float | None:
                return cells.get((period, series), {}).get("value")

            level, lag = value(mapping["z1_level"]), value(mapping["z1_level"], previous)
            measurements = {
                "position": (["position"], level),
                "change_in_position": (["change in position"],
                                       None if level is None or lag is None else level - lag),
                "transactions": (["financial-account transactions"], value(mapping["z1_flow"])),
                "revaluation": (["price changes", "exchange-rate changes"], value(mapping["z1_revaluation"])),
                "other_volume": (["changes in volume and valuation n.i.e."], value(mapping["z1_other_volume"])),
                "other_changes": (["other changes"], _sum_required([
                    value(mapping["z1_revaluation"]), value(mapping["z1_other_volume"])])),
            }
            for measurement, (components, z1_value) in measurements.items():
                bea_values = [index.get((q, c, component)) for c in mapping["bea_categories"] for component in components]
                bea_value = _sum_required(bea_values)
                gap = None if bea_value is None or z1_value is None else z1_value - bea_value
                rows.append({"quarter": q, "category": category, "measurement": measurement,
                             "z1_vintage": vintage, "bea_value_usd_millions": bea_value,
                             "z1_value_usd_millions": z1_value, "gap_z1_minus_bea_usd_millions": gap,
                             "numeric_comparison": "unavailable" if gap is None else "exact_match" if gap == 0 else "different",
                             "mapping_status": mapping["mapping_status"], "boundary": mapping["boundary"],
                             "independent_stock_validation": "unavailable"})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bea", type=Path, required=True)
    parser.add_argument("--spec", type=Path, default=Path("config/bea_position_check.yml"))
    parser.add_argument("--z1", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite a comparison")
    spec = yaml.safe_load(args.spec.read_text())
    categories = sorted({c for m in spec["categories"].values() for c in m["bea_categories"]})
    bea, metadata = normalize_bea(json.loads(args.bea.read_text()), categories)
    frames, inputs = [], {"bea_sha256": sha256_file(args.bea), "spec_sha256": sha256_file(args.spec), "z1": []}
    for root in args.z1:
        cells, source_metadata, receipt = load_archive(root)
        cells, unit_status = checked_z1_units(cells, source_metadata, spec)
        frames.append(compare(bea, cells, spec, receipt["vintage"]))
        inputs["z1"].append({"vintage": receipt["vintage"], "receipt_sha256": sha256_file(root / "receipt.json"),
                            "source_files": receipt["retained_files"], "mapped_source_units": unit_status,
                            "alfred_receipt_sha256": sha256_file(root / "alfred/receipt.json") if (root / "alfred/receipt.json").exists() else None})
    comparison = pd.concat(frames, ignore_index=True)
    summary = {"recent_external_position_change_check": "partial", "independent_stock_validation": "unavailable",
               "start_quarter": spec["start_quarter"], "end_quarter": spec["end_quarter"],
               "bea": metadata, "inputs": inputs, "effective_contract": spec,
               "numeric_comparison_counts": comparison.groupby(["z1_vintage", "category", "measurement", "numeric_comparison"]).size().rename("rows").reset_index().to_dict("records")}
    args.output.mkdir(parents=True)
    bea.to_csv(args.output / "bea_selected_cells.csv", index=False)
    comparison.to_csv(args.output / "comparison.csv", index=False)
    summary["output_hashes"] = {p.name: sha256_file(p) for p in args.output.glob("*.csv")}
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
