import pandas as pd
from trade_decision_lab.engine import run_model_a, run_model_b, run_model_c

def fixture():
    return pd.DataFrame({
        "year": [2022, 2022, 2022, 2023, 2023, 2023],
        "flow": ["Import"] * 3 + ["Import"] * 3,
        "partner": ["China", "Ghana", "World", "China", "Ghana", "World"],
        "trade_value": [100, 50, 150, 120, 80, 200],
        "commodity_code": ["8517"] * 6,
        "net_weight": [10, None, 12, 12, 8, 20],
        "estimated_weight": [False, False, False, False, True, False],
        "source_file": ["fixture.csv"] * 6,
        "source_row": list(range(2, 8)),
        "classification": ["H6"] * 6,
    })

def test_models_run_and_return_expected_shapes():
    data = fixture()
    quality, trace = run_model_a(data)
    rankings, sensitivity = run_model_b(data)
    decisions = run_model_c(quality, sensitivity)
    assert not quality.empty
    assert not rankings.empty
    assert not sensitivity.empty
    assert not decisions.empty
    assert "Unit-value screening" in set(quality["rule"])
    assert "Country-only baseline" in set(rankings["treatment"])

def test_model_b_excludes_world_from_country_rankings():
    rankings, _ = run_model_b(fixture())
    assert "World" not in set(rankings["partner"])

def test_model_c_does_not_claim_actual_decision_change():
    q, _ = run_model_a(fixture())
    _, s = run_model_b(fixture())
    c = run_model_c(q, s)
    assert c["interpretation_limit"].str.contains("does not observe an actual decision").all()
