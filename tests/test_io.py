from io import StringIO
import pandas as pd
from trade_decision_lab.io import read_trade_file

def test_comtrade_csv_trailing_empty_field_does_not_shift_columns():
    content = "refYear,flowDesc,partnerDesc,cmdCode,primaryValue,\n2022,Import,China,8517,1000,\n2022,Export,Ghana,8517,500,\n"
    frame = read_trade_file(StringIO(content), "comtrade.csv")
    assert list(frame.columns[:5]) == ["refYear", "flowDesc", "partnerDesc", "cmdCode", "primaryValue"]
    assert frame.loc[0, "flowDesc"] == "Import"
    assert frame.loc[0, "partnerDesc"] == "China"
    assert frame.loc[0, "cmdCode"] == "8517"
    assert frame.loc[0, "primaryValue"] == "1000"

def test_comtrade_total_code_is_not_ranked_as_commodity():
    from trade_decision_lab.engine import run_model_b
    data = pd.DataFrame({
        "year": [2022, 2022, 2022],
        "flow": ["Import"] * 3,
        "partner": ["China", "Ghana", "World"],
        "trade_value": [100, 50, 150],
        "commodity_code": ["TOTAL", "TOTAL", "TOTAL"],
        "classification": ["H6"] * 3,
    })
    rankings, sensitivity = run_model_b(data)
    assert rankings.empty
    assert sensitivity.empty
