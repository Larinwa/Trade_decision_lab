# Trade Decision Lab integration contract

## Canonical research workflow

```python
from trade_decision_lab.integration import run_analysis, load_file
imports = load_file(import_file, 'imports.csv')
exports = load_file(export_file, 'exports.csv')
total = load_file(total_file, 'total.csv')
result = run_analysis(imports, exports, total, 'output/run_001')
from trade_decision_lab.reporting import generate_reports
files = generate_reports(result['output_dir'])
```

Inputs are three pandas DataFrames in the preserved UN Comtrade schema. CSV and XLSX are accepted by `load_file`. The research engine is **not** the general-purpose external dataset engine. Validate against `trade_decision_lab/comtrade_engine/docs/data_contract.md`. Missing required columns cause `SchemaError`. Unsupported file extensions cause `ValueError`.

`run_analysis` returns `audits`, `comparisons`, `decisions`, `output_dir`. Audit keys include `Import`, `Export`, `Total trade — Import`, `Total trade — Export`. Comparisons contain `periods`, `rankings`, `sensitivity`. Decision outputs are pandas DataFrames. The engine also saves detailed CSV files, metadata and a Markdown report beneath `output_dir`.

`generate_reports` reads the saved original engine evidence and creates a structured Excel workbook and readable PDF. CSV outputs remain the complete detailed evidence, including source-row traceability. Excel limits apply to unusually large tables. PDF previews are intentionally abbreviated; the workbook/CSVs hold detail.

## LLM boundary

`trade_decision_lab.llm.chat(api_key, model, messages, base_url)` supports OpenAI-compatible Chat Completions endpoints only. Other provider APIs require a provider-specific adapter. Pass a compact structured summary of the verified engine outputs, not raw credentials. Never allow the LLM to calculate the models. Use environment variables or server-side secrets for keys. For production, run analysis in a worker, isolate outputs by run ID, limit upload sizes, authenticate users and protect downloads.

## Deployment

`pip install -r requirements.txt`, then `streamlit run streamlit_app.py`. A future FastAPI service can call `run_analysis` and `generate_reports` without importing Streamlit. Run `PYTHONPATH=. python -m pytest -q` from the project root.
