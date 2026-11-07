"""Trade Decision Lab: presentation interface for the preserved research pipeline."""
from __future__ import annotations

import io
import json
import os
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from trade_decision_lab.integration import load_file, run_analysis
from trade_decision_lab.comtrade_engine.schema import validate_comtrade_frame
from trade_decision_lab.comtrade_engine.quality import findings_summary
from trade_decision_lab.reporting import generate_reports
from trade_decision_lab.llm import chat

st.set_page_config(page_title="Trade Decision Lab | Research demonstration", page_icon="◈", layout="wide", initial_sidebar_state="collapsed")
st.markdown('''<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
html,body,[class*="css"],.stApp {font-family:'DM Sans',sans-serif}
.stApp {background:#f7f9fc;color:#172b42}
.block-container {max-width:1180px;padding-top:2rem;padding-bottom:4rem}
h1,h2,h3 {font-family:'Manrope',sans-serif;letter-spacing:-.035em}
.hero {background:linear-gradient(115deg,#102a43 0%,#143d57 58%,#126b72 100%);color:white;border-radius:22px;padding:42px 46px;margin-bottom:26px;position:relative;overflow:hidden}
.hero:after {content:'◈';position:absolute;right:45px;top:-80px;font-size:250px;opacity:.075}
.eyebrow {font-size:12px;letter-spacing:.15em;font-weight:800;text-transform:uppercase;color:#75e0c8}
.hero h1 {color:white;font-size:clamp(2rem,4vw,3.1rem);margin:14px 0 12px;max-width:730px;line-height:1.15}
.hero p {color:#d6e9f1;max-width:750px;font-size:16px;line-height:1.75}
.pill {display:inline-block;padding:7px 12px;border:1px solid #7297a7;border-radius:100px;color:#e5f8fa;font-size:12px;margin-right:7px;margin-top:14px}
.section-caption {font-size:12px;text-transform:uppercase;letter-spacing:.13em;color:#3c7c86;font-weight:800}
.soft-card {background:white;border:1px solid #e3eaf0;border-radius:16px;padding:22px 24px;margin-bottom:14px;box-shadow:0 3px 14px rgba(15,35,58,.025)}
.soft-card h3 {margin:0 0 6px;font-size:19px}
.soft-card p {color:#65788a;margin:0;line-height:1.65}
.step {display:inline-flex;align-items:center;justify-content:center;background:#dff5ef;color:#0d6b63;border-radius:9px;width:28px;height:28px;font-weight:800;margin-right:10px}
[data-testid="stMetric"] {background:white;border:1px solid #e3eaf0;border-radius:14px;padding:17px}
[data-testid="stFileUploader"] {background:white;border:1px dashed #a9c8ce;border-radius:13px;padding:12px}
.stButton button[kind="primary"] {background:#087f78;border:0;border-radius:10px;font-weight:700}
.stDownloadButton button {border-radius:10px;border:1px solid #b9d7d8;color:#126b72;font-weight:700;width:100%}
[data-testid="stChatMessage"] {border:1px solid #e5ecf1;border-radius:14px;background:white}
.small-note {color:#65788a;font-size:13px;line-height:1.6}
</style>''', unsafe_allow_html=True)


def secret(name, default=""):
    try:
        return st.secrets.get(name, os.environ.get(name, default))
    except Exception:
        return os.environ.get(name, default)


def validate_role(frame, role):
    validation = validate_comtrade_frame(frame, strict=False)
    if not validation["valid"]:
        raise ValueError(f"{role}: required UN Comtrade fields are missing or invalid. {validation}")
    if "flowCode" not in frame.columns:
        raise ValueError(f"{role}: flowCode is missing.")
    codes = set(frame["flowCode"].dropna().astype(str).str.strip().str.upper().unique())
    if role == "Imports" and codes != {"M"}:
        raise ValueError(f"Imports must contain only flowCode M. Found {sorted(codes)}.")
    if role == "Exports" and codes != {"X"}:
        raise ValueError(f"Exports must contain only flowCode X. Found {sorted(codes)}.")
    if role == "Total trade" and (not codes or not codes.issubset({"M", "X"})):
        raise ValueError(f"Total trade must contain M and/or X. Found {sorted(codes)}.")
    return codes


