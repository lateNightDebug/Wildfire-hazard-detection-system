"""LM Studio client (Layer 2): health check + wildfire analysis text generation.

LM Studio exposes an OpenAI-compatible REST API at http://localhost:1234/v1.
This module is fully offline-tolerant: every call returns a value instead of
raising, so the report pipeline degrades cleanly when LM Studio is not running.

Qwen3.5-9B is a reasoning model: it may emit <think>...</think> and can leave
`content` empty while reasoning fills `reasoning_content` (known LM Studio bug).
We set a generous max_tokens, strip <think> tags, and fall back to
`reasoning_content` so the PDF never gets empty or chain-of-thought text.
"""

from __future__ import annotations

import re
from typing import Optional

import requests

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

SYSTEM_PROMPT = (
    "You are a wildfire risk analyst. Given a detection summary, write a concise, "
    "factual technical report with three sections: 1) Situation overview, 2) Risk "
    "assessment by level, 3) Recommended actions for field teams. Use plain prose and "
    "short bullet points. Do not invent data beyond what is provided."
)


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks, including a dangling/truncated opening tag."""
    if not text:
        return ""
    cleaned = _THINK_RE.sub("", text)
    if "<think>" in cleaned.lower():
        parts = re.split(r"</think>", cleaned, flags=re.IGNORECASE)
        cleaned = parts[-1] if len(parts) > 1 else re.sub(
            r"<think>.*", "", cleaned, flags=re.DOTALL | re.IGNORECASE
        )
    return cleaned.strip()


def health_check(base_url: str, timeout: float = 3.0) -> tuple[bool, list[str], Optional[str]]:
    """Return (is_up, model_ids, error_msg). Never raises.

    is_up=True with a non-empty model_ids means the server is running with at
    least one model loaded.
    """
    url = base_url.rstrip("/") + "/v1/models"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        ids = [m.get("id") for m in data if m.get("id")]
        if not ids:
            return False, [], "LM Studio is running but no model is loaded."
        return True, ids, None
    except requests.exceptions.ConnectionError:
        return False, [], f"Cannot reach LM Studio at {base_url} (is the local server started?)."
    except requests.exceptions.Timeout:
        return False, [], f"LM Studio did not respond within {timeout:.1f}s."
    except requests.exceptions.RequestException as e:
        return False, [], f"LM Studio request failed: {e}"


def resolve_model_id(base_url: str, preferred: str) -> tuple[Optional[str], Optional[str]]:
    """Pick the configured model if loaded, else the first loaded model."""
    up, ids, err = health_check(base_url)
    if not up:
        return None, err
    for mid in ids:
        if preferred.lower() in str(mid).lower():
            return mid, None
    return ids[0], None


def generate_analysis(
    summary_text: str,
    base_url: str,
    model_id: str,
    timeout: tuple[float, float] = (3.05, 120.0),
) -> tuple[Optional[str], Optional[str]]:
    """Call LM Studio for report prose. Returns (text, error).

    On any failure returns (None, error) so the caller can fall back gracefully.
    """
    body = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": summary_text},
        ],
        "temperature": 0.3,
        "max_tokens": 2048,
        "stream": False,
        # Best-effort thinking-off (often ignored by Qwen3.5-9B GGUF -> we also strip).
        "chat_template_kwargs": {"enable_thinking": False},
    }
    url = base_url.rstrip("/") + "/v1/chat/completions"
    try:
        resp = requests.post(url, json=body, timeout=timeout)
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        content = _strip_thinking(msg.get("content") or "")
        if not content:
            content = _strip_thinking(msg.get("reasoning_content") or "")
        if not content:
            return None, "LLM returned empty content (reasoning consumed the token budget)."
        return content, None
    except requests.exceptions.ConnectionError:
        return None, "LM Studio not reachable — report will omit AI analysis."
    except requests.exceptions.Timeout:
        return None, "LM Studio timed out — report will omit AI analysis."
    except (KeyError, ValueError, requests.exceptions.RequestException) as e:
        return None, f"LLM call failed: {e}"
