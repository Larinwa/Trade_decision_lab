from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

def save_run(output_dir, source_name, validation, quality, rankings, sensitivity, decisions):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "dataset_validation.csv": pd.DataFrame([{"item": k, "value": str(v)} for k, v in validation.items()]),
        "model_a_quality_findings.csv": quality,
        "model_b_partner_rankings.csv": rankings,
        "model_b_sensitivity.csv": sensitivity,
        "model_c_decision_implications.csv": decisions,
    }
    for name, frame in tables.items():
        frame.to_csv(out / name, index=False)
    metadata = {"source_file": source_name, "validation": validation,
                "rows_quality_findings": len(quality), "rows_rankings": len(rankings),
                "rows_sensitivity": len(sensitivity), "rows_decisions": len(decisions)}
    (out / "run_metadata.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    lines = ["# Trade Decision Lab — Analysis Report", "", f"Input file: **{source_name}**", "",
             "## Dataset validation", "", f"- Rows: {validation['rows']:,}",
             f"- Monetary partner analysis supported: {validation['analysis_capabilities']['monetary_partner_analysis']}",
             f"- Commodity analysis supported: {validation['analysis_capabilities']['commodity_analysis']}",
             f"- Quantity analysis supported: {validation['analysis_capabilities']['quantity_analysis']}",
             f"- Weight analysis supported: {validation['analysis_capabilities']['weight_analysis']}", "",
             "## Model A — Data quality findings", "",
             quality.to_markdown(index=False) if not quality.empty else "No findings generated.", "",
             "## Model B — Analytical consequences", "",
             f"- Partner ranking rows: {len(rankings):,}",
             f"- Sensitivity comparisons: {len(sensitivity):,}", "",
             "## Model C — Potential decision implications", "",
             decisions.to_markdown(index=False) if not decisions.empty else "No decision assessment generated.", "",
             "## Interpretation boundary", "",
             "The report identifies data conditions and analytical sensitivity. It does not prove that a real decision-maker changed an actual decision. Screening flags are not confirmed errors. Results are limited to the uploaded dataset and fields available."]
    (out / "run_summary.md").write_text("\n".join(lines), encoding="utf-8")