def compact_context(results, frames):
    context = {
        "scope": "Nigerian UN Comtrade commodity imports, exports and total trade. Preliminary rule-based screening; no observed organisational decisions.",
        "inputs": {role: {"records": len(frame), "columns": len(frame.columns)} for role, frame in frames.items()},
        "model_a": {}, "model_b": {}, "model_c": {},
        "interpretation": "Quality flags are not confirmed errors. Sensitivity is not correction. World aggregates are diagnostic, not additional countries. H4/H6 are classification revisions. Historical and recent H6 periods overlap. Fitness thresholds are prototype heuristics."
    }
    for flow, audit in results["audits"].items():
        findings = findings_summary(audit)
        context["model_a"][flow] = findings.head(12).where(pd.notna(findings), None).to_dict("records")
    for flow, comp in results["comparisons"].items():
        sens = comp["sensitivity"]
        alt = sens.loc[sens["treatment"].ne("country_only_baseline")].copy()
        top = alt["top1_changed"].astype(str).str.lower().eq("true")
        five = alt["top5_membership_changed"].astype(str).str.lower().eq("true")
        examples = []
        for _, row in alt.loc[top].head(3).iterrows():
            examples.append({k: row.get(k) for k in ["commodity_code", "commodity_description", "scenario", "treatment", "baseline_top1", "treatment_top1"]})
        context["model_b"][flow] = {"alternative_treatment_comparisons": len(alt), "leading_partner_changes": int(top.sum()), "top_five_membership_changes": int(five.sum()), "examples": examples}
    for flow, decisions in results["decisions"].items():
        cols = ["scenario", "classification", "years", "commodity_code", "commodity_description", "records", "country_partners", "partner_prioritisation_fitness", "partner_prioritisation_reason", "concentration_fitness", "concentration_reason", "unit_value_fitness", "unit_value_reason"]
        available = [c for c in cols if c in decisions.columns]
        selected = decisions.drop_duplicates(subset=["classification", "years", "commodity_code"], keep="last")
        context["model_c"][flow] = selected[available].where(pd.notna(selected[available]), None).to_dict("records")
    return json.dumps(context, ensure_ascii=False, default=str)


def offline_summary(results):
    parts = []
    for flow, comp in results["comparisons"].items():
        alt = comp["sensitivity"]
        alt = alt[alt["treatment"].ne("country_only_baseline")]
        n = int(alt["top1_changed"].astype(str).str.lower().eq("true").sum())
        parts.append(f"{flow.lower()} rankings changed their leading partner in {n} of {len(alt)} alternative-treatment comparisons")
    return ("### What we examined\nWe assessed supplied Nigerian UN Comtrade import, export and total-trade records. Model A screened data quality, Model B tested analytical sensitivity, and Model C evaluated whether the evidence could support three specific decisions.\n\n"
            "### What stood out\n" + "; ".join(parts).capitalize() + ". These comparisons include diagnostic scenarios, not corrections.\n\n"
            "### What this means for decisions\nThe evidence may support some uses with caution while remaining insufficient for others. The detailed Model C assessments explain the judgement for each commodity and period.\n\n"
            "### What we cannot conclude\nScreening flags do not prove errors, changes in rankings do not establish better decisions, and no actual organisational decisions were observed.\n\n"
            "**For the complete findings, explanations and recommended actions, download the full technical PDF report below.**")


SYSTEM = ("You are a careful research communication assistant for Trade Decision Lab. Use only the supplied evidence. "
          "Never invent figures, partners, causes or observed decisions. Distinguish diagnostic treatments from corrections. "
          "Use clear British English, accessible to a non-specialist, with specific and relevant examples. "
          "Model C distinguishes 'Use with caution' from 'Insufficient evidence' for each proposed decision. "
          "Flags are not confirmed errors; sensitivity is not proof of an error or real decision change. "
          "Avoid implying that the World aggregate is a country. Never claim real commercial outcomes were measured.")


def llm_settings():
    with st.expander("AI connection settings", expanded=False):
        st.caption("Optional. The research engine and downloads work without AI. Your API key is not stored in the report.")
        api_key = st.text_input("API key", type="password", value=secret("GEM_KEY") or secret("OPENAI_API_KEY"), help="Use your own Gemini or OpenAI-compatible key.")
        provider = st.selectbox("Provider", ["Gemini (OpenAI-compatible)", "OpenAI-compatible custom"], index=0)
        default_url = "https://generativelanguage.googleapis.com/v1beta/openai" if provider.startswith("Gemini") else "https://api.openai.com/v1"
        base_url = st.text_input("API endpoint", value=default_url)
        model = st.text_input("Model", value=secret("TDL_LLM_MODEL", "gemini-2.5-flash"))
    return api_key, model, base_url


