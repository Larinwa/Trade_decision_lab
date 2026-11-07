from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

from . import config
from . import quality, comparison, decision


def _attach_trace(frame: pd.DataFrame, filename: str) -> pd.DataFrame:
    out = frame.copy()
    if "source_file" not in out.columns:
        out["source_file"] = filename
    if "source_row" not in out.columns:
        out["source_row"] = out.index
    return out


def _write_csv(frame: pd.DataFrame, path: Path):
    if frame is not None:
        frame.to_csv(path, index=False)


def _write_markdown_report(output_dir: Path, audits: dict, comparisons: dict, decisions: dict):
    lines = [
        "# Trade Decision Lab — Run Summary", "",
        "Research project: *Garbage In, Garbage Out: Examining the Implications of Poor Data Quality for Decision-Making in Nigeria's Import–Export Sector*.", "",
        "## Scope", "",
        "This run processes the supplied UN Comtrade commodity-import, commodity-export and total-trade extracts. The three analytical components are descriptive and rule-based; no trained predictive model is used.", "",
    ]
    for flow, audit in audits.items():
        lines.extend([f"## Model A — {flow}", "",
                      f"- Input records: {audit['n_rows_input']:,}",
                      f"- Records in flow scope: {audit['n_rows_scoped']:,}",
                      f"- HS4 records available for Models B and C: {audit['n_rows_hs4']:,}",
                      f"- Candidate partial years: {audit['partial_years'] or 'None identified by the configured screen'}", "",
                      "### Findings", "",
                      "| Rule | Finding class | Status | Affected records | Evidence |",
                      "|---|---|---|---:|---|"])
        for row in audit["findings"].to_dict("records"):
            evidence = str(row["evidence"]).replace("|", "\\|")
            rows = "—" if pd.isna(row["rows_affected"]) else f"{int(row['rows_affected']):,}"
            lines.append(f"| {row['rule_id']} | {row['finding_class']} | {row['status']} | {rows} | {evidence} |")
        lines.append("")
        if flow in comparisons:
            comp = comparisons[flow]
            sens = comp.get("sensitivity", pd.DataFrame())
            dec = decisions.get(flow, pd.DataFrame())
            lines.extend([f"## Model B — {flow}", "",
                          f"- Ranking rows generated: {len(comp.get('rankings', [])):,}",
                          f"- Treatment comparisons generated: {len(sens):,}",
                          "- Historical Scenario A is partitioned by the classification version actually present in the data. This avoids silently combining H4 and H6 records.",
                          "- Trade-value rankings retain records with missing or estimated weights in the primary country-only baseline. Weight-based exclusions are sensitivity analyses only.", "",
                          f"## Model C — {flow}", "",
                          f"- Decision-assessment records: {len(dec):,}",
                          "- Outputs describe potential decision relevance. They do not demonstrate that a real decision-maker changed an actual decision.", ""])
    lines.extend(["## Interpretation limits", "",
        "- The partner-country classification uses a transparent description/code heuristic; it is not an authoritative UN M49 country-area lookup.",
        "- Unit-value flags are screening signals, not confirmed errors or direct price comparisons.",
        "- The 50% reported-weight reference is applied only as a qualification for weight-dependent evidence and is used by analogy; it is not a universal data-quality pass mark.",
        "- Classification versions are kept separate in the comparison outputs. Cross-version commodity-code equivalence has not been established.",
        "- Missing trade values, confidential trade, revisions and mirror-data asymmetries are not resolved by this prototype.",
        "- Decision outputs are analytical indicators, not sourcing recommendations, forecasts or proof of actual decision impact.", ""])
    (output_dir / "run_summary.md").write_text("\n".join(lines), encoding="utf-8")


def run_project(imports_raw: pd.DataFrame, exports_raw: pd.DataFrame, total_trade_raw: pd.DataFrame,
                output_dir, commodities: dict | None = None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    inputs = {
        "Import": _attach_trace(imports_raw, "commodity_imports_combined.csv"),
        "Export": _attach_trace(exports_raw, "commodity_exports_2016_2025.csv"),
    }
    total = _attach_trace(total_trade_raw, "un_comtrade_nigeria_2016_2025.csv")
    audits, comparisons, decisions = {}, {}, {}
    for flow, raw in inputs.items():
        prepared, audit = quality.run_audit(raw, total_raw=total, flow_desc=flow)
        comparison_result = comparison.run_comparison(prepared, flow, commodities=commodities)
        decision_result = decision.run_decision_assessment(prepared, comparison_result, flow)
        audits[flow] = audit
        comparisons[flow] = comparison_result
        decisions[flow] = decision_result

        flow_dir = output / flow.lower()
        flow_dir.mkdir(exist_ok=True)
        _write_csv(quality.findings_summary(audit), flow_dir / "model_a_findings.csv")
        _write_csv(prepared, flow_dir / "model_a_prepared_records.csv")
        _write_csv(quality.findings_long(audit), flow_dir / "model_a_source_row_traceability.csv")
        _write_csv(audit["coverage"].reset_index(), flow_dir / "model_a_year_coverage.csv")
        _write_csv(audit["reconciliation"].drop(columns=["source_rows"], errors="ignore"), flow_dir / "model_a_world_reconciliation.csv")
        _write_csv(comparison_result["periods"], flow_dir / "model_b_analysis_periods.csv")
        _write_csv(comparison_result["rankings"], flow_dir / "model_b_partner_rankings.csv")
        _write_csv(comparison_result["sensitivity"], flow_dir / "model_b_sensitivity_comparison.csv")
        _write_csv(decision_result, flow_dir / "model_c_decision_assessment.csv")

    for flow in ["Import", "Export"]:
        total_prepared, total_audit = quality.run_audit(total, total_raw=None, flow_desc=flow)
        audit_key = f"Total trade — {flow}"
        audits[audit_key] = total_audit
        total_dir = output / f"total_trade_{flow.lower()}"
        total_dir.mkdir(exist_ok=True)
        _write_csv(quality.findings_summary(total_audit), total_dir / "model_a_findings.csv")
        _write_csv(total_prepared, total_dir / "model_a_prepared_records.csv")
        _write_csv(quality.findings_long(total_audit), total_dir / "model_a_source_row_traceability.csv")
        _write_csv(total_audit["coverage"].reset_index(), total_dir / "model_a_year_coverage.csv")
        _write_csv(total_audit["reconciliation"].drop(columns=["source_rows"], errors="ignore"), total_dir / "model_a_world_reconciliation.csv")

    metadata = {
        "project_version": config.PROJECT_VERSION,
        "flows": list(inputs),
        "input_shapes": {flow: list(frame.shape) for flow, frame in inputs.items()},
        "total_trade_shape": list(total.shape),
        "commodities": commodities or config.SELECTED_COMMODITIES,
        "analysis_years_A": list(config.ANALYSIS_YEARS_A),
        "analysis_years_B": list(config.ANALYSIS_YEARS_B),
        "treatments": comparison.TREATMENTS,
    }
    (output / "run_metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    _write_markdown_report(output, audits, comparisons, decisions)
    return {"audits": audits, "comparisons": comparisons, "decisions": decisions, "output_dir": output}
