from __future__ import annotations
import re
import pandas as pd

# Standard internal schema. Only year, flow, trade_value and partner are
# required for the core monetary partner analysis. Commodity is required
# for commodity-level analysis; quantity and net_weight are optional.
ALIASES = {
    "year": ["year", "refyear", "trade_year", "period", "time"],
    "flow": ["flow", "flowdesc", "trade_flow", "tradeflow", "direction"],
    "reporter": ["reporter", "reporterdesc", "reporting_country", "reporter_country", "country"],
    "partner": ["partner", "partnerdesc", "partner_country", "trading_partner", "destination", "origin"],
    "commodity_code": ["commodity_code", "cmdcode", "hs_code", "hscode", "commodity", "product_code"],
    "trade_value": ["trade_value", "primaryvalue", "tradevalue", "value", "trade_amount", "amount"],
    "quantity": ["quantity", "qty", "trade_quantity"],
    "net_weight": ["net_weight", "netwgt", "netweight", "weight"],
    "currency": ["currency", "trade_currency", "currency_code"],
    "quantity_unit": ["quantity_unit", "qtyunit", "qtyunitcode", "unit", "unit_of_measure"],
    "classification": ["classification", "classificationcode", "hs_version", "hs_classification"],
    "estimated_weight": ["estimated_weight", "isnetwgtestimated", "net_weight_estimated"],
}

REQUIRED = ["year", "flow", "partner", "trade_value"]
OPTIONAL = ["reporter", "commodity_code", "quantity", "net_weight", "currency",
            "quantity_unit", "classification", "estimated_weight"]

def norm_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().casefold())

_ALIAS_LOOKUP = {norm_name(alias): canonical for canonical, aliases in ALIASES.items()
                 for alias in [canonical, *aliases]}

def suggest_mapping(columns) -> dict:
    mapping = {}
    for col in columns:
        canonical = _ALIAS_LOOKUP.get(norm_name(col))
        if canonical and canonical not in mapping.values():
            mapping[col] = canonical
    return mapping

def standardize_frame(frame: pd.DataFrame, mapping: dict) -> tuple[pd.DataFrame, dict]:
    if frame is None or frame.empty:
        raise ValueError("The uploaded dataset is empty.")
    if not mapping:
        raise ValueError("No column mapping was provided.")
    chosen = {}
    for source, target in mapping.items():
        if source not in frame.columns:
            raise ValueError(f"Mapped source column does not exist: {source}")
        if target in chosen:
            raise ValueError(f"More than one source column was mapped to '{target}'.")
        chosen[target] = source

    missing = [field for field in REQUIRED if field not in chosen]
    if missing:
        raise ValueError("Required fields are not mapped: " + ", ".join(missing))

    out = pd.DataFrame(index=frame.index)
    for target, source in chosen.items():
        out[target] = frame[source]

    # Canonical types and normalisation.
    out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
    out["trade_value"] = pd.to_numeric(
        out["trade_value"].astype("string").str.replace(",", "", regex=False), errors="coerce"
    )
    for col in ["quantity", "net_weight"]:
        if col in out:
            out[col] = pd.to_numeric(
                out[col].astype("string").str.replace(",", "", regex=False), errors="coerce"
            )
    for col in ["flow", "partner", "reporter", "commodity_code", "classification",
                "currency", "quantity_unit"]:
        if col in out:
            out[col] = out[col].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

    if "flow" in out:
        f = out["flow"].astype("string").str.casefold()
        out["flow"] = f.replace({
            "imports": "Import", "import": "Import", "m": "Import",
            "exports": "Export", "export": "Export", "x": "Export",
        }).astype("string")
    if "commodity_code" in out:
        out["commodity_code"] = out["commodity_code"].astype("string").str.replace(r"\.0$", "", regex=True)
    if "estimated_weight" in out:
        raw = out["estimated_weight"].astype("string").str.strip().str.casefold()
        out["estimated_weight"] = raw.isin(["true", "1", "yes", "y", "t"])

    out["source_row"] = [int(i) + 2 if isinstance(i, int) else str(i) for i in frame.index]
    out["source_file"] = "uploaded_dataset"
    report = validate_standard_frame(out)
    return out.reset_index(drop=True), report

def validate_standard_frame(frame: pd.DataFrame) -> dict:
    problems = []
    missing_required_values = {}
    for col in REQUIRED:
        n = int(frame[col].isna().sum())
        if n:
            missing_required_values[col] = n
    invalid_year = int((frame["year"].isna() | (frame["year"] < 1900) | (frame["year"] > 2100)).sum())
    invalid_value = int(frame["trade_value"].isna().sum())
    invalid_flow = int((~frame["flow"].astype("string").str.casefold().isin(["import", "export"])).sum())
    if invalid_year:
        problems.append(f"{invalid_year} rows have missing or implausible years.")
    if invalid_value:
        problems.append(f"{invalid_value} rows have missing or non-numeric trade values.")
    if invalid_flow:
        problems.append(f"{invalid_flow} rows have flow values other than Import or Export.")
    if missing_required_values:
        problems.append("Missing values in required fields: " + str(missing_required_values))
    valid_commodity_rows = 0
    if "commodity_code" in frame:
        valid_commodity_rows = int(frame["commodity_code"].notna().sum())
    return {
        "valid": not problems,
        "rows": int(len(frame)),
        "columns_mapped": [c for c in frame.columns if c not in ["source_row", "source_file"]],
        "missing_required_values": missing_required_values,
        "invalid_year_rows": invalid_year,
        "invalid_trade_value_rows": invalid_value,
        "invalid_flow_rows": invalid_flow,
        "commodity_code_rows": valid_commodity_rows,
        "has_quantity": "quantity" in frame and frame["quantity"].notna().any(),
        "has_net_weight": "net_weight" in frame and frame["net_weight"].notna().any(),
        "problems": problems,
        "analysis_capabilities": {
            "monetary_partner_analysis": not any(x in missing_required_values for x in ["year", "flow", "partner", "trade_value"]) and invalid_year == 0 and invalid_value == 0 and invalid_flow == 0,
            "commodity_analysis": "commodity_code" in frame and frame["commodity_code"].notna().any(),
            "quantity_analysis": "quantity" in frame and frame["quantity"].notna().any(),
            "weight_analysis": "net_weight" in frame and frame["net_weight"].notna().any(),
        }
    }