# Visual presentation layer. The research engine below is unchanged.
if "tdl_view" not in st.session_state:
    st.session_state.tdl_view = "Home"

logo_svg = """<svg width="50" height="50" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Trade Decision Lab logo"><path d="M19 7 30 10 35 6 43 13 51 12 56 21 52 30 57 37 48 45 45 55 34 51 26 57 17 49 9 47 12 35 7 28 13 20Z" fill="#e6f5eb" stroke="#08764c" stroke-width="2.5" stroke-linejoin="round"/><path d="M18 39V31h6v8zm10 0V24h6v15zm10 0V19h6v20z" fill="#08764c"/><circle cx="46" cy="45" r="11" fill="#065e46"/><path d="m40 45 4 4 8-9" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>"""
st.markdown("""<style>
.tdl-nav {display:flex;align-items:center;gap:14px;padding:10px 0 20px;border-bottom:1px solid #dce8e6;margin-bottom:18px}
.tdl-brand {font-family:Manrope,sans-serif;font-weight:800;font-size:20px;color:#103c34}
.tdl-subbrand {font-size:11px;color:#5b736e}
.tdl-landing {border-radius:22px;overflow:hidden;background:linear-gradient(90deg,rgba(5,34,34,.96),rgba(5,34,34,.72) 48%,rgba(5,34,34,.12)),url('https://images.unsplash.com/photo-1578575437130-527eed3abbec?auto=format&fit=crop&w=1800&q=85') center/cover;min-height:440px;padding:65px 54px;color:white}
.tdl-landing h1 {color:white;font-size:clamp(38px,5vw,66px);max-width:750px;line-height:1.08}
.tdl-landing p {color:#e6f4f1;max-width:650px;font-size:17px;line-height:1.7}
.tdl-kicker {letter-spacing:.14em;text-transform:uppercase;color:#9cf2b3;font-size:12px;font-weight:800}
.tdl-footer {border-top:1px solid #dce8e6;margin-top:50px;padding:24px 0;color:#56716a;font-size:13px}
</style>""",unsafe_allow_html=True)

left, right = st.columns([5,2],vertical_alignment="center")
with left:
    st.markdown(f'<div class="tdl-nav">{logo_svg}<div><div class="tdl-brand">Trade Decision Lab</div><div class="tdl-subbrand">Data quality · Evidence · Decision fitness</div></div></div>',unsafe_allow_html=True)
with right:
    nav_home, nav_demo = st.columns(2)
    with nav_home:
        if st.button("Home", use_container_width=True, key="tdl_home"):
            st.session_state.tdl_view="Home"
            st.rerun()
    with nav_demo:
        if st.button("Launch demo", type="primary", use_container_width=True, key="tdl_demo"):
            st.session_state.tdl_view="Demo"
            st.rerun()

if st.session_state.tdl_view == "Home":
    st.markdown("""<section class="tdl-landing"><div class="tdl-kicker">University of Ibadan · Group 5 research demonstration</div><h1>Trade data is only as useful as the decisions it can support.</h1><p>Explore how data quality and analytical choices shape what Nigerian import–export statistics can reliably tell us.</p><p>Trade Decision Lab assesses data quality, tests analytical sensitivity and explains fitness for specific decisions.</p></section>""",unsafe_allow_html=True)
    st.write("")
    if st.button("Start the interactive demonstration →",type="primary",use_container_width=True,key="tdl_start"):
        st.session_state.tdl_view="Demo"
        st.rerun()
    st.markdown("### How the lab works")
    a,b,c=st.columns(3)
    with a: st.markdown("**01 · Assess data quality**\n\nScreen completeness, validity, consistency and other data conditions.")
    with b: st.markdown("**02 · Test analytical sensitivity**\n\nSee how selected analytical treatments affect rankings and concentration.")
    with c: st.markdown("**03 · Evaluate decision fitness**\n\nUnderstand which uses warrant caution or lack sufficient evidence.")
    st.markdown("### About the research")
    st.write("**Garbage In, Garbage Out: Examining the Implications of Poor Data Quality for Decision-Making in Nigeria's Import–Export Sector.** This prototype uses UN Comtrade data and does not claim to observe actual organisational decisions.")
    st.markdown('<div class="tdl-footer"><strong>Research by Group 5</strong> · Technical Writing and Presentation · Department of Data and Information Science · University of Ibadan<br>Trade Decision Lab is an academic research demonstration, not an official University of Ibadan service.</div>',unsafe_allow_html=True)
    st.stop()

