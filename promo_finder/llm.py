# ──────────────────────────────────────────────────────────
# promo_finder/llm.py – Swappable LLM interface
# ──────────────────────────────────────────────────────────
"""
Single entry point:  generate_json(prompt, schema, ...)

Supports:
  - gemini        (google-genai SDK)
  - openai_compatible  (any OpenAI-compatible endpoint)

Features: disk cache, exponential backoff, token/cost logging,
          JSON repair retry.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import random
from pathlib import Path
from typing import Any

import yaml

from .cost import log_call

# ── Config ───────────────────────────────────────────────

_CFG: dict | None = None
_CFG_PATH: Path | None = None


def configure(config: dict | None = None, config_path: str | Path | None = None):
    """Configure the LLM layer for a CLI run or an embedding application."""
    global _CFG, _CFG_PATH
    _CFG = config
    _CFG_PATH = Path(config_path).resolve() if config_path else None


def _load_config() -> dict:
    global _CFG
    if _CFG is None:
        cfg_path = _CFG_PATH or Path(__file__).parent.parent / "config.yaml"
        _CFG = yaml.safe_load(cfg_path.read_text())
    return _CFG or {}


def reset_runtime_state():
    """Reset module state between independent runs and tests."""
    global _last_call_time
    _last_call_time = 0.0


def get_model_name(stage: str) -> str:
    """Return the configured model name for a pipeline stage."""
    cfg = _load_config()
    provider = cfg["provider"]
    provider_cfg = cfg[provider]
    key = f"{stage}_model"
    if key not in provider_cfg:
        key = "stage1_model"
    return provider_cfg[key]


# ── Cache ────────────────────────────────────────────────

def _cache_key(prompt: str, model: str, schema: dict | None) -> str:
    blob = json.dumps({"p": prompt, "m": model, "s": schema}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    cfg = _load_config()
    d = Path(cfg.get("cache_dir", "cache"))
    if not d.is_absolute():
        base = _CFG_PATH.parent if _CFG_PATH else Path(__file__).parent.parent
        d = base / d
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def _cache_get(key: str) -> dict | list | None:
    p = _cache_path(key)
    if p.exists():
        try:
            value = json.loads(p.read_text())
            return value if isinstance(value, (dict, list)) else None
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _cache_put(key: str, data: dict | list):
    _cache_path(key).write_text(json.dumps(data, indent=2))


def _validate_schema(value: Any, schema: dict | None):
    if not schema:
        return
    try:
        from jsonschema import ValidationError, validate
    except ImportError:
        return
    try:
        validate(value, schema)
    except ValidationError as exc:
        raise ValueError(f"JSON schema validation failed: {exc.message}") from exc


# ── JSON extraction ─────────────────────────────────────

def _extract_json(text: str) -> dict | list:
    """Extract JSON from a text response that may have markdown fences."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try stripping markdown code fences
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try finding first { or [
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        idx = text.find(start_char)
        if idx >= 0:
            ridx = text.rfind(end_char)
            if ridx > idx:
                try:
                    return json.loads(text[idx:ridx + 1])
                except json.JSONDecodeError:
                    pass
    raise ValueError(f"Could not extract JSON from response: {text[:200]}")


# ── Providers ────────────────────────────────────────────

def _call_gemini(prompt: str, model: str, temperature: float,
                 schema: dict | None) -> tuple[str, int, int]:
    """Call Gemini via google-genai SDK. Returns (text, prompt_tokens, completion_tokens)."""
    from google import genai

    cfg = _load_config()
    api_key = os.environ.get(cfg["gemini"]["api_key_env"], "")
    if not api_key:
        raise RuntimeError(
            f"Set {cfg['gemini']['api_key_env']} environment variable"
        )

    client = genai.Client(api_key=api_key)

    # Build generation config
    gen_config: dict[str, Any] = {"temperature": temperature}
    if schema:
        gen_config["response_mime_type"] = "application/json"
        if schema.get("type") in {"object", "array"}:
            gen_config["response_schema"] = schema

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=gen_config,
    )

    text = response.text or ""
    # Extract token counts from usage metadata
    usage = getattr(response, "usage_metadata", None)
    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) or 0

    return text, prompt_tokens, completion_tokens


