from __future__ import annotations
import ast
import numpy as np
import pandas as pd

from . import config


def _weight_evidence(prepared: pd.DataFrame, flow_desc: str, hs_code: str, years: list[int], classification: str):
    d = prepared[
        prepared["is_hs4"]
        & prepared["flowDesc"].fillna("").str.casefold().eq(str(flow_desc).casefold())
        & prepared["cmdCode"].astype(str).eq(str(hs_code))
        & prepared["refYear"].isin(years)
        & prepared["classificationCode"].fillna("UNSPECIFIED").astype(str).eq(str(classification))
        & prepared["is_country"]
    ]
    total = d["primaryValue"].sum()
    if d.empty or total <= 0:
        return {"reported_weight_value_share_pct": np.nan, "estimated_weight_value_share_pct": np.nan,
                "present_unverified_weight_value_share_pct": np.nan, "missing_weight_value_share_pct": np.nan, "weight_estimation_indicators_available": False,
                "unit_value_evidence": "Insufficient records"}
    shares = d.groupby("weight_state")["primaryValue"].sum().div(total).mul(100)
    estimation_known = d["weight_state"].isin(["reported", "estimated"]).any()
    reported = float(shares.get("reported", 0.0)) if estimation_known else np.nan
    estimated = float(shares.get("estimated", 0.0)) if estimation_known else np.nan
    present_unverified = float(shares.get("present_unverified", 0.0)) if not estimation_known else np.nan
    missing = float(shares.get("missing", 0.0))
    if not estimation_known:
        evidence_status = "Weight estimation status unavailable; present weights cannot be assumed reported."
    elif reported < config.REPORTED_WEIGHT_VALUE_SHARE_MIN_PCT:
        evidence_status = "Limited: reported net-weight share is below the 50% reference threshold."
    else:
        evidence_status = "Reported net-weight share meets the 50% reference threshold."
    return {"reported_weight_value_share_pct": reported,
            "estimated_weight_value_share_pct": estimated,
            "present_unverified_weight_value_share_pct": present_unverified,
            "missing_weight_value_share_pct": missing,
            "weight_estimation_indicators_available": bool(estimation_known),
            "unit_value_evidence": evidence_status}