st.markdown('''<div class="hero"><div class="eyebrow">University research demonstration · Data quality & decision intelligence</div>
<h1>Welcome to Trade Decision Lab.</h1><p>When the data changes, does the decision change? Explore the quality of Nigeria's trade data, see how analytical choices affect the evidence, and understand what the findings can and cannot support.</p>
<span class="pill">01 · Upload data</span><span class="pill">02 · Analyse evidence</span><span class="pill">03 · Explore & download</span></div>''', unsafe_allow_html=True)

if "tdl_run" not in st.session_state:
    st.session_state.tdl_run = None
if "tdl_messages" not in st.session_state:
    st.session_state.tdl_messages = []

st.markdown('<div class="section-caption">Start a new assessment</div>', unsafe_allow_html=True)
st.subheader("Bring your trade data into the lab")
st.write("Upload the three UN Comtrade extracts used in this research. The lab validates their structure and flow, then runs the original Models A, B and C behind the scenes.")

col1, col2, col3 = st.columns(3, gap="medium")
with col1:
    st.markdown('<div class="soft-card"><h3><span class="step">1</span> Commodity imports</h3><p>Commodity-level Nigerian import records. Flow code M.</p></div>', unsafe_allow_html=True)
    imp_file = st.file_uploader("Import dataset", type=["csv", "xlsx"], key="tdl_import", label_visibility="collapsed")
with col2:
    st.markdown('<div class="soft-card"><h3><span class="step">2</span> Commodity exports</h3><p>Commodity-level Nigerian export records. Flow code X.</p></div>', unsafe_allow_html=True)
    exp_file = st.file_uploader("Export dataset", type=["csv", "xlsx"], key="tdl_export", label_visibility="collapsed")
with col3:
    st.markdown('<div class="soft-card"><h3><span class="step">3</span> Total trade</h3><p>Reference extract for reconciliation. Flow M and/or X.</p></div>', unsafe_allow_html=True)
    total_file = st.file_uploader("Total trade dataset", type=["csv", "xlsx"], key="tdl_total", label_visibility="collapsed")