def _call_openai_compatible(prompt: str, model: str, temperature: float,
                            schema: dict | None) -> tuple[str, int, int]:
    """Call any OpenAI-compatible API. Returns (text, prompt_tokens, completion_tokens)."""
    import httpx

    cfg = _load_config()
    oc = cfg["openai_compatible"]
    api_key = os.environ.get(oc["api_key_env"], "")
    if not api_key:
        raise RuntimeError(f"Set {oc['api_key_env']} environment variable")
    base_url = oc["base_url"].rstrip("/")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }
    if schema:
        body["response_format"] = {"type": "json_object"}

    resp = httpx.post(
        f"{base_url}/chat/completions",
        json=body,
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


_PROVIDERS = {
    "gemini": _call_gemini,
    "openai_compatible": _call_openai_compatible,
}


# ── Rate limiter ─────────────────────────────────────────

_last_call_time = 0.0


def _rate_limit():
    global _last_call_time
    cfg = _load_config()
    rpm = float(cfg.get("requests_per_minute", 15) or 0)
    if rpm <= 0:
        return
    min_interval = 60.0 / rpm
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_call_time = time.time()


# ── Main entry point ─────────────────────────────────────

def generate_json(
    prompt: str,
    schema: dict | None = None,
    *,
    model: str | None = None,
    stage: str = "stage1",
    temperature: float = 0.2,
) -> dict | list:
    """
    Send a prompt to the configured LLM and return parsed JSON.

    Args:
        prompt: The full prompt text.
        schema: JSON schema hint (used for response_format where supported).
        model: Override the model name. If None, uses config for the given stage.
        stage: Pipeline stage name (stage1, stage2, rerank) — used for model lookup and cost.
        temperature: Override temperature. If None, uses config default.

    Returns:
        Parsed JSON dict/list from the LLM response.
    """
    cfg = _load_config()
    provider = cfg["provider"]
    if provider not in _PROVIDERS:
        raise ValueError(f"Unsupported LLM provider: {provider}")
    if model is None:
        model = get_model_name(stage)
    if temperature == 0.2:
        temperature = float(cfg.get("temperature", 0.2))

    # Check cache
    ckey = _cache_key(prompt, model, schema)
    cached = _cache_get(ckey)
    if cached is not None:
        return cached

    call_fn = _PROVIDERS[provider]
    max_retries = max(1, int(cfg.get("max_retries", 3)))
    last_error = None
    repair_prompt_used = False

    for attempt in range(max_retries):
        try:
            _rate_limit()
            text, p_tokens, c_tokens = call_fn(prompt, model, temperature, schema)
            result = _extract_json(text)
            _validate_schema(result, schema)

            # Log cost
            log_call(
                stage=stage,
                model=model,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
            )

            # Cache and return
            _cache_put(ckey, result)
            return result

        except (ValueError, json.JSONDecodeError) as e:
            last_error = e
            if attempt < max_retries - 1 and not repair_prompt_used:
                repair_prompt_used = True
                prompt = (
                    prompt
                    + f"\n\n[SYSTEM: Your previous response was not valid JSON. "
                    f"Error: {e}. Please output ONLY valid JSON.]"
                )
                time.sleep(min(1.0, 0.25 * (attempt + 1)))
            continue

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            if any(code in err_str for code in ("429", "500", "502", "503", "504")):
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"  ⏳ Rate limited / server error, retry in {wait:.1f}s...")
                time.sleep(wait)
            else:
                raise

    raise RuntimeError(
        f"Failed after {max_retries} retries. Last error: {last_error}"
    )

