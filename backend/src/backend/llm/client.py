"""Thin OpenAI-compatible chat client (Section 8: "used here purely for inference,
with no fine-tuning step"). Both Ollama (dev) and vLLM (prod) speak this protocol
natively, so switching between them is a config change (LLM_BASE_URL/LLM_MODEL in
.env), never a code change.
"""

from functools import lru_cache

from openai import OpenAI

from backend.config import get_settings


@lru_cache
def _get_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)


def chat_completion(messages: list[dict[str, str]], temperature: float = 0.2) -> str:
    """One-shot chat completion. Returns the assistant's text content (empty string
    if the model returned none)."""
    client = _get_client()
    response = client.chat.completions.create(
        model=get_settings().llm_model,
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""
