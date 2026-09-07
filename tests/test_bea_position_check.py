import json

import pandas as pd
import pytest

from rowflow.bea_position_check import compare, normalize_bea


def _payload(value="10", adjustment="QNSA"):
    title = "Table 1.3. Change in the U.S. Net International Investment Position"
    table = {"Title": title, "Sub_Title": "[Millions of dollars]", "Description": "Dated release", "TN": []}
    chart = {"CHARTNAME": title, "YAXISLABEL": "[Millions of dollars]", "series": [
        {"name": f"Treasuries (position) ({adjustment})", "rowid": "1",
         "DATAPOINT": [{"time_period": "2023-Q1", "value": value}]},
    ]}
    return {"Steps": [{"Prompts": [{"UIControl": "Table", "PromtData": json.dumps({
        "Table": json.dumps(table), "Chart": json.dumps(chart),
    })}]}]}


def test_normalization_rejects_adjusted_units_and_duplicate_cells():
    with pytest.raises(ValueError, match="not seasonally adjusted"):
        normalize_bea(_payload(adjustment="QSA"), ["Treasuries"])
    payload = _payload()
    prompt = payload["Steps"][0]["Prompts"][0]
    wrapped = json.loads(prompt["PromtData"])
    chart = json.loads(wrapped["Chart"])
    chart["series"] *= 2
    wrapped["Chart"] = json.dumps(chart)
    prompt["PromtData"] = json.dumps(wrapped)
    with pytest.raises(ValueError, match="Duplicate"):
        normalize_bea(payload, ["Treasuries"])
    wrapped["Table"] = json.dumps({"Title": chart["CHARTNAME"], "Sub_Title": "[Billions of dollars]"})
    prompt["PromtData"] = json.dumps(wrapped)
    with pytest.raises(ValueError, match="units"):
        normalize_bea(payload, ["Treasuries"])


@pytest.mark.parametrize("value", [None, "n.a.", ".....", "(*)"])
def test_missing_source_values_are_not_zero(value):
    frame, _ = normalize_bea(_payload(value), ["Treasuries"])
    assert frame.value_usd_millions.isna().all()


@pytest.mark.parametrize("value", ["garbage", "inf", "NaN"])
def test_malformed_or_nonfinite_source_rejected(value):
    with pytest.raises(ValueError):
        normalize_bea(_payload(value), ["Treasuries"])


def test_aggregate_needs_every_cell_and_missing_adjustments_stay_unavailable():
    bea = pd.DataFrame([
        {"quarter": "2023Q1", "category": c, "component": "position", "value_usd_millions": v}
        for c, v in [("bills", 4), ("bonds", 6)]
    ])
    spec = {"start_quarter": "2023Q1", "end_quarter": "2023Q1", "categories": {
        "Treasuries": {"bea_categories": ["bills", "bonds"], "z1_flow": "FU1.Q", "z1_level": "LM1.Q",
                       "z1_revaluation": "FR1.Q", "z1_other_volume": "FV1.Q",
                       "mapping_status": "closest_instrument_comparison", "boundary": "No certificate"},
    }}
    cells = {("2023Q1", "LM1.Q"): {"value": 10}}
    result = compare(bea, cells, spec, "dated").set_index("measurement")
    assert result.loc["position", "numeric_comparison"] == "exact_match"
    assert result.loc["other_changes", "numeric_comparison"] == "unavailable"
    assert set(result.independent_stock_validation) == {"unavailable"}
    result = compare(bea.iloc[:1], cells, spec, "dated").set_index("measurement")
    assert result.loc["position", "numeric_comparison"] == "unavailable"
