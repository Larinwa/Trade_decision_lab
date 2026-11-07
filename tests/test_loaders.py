from io import StringIO
from trade_decision_lab.loaders import read_comtrade_csv

def test_comtrade_csv_trailing_empty_column_and_code_text():
    frame = read_comtrade_csv(StringIO(
        "refYear,flowDesc,cmdCode,primaryValue,\n"
        "2020,Import,010121,100,\n"
    ))
    assert "Unnamed: 4" not in frame.columns
    assert str(frame.loc[0, "cmdCode"]) == "010121"
    assert float(frame.loc[0, "primaryValue"]) == 100
