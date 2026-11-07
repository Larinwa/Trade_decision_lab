
"""OpenAI-compatible LLM assistance. API keys are supplied at runtime and never written to disk."""
import requests

DEFAULT_BASE_URL = "https://api.openai.com/v1"

class LLMError(RuntimeError):
    pass

def chat(api_key, model, messages, base_url=DEFAULT_BASE_URL, timeout=60):
    if not api_key or not api_key.strip():
        raise LLMError("Enter your API key in the LLM settings.")
    if not model or not model.strip():
        raise LLMError("Select an LLM model.")
    url = base_url.rstrip("/") + "/chat/completions"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {api_key.strip()}", "Content-Type": "application/json"},
        json={"model": model.strip(), "messages": messages, "temperature": 0.2},
        timeout=timeout,
    )
    if response.status_code >= 400:
        try:
            detail = response.json().get("error", {}).get("message", response.text)
        except Exception:
            detail = response.text
        raise LLMError(f"LLM request failed ({response.status_code}): {detail}")
    payload = response.json()
    try:
        return payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("The LLM provider returned an unexpected response.") from exc

def test_connection(api_key, model, base_url=DEFAULT_BASE_URL):
    return chat(api_key, model, [{"role":"user","content":"Reply with exactly: Trade Decision Lab connection successful."}], base_url)
