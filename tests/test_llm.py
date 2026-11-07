from trade_decision_lab.llm import chat, LLMError

def test_requires_api_key():
    try:
        chat("", "some-model", [])
    except LLMError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Missing API key should be rejected")
