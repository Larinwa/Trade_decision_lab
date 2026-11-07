import pandas as pd

from trade_decision_lab.comtrade_engine import quality, comparison, decision
from trade_decision_lab.comtrade_engine.pipeline import run_project


def make_data(flow):
    records = []
    years = [(2019, "H4"), (2022, "H6"), (2023, "H6"), (2024, "H6")]
    for year, classification in years:
        for code, total in [("2710", 1000.0), ("1001", 500.0)]:
            records.extend([
                {"refYear": year, "flowCode": "M" if flow == "Import" else "X", "flowDesc": flow,
                 "reporterCode": 566, "reporterDesc": "Nigeria", "partnerCode": 0, "partnerDesc": "World",
                 "cmdCode": code, "cmdDesc": "Test commodity", "classificationCode": classification,
                 "aggrLevel": 4, "primaryValue": total, "qty": 10.0, "netWgt": 10.0,
                 "isNetWgtEstimated": False, "isQtyEstimated": False},
                {"refYear": year, "flowCode": "M" if flow == "Import" else "X", "flowDesc": flow,
                 "reporterCode": 566, "reporterDesc": "Nigeria", "partnerCode": 156, "partnerDesc": "China",
                 "cmdCode": code, "cmdDesc": "Test commodity", "classificationCode": classification,
                 "aggrLevel": 4, "primaryValue": total * 0.6, "qty": 6.0, "netWgt": 6.0,
                 "isNetWgtEstimated": False, "isQtyEstimated": False},
                {"refYear": year, "flowCode": "M" if flow == "Import" else "X", "flowDesc": flow,
                 "reporterCode": 566, "reporterDesc": "Nigeria", "partnerCode": 840, "partnerDesc": "United States",
                 "cmdCode": code, "cmdDesc": "Test commodity", "classificationCode": classification,
                 "aggrLevel": 4, "primaryValue": total * 0.4, "qty": 4.0, "netWgt": 4.0,
                 "isNetWgtEstimated": False, "isQtyEstimated": False},
            ])
    return pd.DataFrame(records)


def make_total_trade(imports, exports):
    rows = []
    for flow, data, flow_code in [("Import", imports, "M"), ("Export", exports, "X")]:
        for year, group in data[data["partnerCode"].eq(0)].groupby("refYear"):
            rows.append({"refYear": year, "flowCode": flow_code, "flowDesc": flow,
                         "reporterCode": 566, "reporterDesc": "Nigeria", "partnerCode": 0,
                         "partnerDesc": "World", "cmdCode": "TOTAL", "cmdDesc": "All commodities",
                         "classificationCode": "TOTAL", "primaryValue": group["primaryValue"].sum()})
    return pd.DataFrame(rows)


def test_three_models_run_for_import_and_export():
    imports = make_data("Import")
    exports = make_data("Export")
    total = make_total_trade(imports, exports)
    for flow, raw in [("Import", imports), ("Export", exports)]:
        prepared, audit = quality.run_audit(raw, total, flow_desc=flow)
        assert len(audit["findings"]) >= 18
        result_b = comparison.run_comparison(prepared, flow, commodities={"2710": "Petroleum oils", "1001": "Wheat"})
        assert not result_b["rankings"].empty
        assert set(result_b["rankings"]["classification"]) == {"H4", "H6"}
        result_c = decision.run_decision_assessment(prepared, result_b, flow)
        assert not result_c.empty
        assert result_c["interpretation_limit"].str.contains("not evidence").all()
        assert not result_c["decision_sensitivity"].eq("Sensitive to tested treatments").any()


def test_missing_weight_sensitivity_uses_net_weight_flag():
    data = make_data("Import")
    data.loc[data.index[-1], "netWgt"] = None
    prepared = quality.prepare_dataset(data)
    result = comparison.run_comparison(prepared, "Import", commodities={"2710": "Petroleum oils"})
    sensitivity = result["sensitivity"]
    assert "missing_weight_excluded_sensitivity" in set(sensitivity["treatment"])


def test_dq12_excludes_unassessable_groups_from_difference_count():
    data = make_data("Import")
    prepared = quality.prepare_dataset(data)
    detail = quality.dq12_detail(prepared)
    assert detail["assessable"].all()
    assert detail["absolute_difference"].fillna(0).eq(0).all()


def test_pipeline_writes_all_three_model_outputs(tmp_path):
    imports = make_data("Import")
    exports = make_data("Export")
    total = make_total_trade(imports, exports)
    result = run_project(imports, exports, total, tmp_path, commodities={"2710": "Petroleum oils", "1001": "Wheat"})
    for flow in ["import", "export"]:
        flow_dir = tmp_path / flow
        for filename in [
            "model_a_findings.csv",
            "model_a_source_row_traceability.csv",
            "model_a_world_reconciliation.csv",
            "model_b_partner_rankings.csv",
            "model_b_sensitivity_comparison.csv",
            "model_c_decision_assessment.csv",
        ]:
            assert (flow_dir / filename).is_file()
    for flow in ["import", "export"]:
        assert (tmp_path / f"total_trade_{flow}" / "model_a_findings.csv").is_file()
    assert (tmp_path / "run_summary.md").is_file()
    assert result["output_dir"] == tmp_path
