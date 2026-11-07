import pandas as pd

def read_comtrade_csv(file_or_path):
    """Read Comtrade CSV robustly; preserve codes and remove all-empty trailing columns."""
    frame = pd.read_csv(file_or_path, dtype={"cmdCode": "string"}, low_memory=False, index_col=False)
    empty_trailing = [c for c in frame.columns if str(c).startswith("Unnamed:") and frame[c].isna().all()]
    return frame.drop(columns=empty_trailing)

def read_comtrade_excel(file_or_path):
    return pd.read_excel(file_or_path, dtype={"cmdCode": "string"})

def read_trade_upload(upload):
    name = getattr(upload, "name", str(upload)).lower()
    if name.endswith(".csv"):
        frame = pd.read_csv(upload, low_memory=False, index_col=False)
        empty_trailing = [c for c in frame.columns if str(c).startswith("Unnamed:") and frame[c].isna().all()]
        return frame.drop(columns=empty_trailing)
    if name.endswith(".xlsx"):
        return pd.read_excel(upload)
    raise ValueError("Only CSV and XLSX files are supported.")
