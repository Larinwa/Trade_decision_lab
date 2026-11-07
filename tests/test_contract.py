import pandas as pd
import pytest
from trade_decision_lab.contract import suggest_mapping, standardize_frame

def sample():
    return pd.DataFrame({
        "Year": [2022, 2022, 2023, 2023],
        "Trade Flow": ["Import", "Import", "Export", "Export"],
        "Partner Country": ["China", "Ghana", "China", "Ghana"],
        "HS Code": ["8517", "8517", "8517", "8517"],
        "Trade Value": ["1000", "500", "700", "300"],
        "Net Weight": ["10", None, "7", "3"],
    })

def test_auto_mapping_and_standardization():
    frame = sample()
    mapping = suggest_mapping(frame.columns)
    standard, report = standardize_frame(frame, mapping)
    assert report["valid"]
    assert len(standard) == 4
    assert standard.loc[0, "flow"] == "Import"
    assert standard.loc[0, "trade_value"] == 1000
    assert report["analysis_capabilities"]["commodity_analysis"]

def test_missing_required_mapping_rejected():
    frame = sample().drop(columns=["Trade Value"])
    with pytest.raises(ValueError, match="Required fields"):
        standardize_frame(frame, suggest_mapping(frame.columns))

def test_duplicate_target_mapping_rejected():
    frame = sample()
    mapping = suggest_mapping(frame.columns)
    mapping["Year"] = "flow"
    with pytest.raises(ValueError):
        standardize_frame(frame, mapping)
