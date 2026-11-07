
from pathlib import Path
import json
import tempfile
import pandas as pd
import streamlit as st
import plotly.express as px

from trade_decision_lab.io import read_trade_file
from trade_decision_lab.contract import suggest_mapping, standardize_frame, REQUIRED, OPTIONAL
from trade_decision_lab.engine import run_model_a, run_model_b, run_model_c
from trade_decision_lab.report import save_run
from trade_decision_lab.loaders import read_comtrade_csv, read_comtrade_excel
from trade_decision_lab.comtrade_engine.pipeline import run_project
from trade_decision_lab.comtrade_engine.schema import validate_comtrade_frame, SchemaError
from trade_decision_lab.llm import chat as llm_chat, test_connection, LLMError
from trade_decision_lab.reporting import generate_reports
from trade_decision_lab.integration import run_analysis

st.set_page_config(page_title="Trade Decision Lab", page_icon="📊", layout="wide")
st.title("Trade Decision Lab")
st.caption("An integrated trade-data quality, analytical sensitivity and decision-implication platform")

with st.sidebar:
    st.header("LLM configuration")
    provider = st.selectbox("API compatibility", ["OpenAI", "OpenAI-compatible endpoint"])
    api_key = st.text_input("API key", type="password", help="Used only for this running session. It is not saved in project files.")
    model = st.text_input("Model", value="gpt-4.1-mini", help="Enter a model available to your API account.")
    base_url = st.text_input("API base URL", value="https://api.openai.com/v1" if provider == "OpenAI" else "https://api.openai.com/v1")
    if st.button("Test LLM connection", use_container_width=True):
        try:
            st.success(test_connection(api_key, model, base_url))
        except Exception as exc:
            st.error(str(exc))
    st.caption("The LLM explains, assists with mapping and interprets results. All data-quality rules and analytical calculations remain deterministic.")

mode = st.radio("Choose analysis workflow", ["UN Comtrade research run", "External trade dataset"], horizontal=True)

def llm_assistant(context):
    st.subheader("LLM research assistant")
    question = st.text_area("Ask about the dataset or results", placeholder="Explain the main data-quality findings and what they mean for interpreting partner rankings.")
    if st.button("Ask the assistant", key="ask_llm"):
        if not api_key:
            st.error("Add your API key in the sidebar first.")
        elif not question.strip():
            st.warning("Enter a question.")
        else:
            prompt = (
                "You are the explanation assistant inside Trade Decision Lab. "
                "Use only the supplied context for claims about this run. Do not invent calculations, "
                "data sources, rule results or causal claims. Distinguish measured findings from interpretation. "
                "State limitations and recommend checking source records where appropriate.\\n\\n"
                f"RUN CONTEXT:\\n{context}\\n\\nUSER QUESTION:\\n{question}"
            )
            try:
                with st.spinner("Consulting the configured LLM..."):
                    answer = llm_chat(api_key, model, [{"role":"user","content":prompt}], base_url)
                st.markdown(answer)
            except Exception as exc:
                st.error(str(exc))

if mode == "UN Comtrade research run":
    st.markdown("Upload the three research inputs. This workflow runs the **original approved empirical engine**, including its 19-rule Model A, original Model B treatments/scenarios, Model C assessment and cross-dataset World reconciliation.")
    c1, c2, c3 = st.columns(3)
    with c1: imports_file = st.file_uploader("Commodity imports CSV/XLSX", type=["csv","xlsx"], key="imp")
    with c2: exports_file = st.file_uploader("Commodity exports CSV/XLSX", type=["csv","xlsx"], key="exp")
    with c3: total_file = st.file_uploader("Total trade reference CSV/XLSX", type=["csv","xlsx"], key="tot")
    commodities_text = st.text_input("Commodity codes (comma-separated; leave blank for research defaults)", value="2710,1001,8703,8517,0303")
    if all([imports_file, exports_file, total_file]):
        if st.button("Run original empirical research engine", type="primary", use_container_width=True):
            try:
                def load(file):
                    return read_comtrade_csv(file) if file.name.lower().endswith(".csv") else read_comtrade_excel(file)
                imp, exp, total = load(imports_file), load(exports_file), load(total_file)
                for label, frame in [("Imports",imp),("Exports",exp),("Total trade",total)]:
                    report = validate_comtrade_frame(frame, strict=False)
                    if not report["valid"]:
                        raise SchemaError(f"{label} input does not meet the Comtrade contract: {report}")
                codes = [x.strip() for x in commodities_text.split(",") if x.strip()]
                defaults = None
                if codes:
                    from trade_decision_lab.comtrade_engine.config import SELECTED_COMMODITIES
                    defaults = {c: SELECTED_COMMODITIES.get(c, f"Commodity {c}") for c in codes}
                out = Path("outputs/comtrade_latest")
                with st.spinner("Running original Models A, B and C for imports and exports..."):
                    result = run_analysis(imp, exp, total, out, commodities=defaults)
                st.session_state["comtrade_out"] = str(out)
                st.session_state["comtrade_meta"] = {
                    "imports": list(imp.shape), "exports": list(exp.shape), "total": list(total.shape),
                    "audits": {k: int(len(v.get("findings", []))) for k,v in result["audits"].items()},
                    "comparisons": {k: int(len(v.get("sensitivity", []))) for k,v in result["comparisons"].items()},
                    "decisions": {k: int(len(v)) for k,v in result["decisions"].items()},
                }
                st.success("Original empirical research pipeline completed.")
                generate_reports(out)
            except Exception as exc:
                st.exception(exc)
    if "comtrade_out" in st.session_state:
        out = Path(st.session_state["comtrade_out"])
        meta = st.session_state["comtrade_meta"]
        st.subheader("Research run summary")
        st.json(meta)
        summary = out / "run_summary.md"
        if summary.exists(): st.markdown(summary.read_text(encoding="utf-8"))
        if st.button("Regenerate Excel and PDF reports"):
            try:
                generate_reports(out, st.session_state.get("comtrade_brief"))
                st.success("Reports regenerated")
            except Exception as exc: st.error(str(exc))
        files = sorted(p for p in out.rglob("*") if p.is_file())
        st.subheader("Research outputs")
        for p in files:
            st.download_button(f"Download {p.relative_to(out)}", p.read_bytes(), file_name=p.name, key=f"dl_{p.as_posix()}")
        context = summary.read_text(encoding="utf-8")[:18000] if summary.exists() else json.dumps(meta)
        if st.button("Generate LLM decision brief"):
            if not api_key: st.warning("Configure the API key first. The deterministic reports remain available.")
            else:
                try:
                    brief = llm_chat(api_key, model, [{"role":"system","content":"Write an evidence-bound decision brief. Do not invent values, rankings or observed real-world decisions. Separate observations, sensitivity and potential implications."},{"role":"user","content":context}],base_url)
                    st.session_state["comtrade_brief"] = brief
                    generate_reports(out, brief)
                except Exception as exc: st.error(str(exc))
        if st.session_state.get("comtrade_brief"): st.markdown(st.session_state["comtrade_brief"])
        llm_assistant(context)

