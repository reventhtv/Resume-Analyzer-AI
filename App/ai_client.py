# App/ai_client.py
"""
Robust Gemini AI client for Streamlit Resume Analyzer.

Supports:
- API key auth (AI_API_KEY / GEMINI_API_KEY / GENAI_API_KEY)
- GCP Service Account JSON via Streamlit secrets (GCP_SA_KEY_JSON)
- Multiple google-genai SDK call signatures (prevents breaking changes)
"""

import os
import json
import tempfile
import traceback

# ---------- helpers ----------

def _get_secret(key: str):
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return os.environ.get(key)

API_KEY = (
    _get_secret("AI_API_KEY")
    or _get_secret("GEMINI_API_KEY")
    or _get_secret("GENAI_API_KEY")
)

DEFAULT_MODEL = _get_secret("AI_MODEL") or "gemini-2.5-flash"
API_PROVIDER = (_get_secret("AI_PROVIDER") or "gemini").lower()

# ---------- Service Account handling ----------

def _init_sa_credentials():
    try:
        import streamlit as st
        sa_json = st.secrets.get("GCP_SA_KEY_JSON")
    except Exception:
        sa_json = os.environ.get("GCP_SA_KEY_JSON")

    if not sa_json:
        return None

    try:
        if isinstance(sa_json, dict):
            sa_str = json.dumps(sa_json)
        else:
            sa_str = sa_json

        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write(sa_str)

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        return path
    except Exception:
        return None

_sa_path = _init_sa_credentials()

# ---------- google-genai import ----------

_has_genai = False
_genai_client = None

try:
    from google import genai  # type: ignore
    _has_genai = True
except Exception:
    _has_genai = False

def _init_genai_client():
    global _genai_client
    if not _has_genai:
        return None
    try:
        if API_KEY:
            _genai_client = genai.Client(api_key=API_KEY)
        else:
            _genai_client = genai.Client()
        return _genai_client
    except Exception:
        _genai_client = None
        return None

if _has_genai:
    _init_genai_client()

# ---------- response parsing ----------

def _resp_to_text(resp):
    if hasattr(resp, "text"):
        return resp.text
    if isinstance(resp, dict):
        if "text" in resp:
            return resp["text"]
        if "candidates" in resp and resp["candidates"]:
            cand = resp["candidates"][0]
            if isinstance(cand, dict):
                return cand.get("content") or cand.get("text")
    return str(resp)

# ---------- Gemini call ----------

def call_gemini(prompt: str, model: str = None):
    model = model or DEFAULT_MODEL

    if not _has_genai:
        raise RuntimeError("google-genai SDK not installed")

    if _genai_client is None:
        _init_genai_client()

    if _genai_client is None:
        raise RuntimeError("Gemini client not initialized")

    # Try multiple SDK signatures (SDK versions differ)
    try:
        resp = _genai_client.models.generate_content(
            model=model,
            contents=prompt
        )
        return _resp_to_text(resp)
    except TypeError:
        pass

    try:
        resp = _genai_client.generate_content(prompt)
        return _resp_to_text(resp)
    except Exception:
        pass

    try:
        resp = _genai_client.generate_text(
            model=model,
            prompt=prompt
        )
        return _resp_to_text(resp)
    except Exception as e:
        raise RuntimeError(str(e))

# ---------- Public API ----------

def ask_ai(prompt: str):
    if not prompt:
        return "No resume text provided."

    try:
        if API_PROVIDER == "gemini" and _has_genai:
            out = call_gemini(prompt)
            return out or "No output returned by model."
    except Exception as e:
        return (
            f"AI provider error (Gemini): {e}\n\n"
            f"{traceback.format_exc()}"
        )

    if not API_KEY and not _sa_path:
        return (
            "AI suggestions are not enabled.\n\n"
            "Add either:\n"
            "- AI_API_KEY (Gemini API key), OR\n"
            "- GCP_SA_KEY_JSON (service account JSON)\n"
            "in Streamlit Secrets."
        )

    return "AI provider not available."
