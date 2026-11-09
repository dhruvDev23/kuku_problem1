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
_STATUS_CALLBACK = None


def set_status_callback(cb):
    global _STATUS_CALLBACK
    _STATUS_CALLBACK = cb


def _notify_status(msg: str):
    if _STATUS_CALLBACK:
        try:
            _STATUS_CALLBACK(msg)
        except Exception:
            pass


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
    provider = cfg.get("provider", "groq")
    provider_cfg = cfg.get(provider, {})
    key = f"{stage}_model"
    if key not in provider_cfg:
        key = "stage1_model"
    if key in provider_cfg:
        return provider_cfg[key]
    if provider == "groq":
        return "llama-3.3-70b-versatile"
    return "gemini-3.8-flash"


# ── Cache ────────────────────────────────────────────────

def _cache_key(prompt: str, model: str, schema: dict | None) -> str:
    blob = json.dumps({"p": prompt, "m": model, "s": schema}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _cache_path(key: str) -> Path:
    cfg = _load_config()
    d = Path(cfg.get("cache_dir", "cache"))
    if not d.is_absolute():
        if _CFG_PATH and "promo-finder-" not in str(_CFG_PATH) and "tmp" not in str(_CFG_PATH):
            base = _CFG_PATH.parent
        else:
            base = Path(__file__).resolve().parent.parent
        d = base / d
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json"


def is_cached(prompt: str, model: str | None = None, schema: dict | None = None, stage: str = "stage1") -> bool:
    if model is None:
        model = get_model_name(stage)
    ckey = _cache_key(prompt, model, schema)
    if _cache_get(ckey) is not None:
        return True
    return _find_cached_fallback(prompt, schema, model) is not None


_KNOWN_MODELS = (
    "qwen/qwen3.8-27b",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "meta-llama/llama-3.3-70b-instruct:free",
    "llama3.2",
    "gpt-4o-mini",
)


def _find_cached_fallback(prompt: str, schema: dict | None, current_model: str) -> tuple[str, dict | list] | None:
    for alt_model in _KNOWN_MODELS:
        if alt_model != current_model:
            alt_key = _cache_key(prompt, alt_model, schema)
            val = _cache_get(alt_key)
            if val is not None:
                return alt_key, val
    return None


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
        if schema.get("type") in {"object", "array"} and (
            schema.get("properties") or schema.get("items")
        ):
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
    provider = cfg.get("provider", "openai_compatible")
    oc = cfg.get(provider, cfg.get("openai_compatible", {}))
    api_key_env = oc.get("api_key_env", "OPENAI_API_KEY")
    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        if provider == "ollama":
            api_key = "ollama"
        else:
            raise RuntimeError(f"Set {api_key_env} environment variable")
    base_url = oc.get("base_url", "https://api.openai.com/v1").rstrip("/")

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
    if resp.is_error:
        err_msg = resp.text
        try:
            err_json = resp.json()
            if "error" in err_json:
                e = err_json["error"]
                err_msg = e.get("message", resp.text) if isinstance(e, dict) else str(e)
        except Exception:
            pass
        raise RuntimeError(f"API Error ({resp.status_code}): {err_msg}")
    data = resp.json()

    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)


_PROVIDERS = {
    "gemini": _call_gemini,
    "openai_compatible": _call_openai_compatible,
    "groq": _call_openai_compatible,
    "openrouter": _call_openai_compatible,
    "ollama": _call_openai_compatible,
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
    if cached is None:
        fallback = _find_cached_fallback(prompt, schema, model)
        if fallback is not None:
            _, cached = fallback
            _cache_put(ckey, cached)
    if cached is not None:
        return cached

    call_fn = _PROVIDERS[provider]
    max_retries = max(5, int(cfg.get("max_retries", 5)))
    rate_limit_retries = 0
    max_rate_limit_retries = 0 if stage == "rerank" else 8
    last_error = None
    repair_prompt_used = False

    while True:
        try:
            _rate_limit()
            _notify_status(f"[LLM] Calling {provider.capitalize()} AI ({model}) for {stage}...")
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
            if isinstance(e, UnicodeError):
                raise
            last_error = e
            if not repair_prompt_used:
                repair_prompt_used = True
                prompt = (
                    prompt
                    + f"\n\n[SYSTEM: Your previous response was not valid JSON. "
                    f"Error: {e}. Please output ONLY valid JSON.]"
                )
                time.sleep(1.0)
                continue
            raise RuntimeError(f"JSON validation failed: {last_error}") from e

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # Daily quota limits (e.g. 200k TPD, 20 requests/day) take hours to reset — do NOT retry in a 30s loop!
            is_daily = any(kw in err_str for kw in ("per day", "daily", "tokens per day", "tpd", "resource_exhausted", "quota exceeded"))
            if is_daily or stage == "rerank":
                raise RuntimeError(f"API Quota Exhausted: {last_error}") from e

            if any(code in err_str for code in ("429", "500", "502", "503", "504")):
                rate_limit_retries += 1
                if rate_limit_retries > max_rate_limit_retries:
                    raise RuntimeError(
                        f"Failed after {max_rate_limit_retries} rate-limit retries. Last error: {last_error}"
                    ) from e
                wait = (2 ** min(rate_limit_retries, 5)) + random.uniform(0, 1)
                resp = getattr(e, "response", None)
                if resp is not None and hasattr(resp, "headers"):
                    retry_after = resp.headers.get("retry-after")
                    reset_tokens = resp.headers.get("x-ratelimit-reset-tokens")
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after) + 2.0)
                        except ValueError:
                            pass
                    elif reset_tokens:
                        try:
                            clean_val = reset_tokens.strip().rstrip("s")
                            wait = max(wait, float(clean_val) + 2.0)
                        except ValueError:
                            pass
                status_msg = f"[Rate limit] {provider.capitalize()} cooling down {wait:.1f}s before retry attempt {rate_limit_retries} of {max_rate_limit_retries}..."
                _notify_status(status_msg)
                try:
                    print(f"  {status_msg}")
                except Exception:
                    pass
                wait_int = int(wait)
                for _ in range(wait_int):
                    time.sleep(1.0)
                    _notify_status("cooling down")
                remainder = wait - wait_int
                if remainder > 0:
                    time.sleep(remainder)
                continue
            else:
                raise