st.caption("Supported formats: CSV or XLSX. Keep commodity codes as text, including leading zeros. Your files are processed in the app session and are not sent to the AI provider. Only selected findings are sent if you enable AI.")
ready = all(f is not None for f in (imp_file, exp_file, total_file))
if st.button("Run trade data assessment", type="primary", disabled=not ready, use_container_width=True):
    st.session_state.tdl_run = None
    st.session_state.tdl_messages = []
    try:
        with st.status("Assessing your trade data…", expanded=True) as status:
            st.write("Checking datasets and trade-flow assignments…")
            frames = {}
            for role, uploaded in [("Imports", imp_file), ("Exports", exp_file), ("Total trade", total_file)]:
                uploaded.seek(0)
                frame = load_file(uploaded, uploaded.name)
                validate_role(frame, role)
                frames[role] = frame
            st.write("Running data quality, sensitivity and fitness-for-use assessments…")
            with tempfile.TemporaryDirectory(prefix="tdl_") as tmp:
                output = Path(tmp) / "results"
                results = run_analysis(frames["Imports"], frames["Exports"], frames["Total trade"], output)
                st.write("Preparing your technical report and evidence workbook…")
                reports = generate_reports(output, llm_brief=None)
                context_text = compact_context(results, frames)
                pdf = Path(reports["pdf"]).read_bytes()
                xlsx = Path(reports["xlsx"]).read_bytes()
                evidence_buffer = io.BytesIO()
                with zipfile.ZipFile(evidence_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                    for path in output.rglob("*"):
                        if path.is_file():
                            archive.write(path, path.relative_to(output))
                st.session_state.tdl_run = {
                    "frames": {name: {"records": len(frame), "columns": len(frame.columns)} for name, frame in frames.items()},
                    "decisions": {name: df.copy() for name, df in results["decisions"].items()},
                    "sensitivity": {name: comp["sensitivity"].copy() for name, comp in results["comparisons"].items()},
                    "context": context_text,
                    "pdf": pdf, "xlsx": xlsx, "zip": evidence_buffer.getvalue(),
                    "fallback": offline_summary(results),
                    "summary": None,
                }
            status.update(label="Assessment complete. Your results are ready.", state="complete", expanded=False)
    except Exception as exc:
        st.error(f"Assessment could not finish: {exc}")
        st.info("Check the three file assignments, the required UN Comtrade columns and the trade-flow codes. No partial results have been published.")

run = st.session_state.tdl_run
if run is not None:
    st.divider()
    st.markdown('<div class="section-caption">Your assessment is ready</div>', unsafe_allow_html=True)
    st.subheader("Explore your results")
    a, b, c, d = st.columns(4)
    a.metric("Import records", f'{run["frames"]["Imports"]["records"]:,}')
    b.metric("Export records", f'{run["frames"]["Exports"]["records"]:,}')
    c.metric("Total-trade records", f'{run["frames"]["Total trade"]["records"]:,}')
    d.metric("Decision assessments", sum(len(df) for df in run["decisions"].values()))
    summary_tab, evidence_tab, download_tab, ask_tab = st.tabs(["✦ Report summary", "◫ Decision evidence", "↓ Download reports", "◌ Ask the lab"])
    with summary_tab:
        st.markdown("### Report summary")
        api_key, model, base_url = llm_settings()
        if api_key and run["summary"] is None:
            if st.button("Generate AI report summary", type="primary"):
                with st.spinner("Writing an accessible summary of the verified findings…"):
                    try:
                        prompt = ("Write 400–550 words with exactly five accessible sections titled 'What we examined', 'What stood out', "
                                  "'What this means for decisions', 'Important limitations', and 'What to do next'. Use up to four grounded examples. "
                                  "Mention specific analytical treatment when describing a changed partner. Highlight the distinction between "
                                  "Use with caution and Insufficient evidence, without overgeneralising. Do not enumerate every finding. "
                                  "End with this exact sentence: 'For the complete findings, explanations and recommended actions, download the full technical PDF report below.'\nEvidence:\n" + run["context"])
                        run["summary"] = chat(api_key, model, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}], base_url)
                    except Exception as exc:
                        st.warning(f"AI summary is temporarily unavailable: {exc}")
        st.markdown("## Report summary")
        st.markdown("#### What the evidence shows")
        st.caption("Charts are calculated from Models B and C, not generated by AI.")

        # Model B: changes across alternative analytical treatments.
        sensitivity_rows = []
        for flow_name, sensitivity in run["sensitivity"].items():
            alternatives = sensitivity.loc[
                sensitivity["treatment"].ne("country_only_baseline")
            ]
            sensitivity_rows.append({
                "Trade flow": f"{flow_name} ({len(alternatives)} comparisons)",
                "Leading partner changed": int(
                    alternatives["top1_changed"].astype(str).str.lower().eq("true").sum()
                ),
                "Top-five membership changed": int(
                    alternatives["top5_membership_changed"].astype(str).str.lower().eq("true").sum()
                ),
            })
        st.markdown("**Changes in trade-partner rankings**")
        sensitivity_chart = pd.DataFrame(sensitivity_rows).set_index("Trade flow")
        st.bar_chart(sensitivity_chart, horizontal=True, stack=False)
        st.caption(
            "Counts refer to alternative-treatment comparisons, not confirmed errors "
            "or independent trade decisions. Some treatments are diagnostic only."
        )

        # Model C: fitness judgements across three decision uses.
        fitness_columns = {
            "Partner prioritisation": "partner_prioritisation_fitness",
            "Market concentration": "concentration_fitness",
            "Unit-value comparison": "unit_value_fitness",
        }
        verdicts = ["Suitable", "Use with caution", "Insufficient evidence"]
        fitness_rows = []
        for decision_use, column in fitness_columns.items():
            row = {"Decision use": decision_use, **{verdict: 0 for verdict in verdicts}}
            for assessments in run["decisions"].values():
                if column in assessments.columns:
                    counts = assessments[column].value_counts()
                    for verdict in verdicts:
                        row[verdict] += int(counts.get(verdict, 0))
            fitness_rows.append(row)
        st.markdown("**Fitness for specific trade decisions**")
        fitness_chart = pd.DataFrame(fitness_rows).set_index("Decision use")
        st.bar_chart(fitness_chart, horizontal=True, stack=True)
        st.caption(
            "Preliminary rule-based assessments across commodity-period scenarios. "
            "Historical and recent H6 scenarios overlap, so counts are not independent observations."
        )

        st.markdown("#### Interpretation")
        st.markdown(run["summary"] or run["fallback"])
        st.markdown("**For complete methods, evidence, explanations and recommended actions, download the full technical PDF report below.**")
        st.info("This is a plain-English interpretation of the research evidence, not a substitute for the technical report. The analysis does not observe actual organisational decisions.")
        st.download_button("Download full technical PDF report", data=run["pdf"], file_name="Trade_Decision_Lab_Report.pdf", mime="application/pdf", key="summary_pdf")
    with evidence_tab:
        flow = st.segmented_control("Trade direction", ["Import", "Export"], default="Import")
        if flow:
            decisions = run["decisions"][flow].copy()
            display_cols = ["scenario", "commodity_code", "commodity_description", "records", "country_partners", "partner_prioritisation_fitness", "concentration_fitness", "unit_value_fitness"]
            st.markdown("**Decision-specific fitness for use**")
            st.dataframe(decisions[[x for x in display_cols if x in decisions]], use_container_width=True, hide_index=True)
            st.caption("These are preliminary screening judgements. 'Insufficient evidence' does not mean the commodity has no trade; it means the supplied records do not adequately support that particular assessment.")
            with st.expander("Explore sensitivity comparisons"):
                sens = run["sensitivity"][flow]
                cols = ["scenario", "commodity_code", "treatment", "baseline_top1", "treatment_top1", "top1_changed", "top5_membership_changed", "cr5_difference_pp"]
                st.dataframe(sens[[x for x in cols if x in sens]], use_container_width=True, hide_index=True)
                st.caption("World-inclusive comparisons are diagnostic. Changes across treatments are not independently verified data corrections.")
    with download_tab:
        st.markdown("### Take the evidence with you")
        st.write("Choose only what you need. The PDF and workbook are deterministic research outputs and do not contain AI-generated text.")
        x, y, z = st.columns(3)
        with x:
            st.markdown("**Technical PDF**")
            st.caption("Methods, fitness verdicts, reasons and recommended actions")
            st.download_button("Download PDF", run["pdf"], "Trade_Decision_Lab_Report.pdf", "application/pdf", key="download_pdf")
        with y:
            st.markdown("**Excel workbook**")
            st.caption("Structured tables for further inspection and presentation")
            st.download_button("Download Excel", run["xlsx"], "Trade_Decision_Lab_Results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel")
        with z:
            st.markdown("**Complete evidence ZIP**")
            st.caption("Detailed CSV evidence, traceability, PDF and Excel")
            st.download_button("Download evidence ZIP", run["zip"], "Trade_Decision_Lab_All_Results.zip", "application/zip", key="download_zip")
    with ask_tab:
        st.markdown("### Ask the lab")
        st.write("Ask questions about the results, data limitations, or what a fitness verdict means. Answers are restricted to this assessment's evidence.")
        if not api_key:
            st.info("To enable interactive questions, enter an API key under **Report summary → AI connection settings**. The reports and decision evidence remain available without it.")
        for message in st.session_state.tdl_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        question = st.chat_input("For example: Can I use the wheat import data to compare suppliers?", disabled=not bool(api_key))
        if question:
            st.session_state.tdl_messages.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Reviewing the evidence…"):
                    try:
                        history = st.session_state.tdl_messages[-8:]
                        answer = chat(api_key, model, [{"role": "system", "content": SYSTEM + " Be concise. Say when the evidence cannot answer the question. Recommend consulting the downloadable report for complete detail."}, {"role": "user", "content": "Research evidence:\n" + run["context"]}, *history], base_url)
                    except Exception as exc:
                        answer = f"The AI response is unavailable: {exc}"
                    st.markdown(answer)
            st.session_state.tdl_messages.append({"role": "assistant", "content": answer})
else:
    st.markdown('<p class="small-note">The assessment runs only after all three datasets have been uploaded. Your results, report downloads and optional AI assistant will appear here when processing is complete.</p>', unsafe_allow_html=True)

st.divider()
st.caption("Trade Decision Lab · Group 5 · Technical Writing and Presentation · Department of Data and Information Science · University of Ibadan · Academic research demonstration.")
