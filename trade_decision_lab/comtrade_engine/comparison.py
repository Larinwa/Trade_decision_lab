from __future__ import annotations
import numpy as np
import pandas as pd

from . import config

TREATMENTS = {
    "country_only_baseline": "Country partners only; primaryValue retained regardless of quantity/weight availability.",
    "all_partner_labels_diagnostic": "Includes World and non-country labels; diagnostic only, not a valid country ranking.",
    "reported_weight_only_sensitivity": "Retains country records with reported net weight; sensitivity only because it also removes valid trade-value records.",
    "missing_weight_excluded_sensitivity": "Excludes country records with missing/zero net weight; sensitivity only, not a recommended trade-value cleaning step.",
    "reported_weight_uv_screen_sensitivity": "Excludes reported-weight unit-value screen flags; potential anomalies are not confirmed errors.",
    "notebook_uv_screen_sensitivity": "Excludes all notebook-style unit-value flags, including records with estimated weights; exploratory sensitivity only.",
}


def _periods(frame: pd.DataFrame):
    periods = {
        "A_historical": list(config.ANALYSIS_YEARS_A),
        "B_recent": list(config.ANALYSIS_YEARS_B),
    }
    output = []
    for scenario, years in periods.items():
        scoped = frame[frame["refYear"].isin(years)]
        if scoped.empty:
            continue
        classes = sorted(scoped["classificationCode"].dropna().astype(str).unique().tolist())
        if scoped["classificationCode"].isna().any():
            classes.append("UNSPECIFIED")
        for classification in classes:
            class_values = scoped["classificationCode"].fillna("UNSPECIFIED").astype(str)
            actual_years = sorted(scoped.loc[class_values.eq(classification), "refYear"].dropna().astype(int).unique().tolist())
            output.append({"scenario": scenario, "classification": classification, "years": actual_years})
    return output


def _apply_treatment(data: pd.DataFrame, treatment: str) -> pd.DataFrame:
    if treatment == "all_partner_labels_diagnostic":
        return data.copy()
    out = data[data["is_country"]].copy()
    if treatment == "reported_weight_only_sensitivity":
        return out[out["weight_state"].eq("reported")].copy()
    if treatment == "missing_weight_excluded_sensitivity":
        return out[~out["flag_missing_wgt"]].copy()
    if treatment == "reported_weight_uv_screen_sensitivity":
        return out[~out["flag_uv_reported_only"]].copy()
    if treatment == "notebook_uv_screen_sensitivity":
        return out[~out["flag_unit_value_anomaly"]].copy()
    return out


def _rank(data: pd.DataFrame, top_n: int):
    if data.empty:
        return pd.DataFrame(columns=["partnerCode", "partnerDesc", "trade_value_usd", "share_pct", "rank"]), np.nan, np.nan
    data = data.dropna(subset=["primaryValue"])
    if data.empty:
        return pd.DataFrame(columns=["partnerCode", "partnerDesc", "trade_value_usd", "share_pct", "rank"]), np.nan, np.nan
    grouped = data.groupby(["partnerCode", "partnerDesc"], dropna=False, as_index=False)["primaryValue"].sum()
    grouped = grouped.rename(columns={"primaryValue": "trade_value_usd"})
    total = grouped["trade_value_usd"].sum()
    grouped["share_pct"] = grouped["trade_value_usd"].div(total).mul(100) if total else np.nan
    grouped = grouped.sort_values(["trade_value_usd", "partnerDesc"], ascending=[False, True]).reset_index(drop=True)
    grouped["rank"] = np.arange(1, len(grouped) + 1)
    hhi = float((grouped["share_pct"].dropna() ** 2).sum()) if total else np.nan
    cr5 = float(grouped.head(5)["share_pct"].sum()) if total else np.nan
    return grouped.head(top_n), hhi, cr5


