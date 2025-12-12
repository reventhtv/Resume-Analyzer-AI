# App/UploadedResumes/ai_client.py
import os
import json
import tempfile
import traceback

def _get_secret(key: str):
    """Try to read from Streamlit secrets (if available), else env var."""
    try:
        import streamlit as _st
        val = _st.secrets.get(key)
        if val:
            return val
    except Exception:
        pass
    return os.environ.get(key)

# Read keys (accept multiple names)
API_KEY = _get_secret("AI_API_KEY") or _get_secret("GEMINI_API_KEY") or _get_secret("GENAI_API_KEY")
API_PROVIDER = (_get_secret("AI_PROVIDER") or os.environ.get("AI_PROVIDER") or "").lower()
DEFAULT_MODEL = _get_secret("AI_MODEL") or os.environ.get("AI_MODEL") or "gemini-2.5-flash"

# If a GCP service account JSON was stored in secrets as GCP_SA_KEY_JSON (triple-quoted string),
# write it to a temp file and set GOOGLE_APPLICATION_CREDENTIALS for google-genai to pick up.
def _init_gcp_sa_from_secrets():
    try:
        import streamlit as _st
        sa_json = _st.secrets.get("GCP_SA_KEY_JSON")
    except Exception:
        sa_json = os.environ.get("GCP_SA_KEY_JSON")
    if not sa_json:
        return None
    try:
        # if value looks like a JSON string, keep as-is
        if isinstance(sa_json, dict):
            sa_str = json.dumps(sa_json)
        else:
            sa_str = sa_json
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write(sa_str)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        return path
    except Exception as e:
        print("Failed to write GCP SA JSON to temp file:", e)
        return None

# Initialize SA JSON if present
_sa_path = _init_gcp_sa_from_secrets()

# Try to import google-genai safely
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
        if API_KEY:
            _genai_client = genai.Client(api_key=API_KEY)
        else:
            # rely on application default credentials (service account JSON path)
            _genai_client = genai.Client()
        return _genai_client
    except Exception as e:
        _genai_client = None
        print("Failed to initialize genai client:", e)
        return None

if _has_genai:
    _init_genai_client()

def call_gemini(prompt: str, model: str = None, max_output_tokens: int = 512):
    model = model or DEFAULT_MODEL
    if not _has_genai or _genai_client is None:
        raise RuntimeError("Google Gen AI SDK not available or not initialized.")
    try:
        resp = _genai_client.models.generate_content(model=model, contents=prompt, max_output_tokens=max_output_tokens)
        # try common attributes
        if hasattr(resp, "text"):
            return resp.text
        if isinstance(resp, dict):
            return resp.get("text") or resp.get("result") or json.dumps(resp)
        return str(resp)
    except Exception:
        raise

def ask_ai(prompt: str, model: str = None, max_output_tokens: int = 512):
    if not prompt:
        return "No prompt provided."
    try:
        # prefer explicit provider empty or gemini
        if API_PROVIDER in ("", "gemini") and _has_genai:
            if _genai_client is None:
                _init_genai_client()
            if _genai_client:
                try:
                    out = call_gemini(prompt, model=model, max_output_tokens=max_output_tokens)
                    return out or "No text returned from model."
                except Exception as e:
                    tb = traceback.format_exc()
                    return f"AI provider error (Gemini): {e}\n\nTraceback:\n{tb}"
        # If no SDK or no API key present, give instructions
        if not API_KEY and not _sa_path:
            return (
                "AI suggestions are not enabled. To enable them add your API key or service account:\n\n"
                "1) For API key: Settings → Secrets → Add KEY: AI_API_KEY (or GEMINI_API_KEY / GENAI_API_KEY).\n"
                "2) For Service Account: Add GCP_SA_KEY_JSON as a triple-quoted JSON string (see docs).\n\n"
                "Also ensure package `google-genai` is in requirements.txt (package name: google-genai).\n"
            )
        return "AI provider not configured or SDK not installed. Please add google-genai to requirements.txt."
    except Exception as e:
        tb = traceback.format_exc()
        return f"Unexpected AI client error: {e}\n\n{tb}"
