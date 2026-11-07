"""Stable application-facing entry point for the original Comtrade research pipeline."""
from pathlib import Path
from .loaders import read_comtrade_csv, read_comtrade_excel
from .comtrade_engine.schema import validate_comtrade_frame, SchemaError
from .comtrade_engine.pipeline import run_project

def run_analysis(imports, exports, total_trade, output_dir, commodities=None):
    """Accept three pandas DataFrames; return audits/comparisons/decisions/output_dir."""
    for name, frame in [('imports', imports), ('exports', exports), ('total_trade', total_trade)]:
        check = validate_comtrade_frame(frame, strict=False)
        if not check['valid']:
            raise SchemaError(f'{name} violates the UN Comtrade input contract: {check}')
    return run_project(imports, exports, total_trade, Path(output_dir), commodities=commodities)

def load_file(file, filename):
    if filename.lower().endswith('.csv'):
        return read_comtrade_csv(file)
    if filename.lower().endswith('.xlsx'):
        return read_comtrade_excel(file)
    raise ValueError('Expected CSV or XLSX file')
