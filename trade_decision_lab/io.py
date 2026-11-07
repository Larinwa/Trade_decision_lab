from pathlib import Path
import pandas as pd

def read_trade_file(uploaded_file, filename: str | None = None) -> pd.DataFrame:
    """Read supported trade files without shifting columns on trailing delimiters.

    UN Comtrade CSV exports may contain an extra empty trailing field.
    index_col=False prevents pandas from interpreting the first data column as
    an index when row widths are inconsistent.
    """
    name = filename or getattr(uploaded_file, "name", "uploaded_file")
    suffix = Path(name).suffix.casefold()
    if suffix == ".csv":
        kwargs = {"dtype": "string", "low_memory": False, "index_col": False}
        try:
            return pd.read_csv(uploaded_file, **kwargs)
        except UnicodeDecodeError:
            if hasattr(uploaded_file, "seek"):
                uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding="latin-1", **kwargs)
    if suffix == ".xlsx":
        return pd.read_excel(uploaded_file, dtype="string", engine="openpyxl")
    raise ValueError("Unsupported file type. Upload a CSV or Excel (.xlsx) file.")
