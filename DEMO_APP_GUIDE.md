# Trade Decision Lab | Demo app

## What this is

A presentation-ready Streamlit interface over the **same preserved UN Comtrade Models A, B and C** used by the final research notebook. No replacement analytical model or invented research results. The app supports a three-file upload, background-style processing status, decision-evidence exploration, PDF/Excel/ZIP downloads, optional AI report summary and evidence-grounded Q&A.

## Run locally

1. Extract the ZIP.
2. Open a terminal in the `TRADE_DECISION_LAB` folder.
3. Install dependencies: `python -m pip install -r requirements.txt`
4. Launch: `python -m streamlit run streamlit_app.py`
5. Open the local URL Streamlit prints, typically `http://localhost:8501`.

Upload the same three files used in Colab, each to its labelled uploader:

- `commodity_imports_combined.csv` (imports, `flowCode` M)
- `commodity_exports_2016_2025.csv` (exports, `flowCode` X)
- `un_comtrade_nigeria_2016_2025.csv` (total trade, `flowCode` M and/or X)

Upload order does not matter because each file has its own labelled input. CSV and XLSX are accepted. Analysis can take time with large datasets; keep the browser tab open.

## Optional AI

Open **Report summary → AI connection settings** and enter a Gemini API key, endpoint and model. The default endpoint uses Google's OpenAI-compatible interface. Alternatively configure an OpenAI-compatible endpoint. For Gemini you can also set `GEM_KEY` as a Streamlit secret or environment variable. The model can be overridden with `TDL_LLM_MODEL`.

The app generates an evidence-based, deterministic plain-English fallback when no AI key is provided. The AI summary and chat are optional. Uploaded raw datasets are not passed to the LLM; selected aggregated audit and decision evidence is sent to the configured provider when AI is used. The PDF and workbook never include AI-generated content.

## Deploy to Streamlit Community Cloud

Create a GitHub repository containing the extracted project. In Streamlit Community Cloud select the repository, branch and `streamlit_app.py` as entrypoint. Set any needed API secrets in the deployment settings, not in the repository. Large dataset processing may exceed a free hosting tier's memory or execution limits; a local demo is the most reliable option for the full extracts.

## Scientific interpretation

Model A reports data-quality conditions. Model B measures sensitivity to specified analytical treatments. Model C assigns preliminary decision-specific fitness-for-use judgements. No observed commercial decisions are measured. World aggregates must not be added to country partner totals. H4 and H6 are classification revisions, not code lengths. The app preserves the original technical report and evidence exports.
