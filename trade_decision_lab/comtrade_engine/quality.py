from __future__ import annotations
import re
import numpy as np
import pandas as pd

from . import config
from . import schema
from .rules import RULES, FINDING_CLASSES

STATUS_CONDITION = "Condition identified"
STATUS_ANOMALY = "Potential anomaly"
STATUS_INFO = "Informational"
STATUS_NOT_ASSESSED = "Not assessed"
STATUS_NONE = "No issue detected by this check"

STRING_COLUMNS = ["cmdCode", "partnerDesc", "reporterDesc", "flowDesc", "classificationCode", "flowCode"]
NUMERIC_COLUMNS = ["primaryValue", "cifvalue", "fobvalue", "qty", "netWgt", "refYear", "partnerCode"]
TRACE_COLUMNS = ["source_file", "source_row"]


def cast_trade_types(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in STRING_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype("string").str.strip().replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    for col in NUMERIC_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _is_world(frame: pd.DataFrame) -> pd.Series:
    result = pd.Series(False, index=frame.index)
    if "partnerCode" in frame.columns:
        result |= pd.to_numeric(frame["partnerCode"], errors="coerce").eq(0)
    if "partnerDesc" in frame.columns:
        result |= frame["partnerDesc"].fillna("").str.casefold().eq("world")
    return result


def _is_non_country(description, code=None) -> bool:
    if pd.isna(description):
        return True
    if code is not None and pd.notna(code) and pd.to_numeric(code, errors="coerce") == 0:
        return True
    value = str(description).strip().casefold()
    patterns = [r"\bnes\b", r"unspecified", r"free zone", r"special categor", r"bunker", r"ship stores", r"not elsewhere"]
    return value == "world" or any(re.search(p, value) for p in patterns)


def _truthy(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.casefold().isin(["true", "1", "t", "yes", "y"])


def estimation_flags(frame: pd.DataFrame):
    if "isNetWgtEstimated" in frame.columns:
        net = _truthy(frame["isNetWgtEstimated"])
        qty = _truthy(frame["isQtyEstimated"]) if "isQtyEstimated" in frame.columns else None
        return net, qty, "explicit estimation indicators"
    if "legacyEstimationFlag" in frame.columns:
        flag = pd.to_numeric(frame["legacyEstimationFlag"], errors="coerce")
        return flag.isin([4, 6]), flag.isin([2, 6]), "legacyEstimationFlag"
    return None, None, "no estimation indicator supplied"


def prepare_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    frame = cast_trade_types(raw)
    if "source_row" not in frame.columns:
        frame["source_row"] = frame.index
    if "source_file" not in frame.columns:
        frame["source_file"] = "input_dataset"
    code = frame["cmdCode"].fillna("").astype("string")
    hs4 = code.str.fullmatch(r"\d{4}").fillna(False)
    if "aggrLevel" in frame.columns:
        level = pd.to_numeric(frame["aggrLevel"], errors="coerce")
        hs4 &= level.eq(4) | level.isna()
    frame["is_hs4"] = hs4.astype(bool)
    if "partnerCode" in frame.columns:
        frame["is_country"] = [not _is_non_country(d, c) for d, c in zip(frame["partnerDesc"], frame["partnerCode"])]
    else:
        frame["is_country"] = [not _is_non_country(d) for d in frame["partnerDesc"]]

    frame["flag_missing_qty"] = frame["qty"].isna() | frame["qty"].eq(0) if "qty" in frame.columns else True
    frame["flag_missing_wgt"] = frame["netWgt"].isna() | frame["netWgt"].eq(0) if "netWgt" in frame.columns else True
    net_est, qty_est, estimation_source = estimation_flags(frame)
    has_weight = frame["netWgt"].gt(0).fillna(False) if "netWgt" in frame.columns else pd.Series(False, index=frame.index)
    if net_est is None:
        frame["weight_state"] = np.where(has_weight, "present_unverified", "missing")
    else:
        frame["weight_state"] = np.where(~has_weight, "missing", np.where(net_est.fillna(False), "estimated", "reported"))
    frame["estimation_source"] = estimation_source

    frame["unit_value"] = frame["primaryValue"].div(frame["netWgt"].where(frame["netWgt"].gt(0))) if "netWgt" in frame.columns else np.nan
    group_cols = [c for c in ["cmdCode", "refYear", "classificationCode"] if c in frame.columns]
    country = frame["is_country"]
    med = frame["unit_value"].where(country).groupby([frame[c] for c in group_cols]).transform("median")
    ratio = frame["unit_value"].div(med.where(med.ne(0)))
    frame["unit_value_ratio"] = ratio
    frame["flag_unit_value_anomaly"] = ((ratio > config.UNIT_VALUE_HIGH_RATIO) | (ratio < config.UNIT_VALUE_LOW_RATIO)) & country

    reported_weight = frame["weight_state"].isin(["reported", "present_unverified"]) & country
    med_reported = frame["unit_value"].where(reported_weight).groupby([frame[c] for c in group_cols]).transform("median")
    reported_ratio = frame["unit_value"].div(med_reported.where(med_reported.ne(0)))
    frame["flag_uv_reported_only"] = ((reported_ratio > config.UNIT_VALUE_HIGH_RATIO) | (reported_ratio < config.UNIT_VALUE_LOW_RATIO)) & reported_weight
    return frame


def analysis_frame(prepared: pd.DataFrame) -> pd.DataFrame:
    return prepared.loc[prepared["is_hs4"]].copy()


def _pct(n, denominator):
    return round(float(n) / float(denominator) * 100, 2) if denominator else np.nan


def _source_rows(frame, mask):
    return frame.loc[mask, "source_row"].tolist()


def _finding(rule_id, status, finding_class, evidence, rows=None, value=None, share=None, source_rows=None, scope="dataset"):
    dimension, check, basis = RULES[rule_id]
    return {
        "rule_id": rule_id, "dimension": dimension, "check": check, "basis": basis,
        "scope": scope, "status": status, "finding_class": finding_class,
        "rows_affected": None if rows is None else int(rows),
        "value_affected_usd": None if value is None else float(value),
        "share_of_value_pct": None if share is None else float(share),
        "evidence": evidence, "source_rows": [int(x) for x in (source_rows or [])],
    }


def dq12_detail(prepared: pd.DataFrame, tolerance: float | None = None) -> pd.DataFrame:
    tolerance = config.DQ12_ABSOLUTE_TOLERANCE_USD if tolerance is None else float(tolerance)
    keys = [c for c in ["refYear", "flowCode", "cmdCode", "classificationCode", "partner2Code", "motCode", "customsCode"] if c in prepared.columns]
    frame = prepared.copy()
    group_keys = frame[keys].astype("string").fillna("__MISSING__")
    group_id = group_keys.groupby(keys, sort=False, dropna=False).ngroup()
    world = _is_world(frame)
    values = pd.to_numeric(frame["primaryValue"], errors="coerce")
    records = []
    for gid, idx in pd.Series(frame.index, index=group_id).groupby(level=0, sort=False):
        loc = idx.tolist()
        part = frame.loc[loc]
        wmask = world.loc[loc]
        wrows = int(wmask.sum())
        prows = int((~wmask).sum())
        missing = int(values.loc[loc].isna().sum())
        if wrows != 1 or prows == 0 or missing:
            reason = "missing_world_row" if wrows == 0 else "multiple_world_rows" if wrows > 1 else "no_partner_rows" if prows == 0 else "missing_primary_value"
            world_total = np.nan
            partner_total = np.nan
            difference = np.nan
            assessable = False
        else:
            world_total = float(values.loc[loc][wmask.to_numpy()].sum())
            partner_total = float(values.loc[loc][(~wmask).to_numpy()].sum())
            difference = world_total - partner_total
            assessable = True
            reason = "assessed"
        key_values = group_keys.loc[loc[0]].to_dict()
        records.append({**key_values, "world_value": world_total, "partner_total": partner_total,
                        "difference": difference, "absolute_difference": abs(difference) if assessable else np.nan,
                        "world_rows": wrows, "partner_rows": prows, "missing_primary_value_rows": missing,
                        "assessable": assessable, "assessment_note": reason,
                        "source_rows": part["source_row"].tolist()})
    result = pd.DataFrame(records)
    if result.empty:
        return result
    result["exceeds_tolerance"] = result["assessable"] & result["absolute_difference"].gt(tolerance)
    return result.sort_values("absolute_difference", ascending=False, na_position="last").reset_index(drop=True)


def _audit_rule_findings(v, schema_report, total_raw, flow_desc):
    findings = []
    findings.append(_finding("DQ-00", STATUS_NONE if schema_report["valid"] else STATUS_CONDITION,
        "condition" if not schema_report["valid"] else "informational", str(schema_report)))

    n = len(v)
    missing_value = v["primaryValue"].isna()
    findings.append(_finding("DQ-01", STATUS_CONDITION if missing_value.any() else STATUS_NONE, "condition",
        f"primaryValue missing on {int(missing_value.sum()):,} of {n:,} records ({_pct(missing_value.sum(), n)}%).",
        rows=missing_value.sum(), source_rows=_source_rows(v, missing_value)))

    aux_parts = []
    for col in ["cifvalue", "fobvalue"]:
        if col in v.columns:
            aux_parts.append(f"{col}: {int(v[col].isna().sum()):,} missing ({_pct(v[col].isna().sum(), n)}%)")
    aux_missing = sum(int(v[c].isna().sum()) for c in ["cifvalue", "fobvalue"] if c in v.columns)
    findings.append(_finding("DQ-02", STATUS_CONDITION if aux_missing else STATUS_NONE, "condition" if aux_missing else "informational",
        "; ".join(aux_parts) if aux_parts else "CIF/FOB columns are not present."))

    for measure, flag in [("qty", "flag_missing_qty"), ("netWgt", "flag_missing_wgt")]:
        pos = v["primaryValue"].gt(0)
        mask = pos & v[flag]
        value_total = v.loc[pos, "primaryValue"].sum()
        affected_value = v.loc[mask, "primaryValue"].sum()
        state_text = ""
        if measure == "netWgt":
            shares = v.loc[pos].groupby("weight_state")["primaryValue"].sum().div(value_total).mul(100).round(2).to_dict() if value_total else {}
            state_text = f" Weight-state shares of positive trade value: {shares}."
        findings.append(_finding("DQ-03", STATUS_CONDITION if mask.any() else STATUS_NONE, "condition",
            f"{int(mask.sum()):,} of {int(pos.sum()):,} positive-value records lack usable {measure} ({_pct(mask.sum(), pos.sum())}% of records; {_pct(affected_value, value_total)}% of value).{state_text}",
            rows=mask.sum(), value=affected_value, share=_pct(affected_value, value_total), source_rows=_source_rows(v, mask), scope=measure))

    key_cols = [c for c in ["refYear", "flowCode", "partnerDesc", "cmdCode"] if c in v.columns]
    key_missing = v[key_cols].isna().any(axis=1)
    findings.append(_finding("DQ-04", STATUS_CONDITION if key_missing.any() else STATUS_NONE, "condition",
        f"{int(key_missing.sum()):,} records have missing key identifiers across {key_cols}.", rows=key_missing.sum(), source_rows=_source_rows(v, key_missing)))

    negative = v["primaryValue"].lt(0)
    zero = v["primaryValue"].eq(0)
    findings.append(_finding("DQ-05", STATUS_CONDITION if negative.any() else STATUS_ANOMALY if zero.any() else STATUS_NONE,
        "condition" if negative.any() else "potential_anomaly", f"{int(negative.sum()):,} negative and {int(zero.sum()):,} zero primaryValue records.",
        rows=(negative | zero).sum(), source_rows=_source_rows(v, negative | zero)))

    code = v["cmdCode"].fillna("").astype(str)
    digits = code.str.fullmatch(r"\d+")
    malformed = (~digits & ~code.str.upper().eq("TOTAL")) | (digits & ~code.str.len().isin([2, 4, 6]))
    if "aggrLevel" in v.columns:
        levels = pd.to_numeric(v["aggrLevel"], errors="coerce")
        malformed |= digits & levels.notna() & levels.ne(code.str.len().astype(int))
    findings.append(_finding("DQ-06", STATUS_CONDITION if malformed.any() else STATUS_NONE, "condition",
        f"{int(malformed.sum()):,} malformed or level-inconsistent commodity codes; {int((~v['is_hs4']).sum()):,} records are outside the HS4 analytical subset.",
        rows=malformed.sum(), source_rows=_source_rows(v, malformed)))

    bad_year = ~pd.to_numeric(v["refYear"], errors="coerce").isin(config.EXPECTED_YEARS)
    bad_flow = v["flowDesc"].fillna("").str.casefold().ne(str(flow_desc).casefold())
    if "reporterCode" in v.columns:
        bad_reporter = pd.to_numeric(v["reporterCode"], errors="coerce").ne(config.EXPECTED_REPORTER_CODE)
    else:
        bad_reporter = ~v["reporterDesc"].fillna("").str.casefold().str.contains("nigeria")
    scope_bad = bad_year | bad_flow | bad_reporter
    findings.append(_finding("DQ-07", STATUS_CONDITION if scope_bad.any() else STATUS_NONE, "condition",
        f"Out-of-scope records: year={int(bad_year.sum())}, flow={int(bad_flow.sum())}, reporter={int(bad_reporter.sum())}.",
        rows=scope_bad.sum(), source_rows=_source_rows(v, scope_bad)))

    mapping = v.dropna(subset=["partnerCode", "partnerDesc"])
    code_multi = mapping.groupby("partnerCode")["partnerDesc"].nunique().gt(1)
    name_multi = mapping.groupby("partnerDesc")["partnerCode"].nunique().gt(1)
    map_bad = mapping["partnerCode"].isin(code_multi[code_multi].index) | mapping["partnerDesc"].isin(name_multi[name_multi].index)
    findings.append(_finding("DQ-08", STATUS_ANOMALY if map_bad.any() else STATUS_NONE, "potential_anomaly",
        f"{int(code_multi.sum())} partner codes map to multiple descriptions; {int(name_multi.sum())} descriptions map to multiple codes.",
        rows=map_bad.sum(), source_rows=_source_rows(mapping, map_bad)))

    original_cols = [c for c in v.columns if c not in ["is_hs4", "is_country", "flag_missing_qty", "flag_missing_wgt", "weight_state", "estimation_source", "unit_value", "unit_value_ratio", "flag_unit_value_anomaly", "flag_uv_reported_only"] + TRACE_COLUMNS]
    exact_dup = v.duplicated(subset=original_cols, keep="first")
    findings.append(_finding("DQ-09", STATUS_CONDITION if exact_dup.any() else STATUS_NONE, "condition",
        f"{int(exact_dup.sum()):,} exact duplicate records (trace columns and derived fields excluded).",
        rows=exact_dup.sum(), value=v.loc[exact_dup, "primaryValue"].sum(), source_rows=_source_rows(v, exact_dup)))

    duplicate_keys = [c for c in ["refYear", "reporterCode", "flowCode", "partnerCode", "partner2Code", "cmdCode", "classificationCode", "motCode", "customsCode"] if c in v.columns]
    duplicate_mask = v.duplicated(subset=duplicate_keys, keep=False)
    duplicate_group = v.loc[duplicate_mask]
    if len(duplicate_group):
        conflict = duplicate_group.groupby(duplicate_keys, dropna=False)["primaryValue"].transform("nunique").gt(1)
        conflict_rows = duplicate_group.loc[conflict]
    else:
        conflict_rows = duplicate_group
    findings.append(_finding("DQ-10", STATUS_ANOMALY if len(conflict_rows) else STATUS_NONE, "potential_anomaly",
        f"{int(duplicate_mask.sum()):,} records share a trade key; {int(len(conflict_rows)):,} records belong to keys with conflicting primaryValue.",
        rows=len(conflict_rows), source_rows=conflict_rows["source_row"].tolist() if len(conflict_rows) else []))

    non_country = ~v["is_country"]
    non_world_non_country = non_country & ~_is_world(v)
    partner_value = v.loc[~_is_world(v), "primaryValue"].sum()
    aggregate_value = v.loc[non_world_non_country, "primaryValue"].sum()
    findings.append(_finding("DQ-11", STATUS_INFO if non_country.any() else STATUS_NONE, "informational",
        f"{int(non_country.sum()):,} non-country/aggregate records including World; {int(non_world_non_country.sum()):,} excluding World. Non-World aggregate rows represent {_pct(aggregate_value, partner_value)}% of non-World partner value.",
        rows=non_country.sum(), value=aggregate_value, share=_pct(aggregate_value, partner_value), source_rows=_source_rows(v, non_country)))

    reconciliation = dq12_detail(v)
    assessable = reconciliation[reconciliation["assessable"]] if len(reconciliation) else reconciliation
    flagged = assessable[assessable["exceeds_tolerance"]] if len(assessable) else assessable
    unassessed = len(reconciliation) - len(assessable)
    source_rows = [x for xs in flagged.get("source_rows", pd.Series(dtype=object)).tolist() for x in xs]
    findings.append(_finding("DQ-12", STATUS_ANOMALY if len(flagged) else STATUS_NONE, "potential_anomaly",
        f"{len(flagged):,} of {len(assessable):,} assessable groups exceed the project-defined ${config.DQ12_ABSOLUTE_TOLERANCE_USD:g} tolerance; {unassessed:,} groups could not be reconciled. Total absolute gap among flagged groups: ${flagged['absolute_difference'].sum() if len(flagged) else 0:,.2f}.",
        rows=sum(len(x) for x in flagged.get("source_rows", pd.Series(dtype=object)).tolist()),
        value=flagged["absolute_difference"].sum() if len(flagged) else 0.0, source_rows=source_rows))

    if total_raw is None:
        findings.append(_finding("DQ-13", STATUS_NOT_ASSESSED, "not_assessed", "Total-trade dataset was not supplied."))
    else:
        total = cast_trade_types(total_raw)
        total = total[total["flowDesc"].fillna("").str.casefold().eq(str(flow_desc).casefold())]
        if "cmdCode" in total.columns and total["cmdCode"].astype(str).str.upper().eq("TOTAL").any():
            total = total[total["cmdCode"].astype(str).str.upper().eq("TOTAL")]
        total_world = total.loc[_is_world(total)].groupby("refYear")["primaryValue"].sum()
        commodity_world = v.loc[_is_world(v)].groupby("refYear")["primaryValue"].sum()
        compare = pd.concat([total_world.rename("total_trade"), commodity_world.rename("commodity")], axis=1)
        compare["gap"] = compare["total_trade"] - compare["commodity"]
        excess = compare[compare["gap"] < -config.DQ13_ABSOLUTE_TOLERANCE_USD]
        shortfall = compare[compare["gap"] > config.DQ13_ABSOLUTE_TOLERANCE_USD]
        if len(excess):
            status, cls = STATUS_ANOMALY, "potential_anomaly"
        elif len(shortfall):
            status, cls = STATUS_INFO, "informational"
        else:
            status, cls = STATUS_NONE, "informational"
        findings.append(_finding("DQ-13", status, cls,
            f"Compared World totals for {str(flow_desc)} by year. Commodity totals exceed total-trade totals in {list(excess.index)}; commodity totals are below total-trade totals in {list(shortfall.index)}. A shortfall may reflect confidential, unclassified or otherwise non-itemised trade."))

    classifications = v.groupby("refYear")["classificationCode"].agg(lambda s: sorted(s.dropna().astype(str).unique().tolist()))
    versions = sorted({item for values in classifications for item in values})
    findings.append(_finding("DQ-14", STATUS_INFO if len(versions) > 1 else STATUS_NONE, "informational",
        f"Classification versions present: {versions}. Versions by year: {classifications.to_dict()}. Cross-version code equivalence has not been established."))

    country = v[v["is_country"]]
    flagged_uv = country["flag_unit_value_anomaly"]
    reported_flagged_uv = country["flag_uv_reported_only"]
    country_value = country["primaryValue"].sum()
    findings.append(_finding("DQ-15", STATUS_ANOMALY if flagged_uv.any() else STATUS_NONE, "potential_anomaly",
        f"{int(flagged_uv.sum()):,} country records flagged by the annual commodity median screen (ratio > {config.UNIT_VALUE_HIGH_RATIO:g} or < {config.UNIT_VALUE_LOW_RATIO:.4f}); {int(reported_flagged_uv.sum()):,} when restricted to non-estimated weights. This is a screening result, not confirmation of error.",
        rows=flagged_uv.sum(), value=country.loc[flagged_uv, "primaryValue"].sum(), share=_pct(country.loc[flagged_uv, "primaryValue"].sum(), country_value), source_rows=_source_rows(country, flagged_uv)))

    coverage, partial_years = assess_coverage(v)
    findings.append(_finding("DQ-17", STATUS_ANOMALY if partial_years else STATUS_NONE, "potential_anomaly",
        f"Candidate partial years under the project-defined cross-year median screen: {partial_years or 'none'}. This is a coverage screen, not proof of incomplete source publication."))
    findings.append(_finding("DQ-18", STATUS_NOT_ASSESSED, "not_assessed", "Revision history is not available in the downloaded extracts."))
    findings.append(_finding("DQ-19", STATUS_NOT_ASSESSED, "not_assessed", "Partner-reported mirror data were not supplied; bilateral asymmetry was not assessed."))
    return findings, coverage, partial_years, reconciliation


def assess_coverage(frame: pd.DataFrame, ratio: float | None = None):
    ratio = config.PARTIAL_YEAR_COVERAGE_RATIO if ratio is None else float(ratio)
    data = frame.loc[~_is_world(frame)]
    if data.empty:
        return pd.DataFrame(), []
    grouped = data.groupby("refYear").agg(
        rows=("primaryValue", "size"),
        partners=("partnerDesc", "nunique"),
        commodities=("cmdCode", "nunique"),
    )
    for col in ["rows", "partners", "commodities"]:
        median = grouped[col].median()
        grouped[f"{col}_pct_of_median"] = (grouped[col] / median * 100).round(2) if median else np.nan
    metrics = [f"{c}_pct_of_median" for c in ["rows", "partners", "commodities"]]
    grouped["candidate_partial"] = grouped[metrics].lt(ratio * 100).any(axis=1)
    return grouped, [int(y) for y in grouped.index[grouped["candidate_partial"]]]


def run_audit(raw: pd.DataFrame, total_raw: pd.DataFrame | None = None, flow_desc: str | None = None):
    report = schema.validate_comtrade_frame(raw)
    prepared = prepare_dataset(raw)
    observed_flows = sorted(prepared["flowDesc"].dropna().astype(str).unique().tolist())
    if flow_desc is None:
        if len(observed_flows) != 1:
            raise ValueError(f"Pass flow_desc when the input contains multiple flows. Found: {observed_flows}")
        flow_desc = observed_flows[0]
    selected = prepared[prepared["flowDesc"].fillna("").str.casefold().eq(str(flow_desc).casefold())].copy()
    findings, coverage, partial, reconciliation = _audit_rule_findings(selected, report, total_raw, flow_desc)
    findings_frame = pd.DataFrame(findings)
    findings_frame["n_source_rows"] = findings_frame["source_rows"].map(len)
    audit = {
        "findings": findings_frame,
        "records": findings,
        "coverage": coverage,
        "partial_years": partial,
        "reconciliation": reconciliation,
        "schema": report,
        "flow_desc": flow_desc,
        "n_rows_input": int(len(raw)),
        "n_rows_scoped": int(len(selected)),
        "n_rows_hs4": int(selected["is_hs4"].sum()),
    }
    return prepared, audit


def findings_summary(audit: dict) -> pd.DataFrame:
    columns = ["rule_id", "dimension", "check", "status", "finding_class", "rows_affected", "value_affected_usd", "share_of_value_pct", "evidence"]
    return audit["findings"][columns].copy()


def findings_long(audit: dict) -> pd.DataFrame:
    rows = []
    for finding in audit["records"]:
        rows.extend({"rule_id": finding["rule_id"], "scope": finding["scope"], "source_row": row} for row in finding["source_rows"])
    return pd.DataFrame(rows, columns=["rule_id", "scope", "source_row"])