def run_comparison(prepared: pd.DataFrame, flow_desc: str, commodities: dict | None = None, top_n: int | None = None):
    commodities = commodities or config.SELECTED_COMMODITIES
    top_n = config.TOP_N if top_n is None else int(top_n)
    data = prepared[
        prepared["is_hs4"]
        & prepared["flowDesc"].fillna("").str.casefold().eq(str(flow_desc).casefold())
        & prepared["cmdCode"].astype(str).isin(commodities)
    ].copy()
    if data.empty:
        return {"rankings": pd.DataFrame(), "sensitivity": pd.DataFrame(), "periods": pd.DataFrame(), "flow_desc": flow_desc}

    periods = _periods(data)
    ranking_rows, sensitivity_rows, period_rows = [], [], []
    for period in periods:
        years = period["years"]
        class_mask = data["classificationCode"].fillna("UNSPECIFIED").astype(str).eq(period["classification"])
        for hs_code, hs_name in commodities.items():
            subset = data[class_mask & data["cmdCode"].astype(str).eq(str(hs_code)) & data["refYear"].isin(years)].copy()
            period_rows.append({"flow": flow_desc, "scenario": period["scenario"], "classification": period["classification"],
                                "years": ",".join(map(str, years)), "commodity_code": hs_code, "commodity_description": hs_name,
                                "records": len(subset), "country_partners": int(subset.loc[subset["is_country"], "partnerCode"].nunique())})
            treatment_results = {}
            for treatment, description in TREATMENTS.items():
                treated = _apply_treatment(subset, treatment)
                ranked, hhi, cr5 = _rank(treated, top_n)
                treatment_results[treatment] = {"ranked": ranked, "hhi": hhi, "cr5": cr5, "n_records": len(treated), "description": description}
                for row in ranked.to_dict("records"):
                    ranking_rows.append({
                        "flow": flow_desc, "scenario": period["scenario"], "classification": period["classification"],
                        "years": ",".join(map(str, years)), "commodity_code": hs_code, "commodity_description": hs_name,
                        "treatment": treatment, "treatment_description": description, **row,
                    })

            baseline = treatment_results["country_only_baseline"]
            base_ranked = baseline["ranked"]
            base_names = base_ranked["partnerDesc"].astype(str).tolist()
            base_top1 = base_names[0] if base_names else None
            base_set = set(base_names)
            for treatment, result in treatment_results.items():
                ranked = result["ranked"]
                names = ranked["partnerDesc"].astype(str).tolist()
                names_set = set(names)
                sensitivity_rows.append({
                    "flow": flow_desc, "scenario": period["scenario"], "classification": period["classification"],
                    "years": ",".join(map(str, years)), "commodity_code": hs_code, "commodity_description": hs_name,
                    "treatment": treatment, "treatment_description": result["description"],
                    "baseline_top1": base_top1, "treatment_top1": names[0] if names else None,
                    "top1_changed": bool(base_top1 is not None and names and base_top1 != names[0]) if treatment != "country_only_baseline" else False,
                    "baseline_top5": " | ".join(base_names), "treatment_top5": " | ".join(names),
                    "top5_membership_changed": bool(base_set != names_set) if treatment != "country_only_baseline" else False,
                    "top5_entries": " | ".join(sorted(names_set - base_set)),
                    "top5_exits": " | ".join(sorted(base_set - names_set)),
                    "baseline_hhi": baseline["hhi"], "treatment_hhi": result["hhi"],
                    "hhi_difference": result["hhi"] - baseline["hhi"] if pd.notna(result["hhi"]) and pd.notna(baseline["hhi"]) else np.nan,
                    "baseline_cr5_pct": baseline["cr5"], "treatment_cr5_pct": result["cr5"],
                    "cr5_difference_pp": result["cr5"] - baseline["cr5"] if pd.notna(result["cr5"]) and pd.notna(baseline["cr5"]) else np.nan,
                    "records_retained": result["n_records"],
                })
    return {
        "rankings": pd.DataFrame(ranking_rows),
        "sensitivity": pd.DataFrame(sensitivity_rows),
        "periods": pd.DataFrame(period_rows),
        "flow_desc": flow_desc,
        "treatment_definitions": TREATMENTS.copy(),
    }
