# App/UploadedResumes/ai_client.py
"""
AI client for Resume Analyzer.
- Uses Google Gen AI Python SDK (Gemini) if available and configured.
- Falls back to a friendly message if SDK or API key is missing.
- Reads secrets from Streamlit secrets (preferred) or environment variables.
"""

import os
import json
import traceback

# Helper to read Streamlit secrets if available (works on Streamlit Cloud)
def _get_secret(key: str):
    try:
        import streamlit as _st
        val = _st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key)

# Prefer specific names but accept either
API_KEY = _get_secret("AI_API_KEY") or _get_secret("GEMINI_API_KEY") or _get_secret("GENAI_API_KEY")
API_PROVIDER = (_get_secret("AI_PROVIDER") or os.environ.get("AI_PROVIDER") or "").lower()
# Optional model name (defaults to a safe Gemini model id if using Gemini)
DEFAULT_MODEL = _get_secret("AI_MODEL") or os.environ.get("AI_MODEL") or "gemini-2.5-flash"

# Try to import Google Gen AI SDK (python package name: google-genai, import path: from google import genai)
_has_genai = False
_genai_client = None
try:
    from google import genai  # type: ignore
    _has_genai = True
except Exception:
    _has_genai = False

def _init_genai_client():
    global _genai_client, _has_genai
    if not _has_genai:
        return None
    try:
        # If API_KEY is provided, pass it; otherwise genai.Client() will try ADC or environment.
        if API_KEY:
            _genai_client = genai.Client(api_key=API_KEY)
        else:
            _genai_client = genai.Client()
        return _genai_client
    except Exception as e:
        # initialization failed
        _genai_client = None
        return None

# initialize if possible
if _has_genai:
    _init_genai_client()

def call_gemini(prompt: str, model: str = None, max_output_tokens: int = 512):
    """
    Call Gemini via google-genai SDK.
    Returns a string (generated text) or raises an exception.
    """
    model = model or DEFAULT_MODEL
    if not _has_genai or _genai_client is None:
        raise RuntimeError("Google Gen AI SDK (google-genai) not available or not initialized.")
    try:
        # The SDK supports a 'models.generate_content' style call as shown in docs
        resp = _genai_client.models.generate_content(model=model, contents=prompt, max_output_tokens=max_output_tokens)
        # The SDK returns an object; many docs show .text or str(resp)
        # Try common properties first:
        text = None
        # resp may be a list-like or object; attempt these safely
        if hasattr(resp, "text"):
            text = resp.text
        elif isinstance(resp, dict):
            # Some SDK versions return dicts
            # try obvious keys
            text = resp.get("text") or resp.get("result") or json.dumps(resp)
        else:
            # fallback to str()
            text = str(resp)
        return text
    except Exception as e:
        # include traceback for debug logging
        raise

def ask_ai(prompt: str, model: str = None, max_output_tokens: int = 512):
    """
    Public helper to get AI output as a string.
    - If Gemini/SDK and API key are available, returns generated text.
    - Otherwise returns a helpful fallback message.
    """
    # Quick sanity for empty prompt
    if not prompt:
        return "No prompt provided."

    # If user explicitly set provider to 'gemini' or provider left blank, try Gemini
    try:
        if API_PROVIDER in ("", "gemini") and _has_genai:
            if _genai_client is None:
                _init_genai_client()
            if _genai_client:
                try:
                    out = call_gemini(prompt, model=model, max_output_tokens=max_output_tokens)
                    return out if out else "No text returned from model."
                except Exception as e:
                    # Return readable error message rather than crash
                    tb = traceback.format_exc()
                    return f"AI provider error (Gemini): {e}\n\nTraceback:\n{tb}"
        # If we get here, no provider configured
        if not API_KEY:
            return (
                "AI suggestions are not enabled. To enable them, add your API key to Streamlit secrets:\n\n"
                "Settings → Secrets → Add KEY: `AI_API_KEY` or `GEMINI_API_KEY` with your API key.\n\n"
                "Also add `google-genai` to requirements.txt (package name `google-genai`)."
            )
        return "AI provider not configured or SDK not installed. Please add the google-genai SDK to requirements.txt."
    except Exception as e:
        tb = traceback.format_exc()
        return f"Unexpected AI client error: {e}\n\n{tb}"
