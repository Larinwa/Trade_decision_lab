from __future__ import annotations
import numpy as np
import pandas as pd

def _country_mask(series: pd.Series) -> pd.Series:
    labels = series.astype("string").fillna("").str.casefold().str.strip()
    aggregate = labels.isin(["world", "areas nes", "areas, nes", "other asia, nes",
                             "unspecified", "not elsewhere specified"])
    aggregate |= labels.str.contains(r"\b(?:nes|unspecified|world)\b", regex=True, na=False)
    return ~aggregate & labels.ne("")

def _safe_share(values: pd.Series) -> pd.Series:
    total = values.sum()
    return values / total * 100 if total else values * np.nan

def run_model_a(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    n = len(data)
    def add(rule, description, count, denominator=None, status=None, evidence=None):
        denom = denominator if denominator is not None else n
        pct = (count / denom * 100) if denom else np.nan
        rows.append({"rule": rule, "check": description, "status": status or ("Condition identified" if count else "No issue detected"),
                     "affected_rows": int(count), "denominator": int(denom),
                     "affected_pct": round(float(pct), 2) if pd.notna(pct) else np.nan,
                     "evidence": evidence or f"{int(count):,} of {int(denom):,} rows ({pct:.2f}%)." if denom else "No assessable rows."})
    for col in ["year", "flow", "partner", "trade_value"]:
        if col in data:
            count = int(data[col].isna().sum())
            add(f"Missing {col}", f"Missing values in {col}", count, evidence=f"{count:,} rows have missing {col}.")
    nonnumeric = int(data["trade_value"].isna().sum())
    add("Trade-value validity", "Missing/non-numeric trade values", nonnumeric,
        evidence=f"{nonnumeric:,} rows have no usable trade value.")
    neg = int((data["trade_value"] < 0).sum())
    zero = int((data["trade_value"] == 0).sum())
    add("Trade-value plausibility", "Negative or zero trade values", neg + zero,
        evidence=f"{neg:,} negative and {zero:,} zero trade values.")
    for col, label in [("quantity", "quantity"), ("net_weight", "net weight")]:
        if col in data:
            eligible = data["trade_value"].gt(0)
            missing = int((eligible & (data[col].isna() | data[col].le(0))).sum())
            denom = int(eligible.sum())
            add(f"{label.title()} completeness", f"Missing or non-positive {label}", missing, denom,
                evidence=f"{missing:,} of {denom:,} positive-value rows lack usable {label} ({(missing/denom*100 if denom else 0):.2f}%).")
    if "estimated_weight" in data and "net_weight" in data:
        positive = data["net_weight"].gt(0)
        estimated = int((positive & data["estimated_weight"].fillna(False)).sum())
        add("Estimated net weight", "Positive net weights marked estimated", estimated, int(positive.sum()),
            evidence=f"{estimated:,} of {int(positive.sum()):,} populated positive net weights are marked estimated.")
    if "commodity_code" in data:
        codes = data["commodity_code"].astype("string")
        malformed = int((codes.notna() & ~codes.str.fullmatch(r"\d{2,10}", na=False)).sum())
        add("Commodity-code format", "Non-numeric or malformed commodity codes", malformed,
            evidence=f"{malformed:,} rows have commodity codes outside the numeric 2–10 digit format.")
    dup_cols = [c for c in ["year", "flow", "reporter", "partner", "commodity_code", "trade_value"] if c in data]
    duplicates = int(data.duplicated(dup_cols, keep="first").sum()) if dup_cols else 0
    add("Duplicate records", "Exact duplicates on available trade keys and value", duplicates,
        evidence=f"{duplicates:,} duplicate rows detected using {dup_cols}.")
    if "net_weight" in data and "commodity_code" in data:
        tmp = data.copy()
        tmp["_uv"] = tmp["trade_value"] / tmp["net_weight"].where(tmp["net_weight"] > 0)
        group_cols = [c for c in ["flow", "year", "commodity_code"] if c in tmp]
        med = tmp["_uv"].where(_country_mask(tmp["partner"])).groupby([tmp[c] for c in group_cols], dropna=False).transform("median")
        ratio = tmp["_uv"] / med.where(med.ne(0))
        flagged = ratio.gt(3) | ratio.lt(1/3)
        flagged &= _country_mask(tmp["partner"]) & tmp["_uv"].notna()
        count = int(flagged.sum())
        add("Unit-value screening", "Potential unit-value anomalies (ratio > 3 or < 1/3)", count,
            evidence=f"{count:,} country-partner rows flagged. These are screening signals, not confirmed errors.")
    else:
        rows.append({"rule":"Unit-value screening","check":"Potential unit-value anomalies","status":"Not assessed",
                     "affected_rows":0,"denominator":0,"affected_pct":np.nan,
                     "evidence":"Not assessed because both commodity code and net weight are needed."})
    if "partner" in data:
        noncountry = int((~_country_mask(data["partner"])).sum())
        add("Aggregate partner labels", "Aggregate/non-country partner labels", noncountry,
            evidence=f"{noncountry:,} rows use aggregate or non-country partner labels; these are excluded from country rankings.")
    summary = pd.DataFrame(rows)
    trace = data[["source_file", "source_row"]].copy() if {"source_file", "source_row"}.issubset(data.columns) else pd.DataFrame()
    return summary, trace

def _rank(group: pd.DataFrame, treatment: str, commodity: str, year_label: str, top_n: int = 5):
    ranked = (group.groupby("partner", dropna=False, as_index=False)["trade_value"].sum()
              .sort_values("trade_value", ascending=False).reset_index(drop=True))
    total = ranked["trade_value"].sum()
    ranked["share_pct"] = _safe_share(ranked["trade_value"])
    ranked["rank"] = np.arange(1, len(ranked) + 1)
    hhi = float((ranked["share_pct"] ** 2).sum()) if total else np.nan
    cr5 = float(ranked.head(top_n)["share_pct"].sum()) if total else np.nan
    ranked = ranked.head(top_n).copy()
    ranked["treatment"] = treatment
    ranked["commodity_code"] = commodity
    ranked["period"] = year_label
    ranked["hhi"] = hhi
    ranked["cr5_pct"] = cr5
    ranked["records_retained"] = len(group)
    return ranked

def run_model_b(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if "commodity_code" not in data or data["commodity_code"].isna().all():
        return pd.DataFrame(), pd.DataFrame()
    base = data.copy()
    base["commodity_code"] = base["commodity_code"].astype("string")
    base = base[base["commodity_code"].notna() & base["trade_value"].notna() & base["year"].notna()]
    # UN Comtrade uses TOTAL for aggregate trade, not a commodity code. Keep
    # those records available to Model A, but never rank TOTAL as a product.
    base = base[~base["commodity_code"].astype("string").str.strip().str.upper().isin(
        ["TOTAL", "ALL", "ALL COMMODITIES", "TOTAL COMMODITIES"]
    )]
    base = base[_country_mask(base["partner"]) & base["trade_value"].gt(0)]
    if base.empty:
        return pd.DataFrame(), pd.DataFrame()
    # Keep each classification/commodity/year in the data; use calendar-year groups
    # to avoid silently combining incompatible classification versions.
    if "classification" not in base:
        base["classification"] = "unspecified"
    base["classification"] = base["classification"].fillna("unspecified").astype("string")
    periods = sorted(base["year"].dropna().astype(int).unique())
    if len(periods) > 3:
        recent = periods[-3:]
        scenarios = {"Full available period": periods, "Most recent three years": recent}
    else:
        scenarios = {"Available period": periods}
    rank_rows, sensitivity_rows = [], []
    for scenario, years in scenarios.items():
        for (commodity, classification), subset in base[base["year"].isin(years)].groupby(["commodity_code", "classification"], dropna=False):
            period_label = f"{min(years)}–{max(years)} ({classification})"
            treatments = {"Country-only baseline": subset}
            if "net_weight" in subset and subset["net_weight"].notna().any():
                treatments["Positive net-weight only"] = subset[subset["net_weight"].gt(0)]
                treatments["Reported-weight only"] = (subset[subset["net_weight"].gt(0) & ~subset.get("estimated_weight", pd.Series(False, index=subset.index)).fillna(False)]
                                                       if "estimated_weight" in subset else subset[subset["net_weight"].gt(0)])
            if "flag_unit_value" not in subset.columns:
                subset = subset.copy()
                subset["flag_unit_value"] = False
                if "net_weight" in subset and subset["net_weight"].notna().any():
                    uv = subset["trade_value"] / subset["net_weight"].where(subset["net_weight"] > 0)
                    med = uv.groupby([subset["year"], subset["commodity_code"]]).transform("median")
                    ratio = uv / med.where(med.ne(0))
                    subset["flag_unit_value"] = ratio.gt(3) | ratio.lt(1/3)
            if "net_weight" in subset and subset["net_weight"].notna().any():
                treatments["Unit-value screen excluded"] = subset[~subset["flag_unit_value"].fillna(False)]
            base_rank = _rank(subset, "Country-only baseline", str(commodity), period_label)
            for treatment, treated in treatments.items():
                ranked = _rank(treated, treatment, str(commodity), period_label)
                rank_rows.extend(ranked.to_dict("records"))
                baseline_top = base_rank["partner"].iloc[0] if not base_rank.empty else None
                treated_top = ranked["partner"].iloc[0] if not ranked.empty else None
                base_set = set(base_rank["partner"].astype(str))
                treated_set = set(ranked["partner"].astype(str))
                sensitivity_rows.append({
                    "scenario": scenario, "period": period_label, "commodity_code": str(commodity),
                    "classification": str(classification), "treatment": treatment,
                    "baseline_top1": baseline_top, "treatment_top1": treated_top,
                    "top1_changed": bool(baseline_top is not None and treated_top is not None and baseline_top != treated_top),
                    "top5_membership_changed": base_set != treated_set,
                    "baseline_hhi": float(base_rank["hhi"].iloc[0]) if not base_rank.empty else np.nan,
                    "treatment_hhi": float(ranked["hhi"].iloc[0]) if not ranked.empty else np.nan,
                    "hhi_difference": (float(ranked["hhi"].iloc[0]) - float(base_rank["hhi"].iloc[0])) if not ranked.empty and not base_rank.empty else np.nan,
                    "baseline_cr5_pct": float(base_rank["cr5_pct"].iloc[0]) if not base_rank.empty else np.nan,
                    "treatment_cr5_pct": float(ranked["cr5_pct"].iloc[0]) if not ranked.empty else np.nan,
                    "cr5_difference_pp": (float(ranked["cr5_pct"].iloc[0]) - float(base_rank["cr5_pct"].iloc[0])) if not ranked.empty and not base_rank.empty else np.nan,
                    "records_retained": int(len(treated)),
                })
    return pd.DataFrame(rank_rows), pd.DataFrame(sensitivity_rows)

def run_model_c(quality: pd.DataFrame, sensitivity: pd.DataFrame) -> pd.DataFrame:
    if sensitivity.empty:
        return pd.DataFrame([{"status":"Insufficient analytical evidence",
                              "implication":"Commodity-level partner comparisons could not be produced from the available fields.",
                              "limitation":"A commodity code and usable trade values are required."}])
    output = []
    for row in sensitivity[sensitivity["treatment"] != "Country-only baseline"].to_dict("records"):
        top_changed = bool(row["top1_changed"])
        top5_changed = bool(row["top5_membership_changed"])
        hhi_delta = row["hhi_difference"]
        if top_changed or top5_changed or (pd.notna(hhi_delta) and abs(hhi_delta) > 1e-9):
            status = "Potentially decision-relevant analytical sensitivity"
            parts = []
            if top_changed:
                parts.append(f"The leading partner changes from {row['baseline_top1']} to {row['treatment_top1']}.")
            if top5_changed:
                parts.append("The composition of the top-five partner group changes.")
            if pd.notna(hhi_delta) and abs(hhi_delta) > 1e-9:
                parts.append(f"HHI changes by {hhi_delta:.2f} points.")
            implication = " ".join(parts) + " Partner prioritisation or concentration assessments may therefore depend on the data treatment used."
        else:
            status = "No change observed under this treatment"
            implication = "No change was observed in the tested partner ranking or concentration measures; this does not establish overall data accuracy."
        output.append({**row, "status":status, "potential_decision_implication":implication,
                       "interpretation_limit":"Potential relevance only; this analysis does not observe an actual decision changing."})
    return pd.DataFrame(output)
