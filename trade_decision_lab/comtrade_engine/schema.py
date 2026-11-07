from __future__ import annotations
import pandas as pd

REQUIRED_COLUMNS = {
    "refYear", "flowCode", "flowDesc", "reporterDesc", "partnerCode",
    "partnerDesc", "cmdCode", "classificationCode", "primaryValue",
}
NUMERIC_COLUMNS = ["refYear", "reporterCode", "partnerCode", "primaryValue", "qty", "netWgt"]
RECOMMENDED_COLUMNS = [
    "reporterCode", "qty", "netWgt", "qtyUnitCode", "aggrLevel", "cifvalue",
    "fobvalue", "partner2Code", "motCode", "customsCode", "isAggregate",
    "isReported", "isNetWgtEstimated", "isQtyEstimated", "legacyEstimationFlag",
]


class SchemaError(ValueError):
    pass


def validate_comtrade_frame(frame: pd.DataFrame, strict: bool = True) -> dict:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    problems = []
    if frame.empty:
        problems.append("The dataset contains no records.")
    for col in NUMERIC_COLUMNS:
        if col in frame.columns:
            invalid = frame[col].notna() & pd.to_numeric(frame[col], errors="coerce").isna()
            if invalid.any():
                problems.append(f"{col}: {int(invalid.sum())} non-numeric values.")
    report = {
        "valid": not missing and not problems,
        "rows": int(len(frame)),
        "columns": int(frame.shape[1]),
        "missing_required": missing,
        "missing_recommended": [c for c in RECOMMENDED_COLUMNS if c not in frame.columns],
        "problems": problems,
        "estimation_columns": [c for c in ["isNetWgtEstimated", "isQtyEstimated", "legacyEstimationFlag"] if c in frame.columns],
    }
    if strict and not report["valid"]:
        raise SchemaError(f"Invalid UN Comtrade structure: {report}")
    return report
