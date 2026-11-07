from pathlib import Path
import pandas as pd
from trade_decision_lab.report import save_run

def test_report_writer_creates_expected_artifacts(tmp_path):
    validation = {
        "rows": 2,
        "analysis_capabilities": {
            "monetary_partner_analysis": True,
            "commodity_analysis": True,
            "quantity_analysis": False,
            "weight_analysis": False,
        },
    }
    quality = pd.DataFrame([{"rule": "test", "affected_rows": 0}])
    rankings = pd.DataFrame([{"partner": "A", "trade_value": 10}])
    sensitivity = pd.DataFrame([{"top1_changed": False}])
    decisions = pd.DataFrame([{"status": "No change"}])
    save_run(tmp_path, "fixture.csv", validation, quality, rankings, sensitivity, decisions)
    expected = {
        "dataset_validation.csv", "model_a_quality_findings.csv",
        "model_b_partner_rankings.csv", "model_b_sensitivity.csv",
        "model_c_decision_implications.csv", "run_metadata.json", "run_summary.md",
    }
    assert expected.issubset({p.name for p in Path(tmp_path).iterdir()})
