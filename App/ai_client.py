# App/UploadedResumes/ai_client.py
"""
Safe AI client skeleton.
- Uses Streamlit secrets (st.secrets) when available.
- Uses environment variables as fallback.
- Returns friendly messages when not configured.
- Replace the `call_provider` implementation with your provider-specific code (Gemini / Z.ai) later.
"""

import os
import json
import requests

def _get_secret(key: str):
    # Try Streamlit secrets first (safe when running on Streamlit Cloud)
    try:
        import streamlit as _st
        val = _st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    # Fallback to environment variable
    return os.environ.get(key)

AI_API_KEY = _get_secret("AI_API_KEY")
AI_API_URL = _get_secret("AI_API_URL")  # optional provider URL
AI_PROVIDER = (_get_secret("AI_PROVIDER") or "").lower()  # optional: "gemini" / "zai" / ""

def call_provider(prompt: str, max_tokens: int = 512):
    """
    Generic provider caller stub.
    Replace this with the exact provider call for Gemini or Z.ai when you're ready.
    For now, it returns a simple JSON-like object explaining that the provider isn't configured.
    """
    if not AI_API_KEY:
        return {
            "ok": False,
            "message": "AI API key not configured. Add AI_API_KEY to Streamlit secrets or environment to enable AI suggestions."
        }

    # Example: If you later set AI_PROVIDER to "gemini", you can branch here and craft the provider-specific request.
    # This block demonstrates structure; you must replace endpoint/payload per provider docs.
    if AI_PROVIDER == "gemini" and AI_API_URL:
        # >>> Replace with real Gemini request shape when you have the docs/key <<<
        try:
            headers = {"Authorization": f"Bearer {AI_API_KEY}", "Content-Type": "application/json"}
            payload = {"prompt": prompt, "max_tokens": max_tokens}
            resp = requests.post(AI_API_URL, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            return {"ok": True, "result": resp.json()}
        except Exception as e:
            return {"ok": False, "message": f"Provider request failed: {e}"}
    else:
        # Default: no provider configured yet
        return {
            "ok": False,
            "message": (
                "AI provider not configured. Set AI_API_KEY and optionally AI_PROVIDER/AI_API_URL in Streamlit secrets.\n"
                "If you want, I can give you the exact code to call Google Gemini or Z.ai — tell me which provider and I will paste it."
            )
        }

def ask_ai(prompt: str, max_tokens: int = 512):
    """
    Public helper. Returns a string for display.
    """
    resp = call_provider(prompt, max_tokens=max_tokens)
    if isinstance(resp, dict):
        if resp.get("ok"):
            # try to convert common structures into a string
            result = resp.get("result")
            if isinstance(result, (dict, list)):
                try:
                    return json.dumps(result, indent=2)
                except Exception:
                    return str(result)
            return str(result)
        else:
            return resp.get("message", str(resp))
    return str(resp)
