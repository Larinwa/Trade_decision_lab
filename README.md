# Trade Decision Lab

**Research:** *Garbage In, Garbage Out: Examining the Implications of Poor Data Quality for Decision-Making in Nigeria’s Import–Export Sector.*

**Group 5**, Technical Writing and Presentation, Department of Data and Information Science, University of Ibadan.

## Overview

This repository contains the research workflow and interactive demonstration for assessing selected UN Comtrade records relevant to Nigeria. The work has five objectives: (1) assess data quality, (2) examine effects of quality issues on analytical results, (3) study sensitivity of trade patterns and rankings, (4) consider potential implications for import–export decisions, and (5) demonstrate the assessment in an interactive application.

- **Model A:** Data-quality screening and audit evidence.
- **Model B:** Analytical sensitivity under defined treatments, including trade-partner rankings.
- **Model C:** Preliminary, decision-specific fitness-for-use assessments.

Quality flags are not confirmed errors. Sensitivity comparisons are not verified corrections, and the project does not measure actual organisational decisions.

## Repository guide

| Location | Purpose |
| --- | --- |
| `notebooks/01_Data_Acquisition_Preprocessing_and_EDA.ipynb` | Original dataset acquisition, preprocessing, exploratory analysis and visualisations. Designed for Google Colab. |
| `notebooks/02_Trade_Decision_Lab_Models_A_B_C.ipynb` | Colab research-model demonstration and report generation. **Prompts for a project ZIP**, then the three datasets. |
| `streamlit_app.py` | **Current** public-facing landing page, assessment interface, summary charts, downloads and optional AI. |
| `trade_decision_lab/comtrade_engine/` | Preserved research model implementations and methodological documentation. |
| `trade_decision_lab/integration.py` | Integration of the research pipeline with uploaded datasets. |
| `trade_decision_lab/reporting.py` | Deterministic PDF and Excel reporting. |
| `tests/` | Automated checks. |
| `data/` | Put the three original UN Comtrade datasets here if they can be redistributed. |

**Important:** `app.py` is a legacy alternative interface. Launch **`streamlit_app.py`**, not `app.py`. The older `Trade_Decision_Lab_Colab.ipynb` is also retained for reference; the numbered notebooks above are the intended reading order.

## Step 1: Get the code

Download this repository using **Code → Download ZIP** on GitHub, extract it, and open a terminal inside the `TRADE_DECISION_LAB` directory. Alternatively:

```bash
git clone https://github.com/OWNER/REPOSITORY.git
cd REPOSITORY
```

Replace `OWNER/REPOSITORY` with the actual GitHub repository path.

## Step 2: Set up Python

Use Python 3.10 or newer. From the project root:

```bash
python -m venv .venv
```

Activate it on **Windows PowerShell**:

```powershell
.venv\Scripts\Activate.ps1
```

Or on **macOS/Linux**:

```bash
source .venv/bin/activate
```

Then install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Step 3: Prepare the three source datasets

The application expects the following **separate** UN Comtrade extracts, uploaded in the indicated roles:

1. **Imports:** `commodity_imports_combined.csv`, commodity-level import records, `flowCode = M`.
2. **Exports:** `commodity_exports_2016_2025.csv`, commodity-level export records, `flowCode = X`.
3. **Total trade:** `un_comtrade_nigeria_2016_2025.csv`, reference records with `flowCode = M` and/or `X`.

The exact filenames are illustrative; select the correct roles based on file contents. CSV and XLSX are supported. Keep HS commodity codes as text, including leading zeroes such as `0303`. Do not add the `World` aggregate to individual country partners. The `data/` folder is a suggested home for published source files, but **the app requires uploads through its interface**, not automatic loading from `data/`.

If the files are too large for ordinary GitHub storage, publish their provenance and a stable download location instead of committing oversized files. GitHub blocks individual files above 100 MB. Do not commit API keys or confidential information.

## Step 4: Run the interactive application

```bash
streamlit run streamlit_app.py
```

Open the local URL shown in the terminal (usually `http://localhost:8501`). On **Home**, select **Launch demo**, upload the three datasets in their correct roles and click **Run trade data assessment**. When processing finishes:

- **Report summary:** Data-driven visualisations and a narrative interpretation.
- **Decision evidence:** Model C verdicts and Model B sensitivity tables.
- **Download reports:** PDF, Excel and complete evidence ZIP.
- **Ask the lab:** Optional AI-assisted questions based on selected research findings.

The analysis and downloadable reports **do not require an AI key**.

## Step 5: Optional AI setup

Open **Report summary → AI connection settings** to enter a Gemini or OpenAI-compatible API key, model and endpoint. Alternatively, create `.streamlit/secrets.toml` locally:

```toml
GEM_KEY = "YOUR_PRIVATE_API_KEY"
TDL_LLM_MODEL = "gemini-2.5-flash"
```

Never publish `.streamlit/secrets.toml`, `.env` or keys in notebook outputs. The repository's `.gitignore` excludes the local secrets file. On Streamlit Community Cloud, configure secrets through the app's deployment settings instead.

The LLM receives selected findings rather than the raw uploaded datasets. It interprets evidence; it does not run the statistical analysis or alter the research models.

## Step 6: Explore the notebooks

**Notebook 01: Data acquisition, preprocessing and EDA**

Open `notebooks/01_Data_Acquisition_Preprocessing_and_EDA.ipynb` in Google Colab. It uses `gdown` and the original shared Google Drive file IDs to acquire datasets. The Drive files must remain accessible. Run cells in order. Its charts are exploratory and should not be confused with the model's decision-fitness outputs.

**Notebook 02: Models A, B and C**

Open `notebooks/02_Trade_Decision_Lab_Models_A_B_C.ipynb` in Colab. Its setup cell **asks you to upload a ZIP of the project**, not to clone the GitHub repository. Create a ZIP containing the `TRADE_DECISION_LAB` folder, upload it when prompted, then upload the three datasets and follow the notebook's assignment, validation, analysis and report-download steps. This is the notebook's existing implementation and has intentionally not been rewritten.

**Suggested reproducibility order:** acquire and inspect data in Notebook 01 → run Notebook 02 or the Streamlit app against the same three source files → review Model A/B/C evidence → download the reports.

## Step 7: Run automated tests

```bash
python -m pytest -q
```

Tests verify implementation behaviour but do not substitute for an end-to-end run against the published original data.

## Interpretation and limitations

The selected five HS4 commodities are `2710`, `1001`, `8703`, `8517` and `0303`. The source data cover the specified research period, but individual analysis scenarios may use configured subsets or overlapping classification windows. Review `trade_decision_lab/comtrade_engine/docs/methodology.md`, `limitations.md` and `data_contract.md` before interpreting comparisons. Rankings changing under analytical treatments do not establish which treatment is factually correct.

## Reproducibility checklist

- [ ] All three original datasets are accessible, correctly labelled and accompanied by source/provenance details.
- [ ] Notebook 01 runs and its figures display.
- [ ] Notebook 02 runs with the packaged project ZIP and all three files.
- [ ] The Streamlit app loads, validates all three uploads and generates reports.
- [ ] Model A/B/C outputs and chart labels have been inspected.
- [ ] Automated tests pass in the target environment.
- [ ] No private API keys or credentials are committed.

**Status:** The code package is prepared for publication; execution against the final uploaded real datasets and hosted Streamlit deployment still require acceptance testing.