def _baseline_present(value):
    """Accept populated pipe-delimited or serialised baseline partner lists."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return False
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ("nan", "none", "null", "[]"):
            return False
        if " | " in value:
            return any(part.strip() for part in value.split(" | "))
        try:
            parsed = ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return bool(value)  # A single named partner is still a valid baseline.
        return isinstance(parsed, (list, tuple)) and len(parsed) > 0
    return isinstance(value, (list, tuple)) and len(value) > 0


def _fitness_for_use(period, has_baseline, top1_changed, top5_changed,
                     concentration_changed, evidence):
    """Transparent screening rules, not empirical validation of decisions."""
    records = int(period.get('records', 0) or 0)
    partners = int(period.get('country_partners', 0) or 0)
    outcome = {}
    if not has_baseline or records < 5 or partners < 3:
        verdict = 'Insufficient evidence'
        reason = f'Only {records} records and {partners} country partners; a usable comparison baseline and at least 5 records across 3 partners are required.'
        action = 'Obtain additional partner-level observations and establish a valid baseline before prioritising partners.'
    elif top1_changed or top5_changed:
        verdict = 'Use with caution'
        reason = 'The leading partner or top-five shortlist changes under at least one tested treatment.'
        action = 'Compare partner shortlists across treatments and verify the affected records before acting.'
    else:
        verdict = 'Supported with limitations'
        reason = 'Partner rankings remained stable under the tested treatments; this does not prove the data are representative or accurate.'
        action = 'Use only as a preliminary shortlist, documenting data coverage and treatment assumptions.'
    outcome.update(partner_prioritisation_fitness=verdict, partner_prioritisation_reason=reason, partner_prioritisation_action=action)
    if not has_baseline or records < 5 or partners < 3:
        verdict = 'Insufficient evidence'
        reason = f'Only {records} records and {partners} country partners; a valid baseline and at least 5 records across 3 partners are required.'
        action = 'Expand and verify partner coverage before interpreting concentration.'
    elif concentration_changed:
        verdict = 'Use with caution'
        reason = 'HHI or CR5 changes under at least one tested treatment.'
        action = 'Report the treatment and range of concentration estimates rather than one unqualified figure.'
    else:
        verdict = 'Supported with limitations'
        reason = 'Concentration measures remained stable under the tested treatments, but coverage and measurement limitations remain.'
        action = 'Present concentration as a preliminary descriptive measure with documented coverage.'
    outcome.update(concentration_fitness=verdict, concentration_reason=reason, concentration_action=action)
    share = evidence.get('reported_weight_value_share_pct')
    if records < 5 or partners < 2 or pd.isna(share):
        verdict = 'Insufficient evidence'
        reason = 'Too few records or partners, or no verified reported-weight share for a meaningful comparison.'
        action = 'Obtain verified net-weight data and enough comparable partner observations.'
    elif share < 50:
        verdict = 'Use with caution'
        reason = f'Only {share:.2f}% of trade value has reported net-weight evidence, below the 50% screening threshold.'
        action = 'Verify weights and compare like-for-like commodities and measurement units before interpreting unit values.'
    else:
        verdict = 'Use with caution'
        reason = f'Reported net-weight evidence covers {share:.2f}% of trade value, but weight coverage alone does not establish product comparability.'
        action = 'Check product specifications, units, valuation and outliers before making price comparisons.'
    outcome.update(unit_value_fitness=verdict, unit_value_reason=reason, unit_value_action=action)
    return outcome

def run_decision_assessment(prepared: pd.DataFrame, comparison: dict, flow_desc: str):
    sensitivity = comparison.get("sensitivity", pd.DataFrame())
    periods = comparison.get("periods", pd.DataFrame())
    if periods.empty:
        return pd.DataFrame()
    rows = []
    for period in periods.to_dict("records"):
        hs = str(period["commodity_code"])
        years = [int(y) for y in str(period["years"]).split(",") if y]
        classification = str(period["classification"])
        key = (
            sensitivity["flow"].eq(flow_desc)
            & sensitivity["scenario"].eq(period["scenario"])
            & sensitivity["classification"].eq(classification)
            & sensitivity["commodity_code"].astype(str).eq(hs)
        )
        comparisons = sensitivity.loc[key]
        alternatives = comparisons[~comparisons["treatment"].isin(["country_only_baseline", "all_partner_labels_diagnostic"])]
        top1_changed = bool(alternatives["top1_changed"].fillna(False).any()) if len(alternatives) else False
        top5_changed = bool(alternatives["top5_membership_changed"].fillna(False).any()) if len(alternatives) else False
        concentration_changed = bool(alternatives["hhi_difference"].abs().gt(0).any() or alternatives["cr5_difference_pp"].abs().gt(0).any()) if len(alternatives) else False
        base = comparisons[comparisons["treatment"].eq("country_only_baseline")]
        has_baseline = len(base) == 1 and _baseline_present(base.iloc[0]["baseline_top5"])
        evidence = _weight_evidence(prepared, flow_desc, hs, years, classification)
        if not has_baseline:
            verdict = "Insufficient analytical evidence"
        elif top1_changed or top5_changed:
            verdict = "Ranking sensitive to tested treatments"
        elif concentration_changed:
            verdict = "Concentration metric changed; ranking membership stable"
        else:
            verdict = "No change observed in tested outputs"
        implications = []
        if top1_changed:
            implications.append("The leading partner changes under at least one tested treatment; market-prioritisation conclusions may be sensitive.")
        if top5_changed:
            implications.append("Top-five membership changes under at least one tested treatment; a partner shortlist may be sensitive.")
        if concentration_changed:
            implications.append("The HHI or CR5 measure changes; interpretation of partner concentration should report the treatment used.")
        if evidence["unit_value_evidence"].startswith("Limited"):
            implications.append("Unit-value evidence is limited by the share of trade value supported by reported net weight.")
        if not implications and not has_baseline:
            implications.append("A valid baseline is unavailable; analytical stability cannot be assessed.")
        if not implications:
            implications.append("No ranking or concentration change was observed under the tested treatments; this does not establish that all trade data are accurate or that a real decision is unaffected.")
        rows.append({
            "flow": flow_desc, "scenario": period["scenario"], "classification": classification,
            "years": period["years"], "commodity_code": hs,
            "commodity_description": period["commodity_description"], "records": period["records"],
            "country_partners": period["country_partners"], "decision_sensitivity": verdict,
            "top1_changed_under_test": top1_changed, "top5_membership_changed_under_test": top5_changed,
            "concentration_measure_changed": concentration_changed,
            **evidence,
            **_fitness_for_use(period, has_baseline, top1_changed, top5_changed, concentration_changed, evidence),
            "potential_decision_implication": " ".join(implications),
            "interpretation_limit": "This is a data-driven assessment of potential decision relevance, not evidence of an actual procurement or policy decision changing.",
        })
    return pd.DataFrame(rows)
