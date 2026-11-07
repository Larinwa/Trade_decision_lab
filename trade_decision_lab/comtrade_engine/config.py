from pathlib import Path

PROJECT_VERSION = "1.0.0"
EXPECTED_REPORTER_CODE = 566
EXPECTED_REPORTER_NAME = "Nigeria"
EXPECTED_YEARS = tuple(range(2016, 2026))
ANALYSIS_YEARS_A = tuple(range(2016, 2025))
ANALYSIS_YEARS_B = (2022, 2023, 2024)
SELECTED_COMMODITIES = {
    "2710": "Petroleum oils and oils obtained from bituminous minerals",
    "1001": "Wheat and meslin",
    "8703": "Motor cars and other motor vehicles",
    "8517": "Telephone sets, including smartphones",
    "0303": "Fish, frozen",
}

UNIT_VALUE_HIGH_RATIO = 3.0
UNIT_VALUE_LOW_RATIO = 1.0 / 3.0
PARTIAL_YEAR_COVERAGE_RATIO = 0.80
REPORTED_WEIGHT_VALUE_SHARE_MIN_PCT = 50.0
DQ12_ABSOLUTE_TOLERANCE_USD = 1.0
DQ13_ABSOLUTE_TOLERANCE_USD = 1.0
TOP_N = 5

# These are descriptive sensitivity checks, not validated economic decision thresholds.
DECISION_CHANGE_RULES = {
    "top1_change": "flag",
    "top5_membership_change": "flag",
    "concentration_change": "report_exact_difference",
}

DEFAULT_FILENAMES = {
    "imports": "commodity_imports_combined.csv",
    "exports": "commodity_exports_2016_2025.csv",
    "total_trade": "un_comtrade_nigeria_2016_2025.csv",
}


def project_paths(project_dir):
    root = Path(project_dir)
    return {
        "root": root,
        "raw": root / "Datasets" / "Raw",
        "reports": root / "Report" / "Trade_Decision_Lab",
    }