else:
    st.markdown("Upload a compatible trade dataset. The system maps its columns to a documented standard trade-data contract. UN Comtrade-specific rules are not silently applied to unrelated datasets.")
    upload = st.file_uploader("Upload external trade dataset", type=["csv","xlsx"], key="external")
    if upload:
        try:
            raw = read_trade_file(upload)
            st.write(f"{len(raw):,} rows · {len(raw.columns):,} columns")
            st.dataframe(raw.head(10), use_container_width=True)
            suggested = suggest_mapping(raw.columns)
            mapping = {}
            choices = ["— Not mapped —"] + list(raw.columns)
            st.subheader("Confirm column mapping")
            cols = st.columns(2)
            for i, target in enumerate(REQUIRED + OPTIONAL):
                default = next((src for src,dest in suggested.items() if dest == target), "— Not mapped —")
                with cols[i%2]:
                    source = st.selectbox(target.replace("_"," ").title() + (" *" if target in REQUIRED else ""), choices,
                                          index=choices.index(default), key=f"extmap_{target}")
                if source != "— Not mapped —": mapping[source] = target
            if st.button("Validate external dataset", type="primary"):
                standard, validation = standardize_frame(raw, mapping)
                st.session_state["external_standard"] = standard
                st.session_state["external_validation"] = validation
                st.session_state["external_name"] = upload.name
            if "external_standard" in st.session_state:
                standard = st.session_state["external_standard"]
                validation = st.session_state["external_validation"]
                st.subheader("Validation and suitability")
                st.json(validation)
                if validation["valid"] and validation["analysis_capabilities"]["monetary_partner_analysis"]:
                    if st.button("Run external-dataset Models A, B and C", type="primary"):
                        quality, trace = run_model_a(standard)
                        rankings, sensitivity = run_model_b(standard)
                        decisions = run_model_c(quality, sensitivity)
                        st.session_state["external_results"] = (quality, rankings, sensitivity, decisions)
                if "external_results" in st.session_state:
                    quality, rankings, sensitivity, decisions = st.session_state["external_results"]
                    tabs = st.tabs(["Model A", "Model B", "Model C", "Downloads"])
                    with tabs[0]: st.dataframe(quality, use_container_width=True)
                    with tabs[1]:
                        st.dataframe(sensitivity, use_container_width=True)
                        if not rankings.empty:
                            st.dataframe(rankings, use_container_width=True)
                    with tabs[2]: st.dataframe(decisions, use_container_width=True)
                    with tabs[3]:
                        out = Path("outputs/external_latest")
                        save_run(out, st.session_state["external_name"], validation, quality, rankings, sensitivity, decisions)
                        for p in sorted(out.glob("*")):
                            st.download_button(f"Download {p.name}", p.read_bytes(), file_name=p.name, key=f"ext_{p.name}")
                    context = "Validation: " + json.dumps(validation, default=str) + "\\nModel A: " + quality.head(30).to_json(orient="records") + "\\nModel B: " + sensitivity.head(30).to_json(orient="records") + "\\nModel C: " + decisions.head(30).to_json(orient="records")
                    llm_assistant(context[:18000])
        except Exception as exc:
            st.exception(exc)

st.divider()
st.caption("Research integrity: outputs are descriptive and sensitivity-based. Potential decision implications are not proof that an actual organisation changed a decision. LLM explanations do not replace deterministic checks.")
