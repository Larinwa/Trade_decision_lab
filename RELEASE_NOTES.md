# Release notes — integrated release candidate

This release consolidates the two previously separate codebases:
- Original research modules preserved under `trade_decision_lab/comtrade_engine/`.
- General upload/mapping and generic analytical modules retained under `trade_decision_lab/`.
- Streamlit interface now exposes separate Comtrade research and external dataset workflows.
- LLM API configuration and assistant added using an OpenAI-compatible Chat Completions endpoint.
- No raw UN Comtrade data were present in the build workspace; empirical acceptance testing on those files remains outstanding.
