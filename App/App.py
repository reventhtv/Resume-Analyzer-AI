import streamlit as st
import os
import re
import random
import base64
import hashlib
import pdfplumber

from streamlit_tags import st_tags
from Courses import (
    ds_course, web_course, android_course,
    ios_course, uiux_course,
    resume_videos, interview_videos
)

# ---------------- Page Config ----------------
st.set_page_config(
    page_title="CareerScope AI",
    page_icon="🎯",
    layout="wide"
)

# ---------------- AI Client ----------------
try:
    from ai_client import ask_ai
except Exception:
    def ask_ai(prompt):
        return "AI service temporarily unavailable."

# ---------------- Sidebar ----------------
st.sidebar.title("CareerScope AI")
section = st.sidebar.radio(
    "Navigate",
    ["Resume Analysis", "Job Match", "About"]
)

# ---------------- Helpers ----------------
def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def show_pdf(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    st.markdown(
        f"""
        <iframe src="data:application/pdf;base64,{b64}"
        width="100%" height="900"></iframe>
        """,
        unsafe_allow_html=True
    )

def detect_experience(text):
    years = re.findall(r"(\d+)\+?\s+years", text.lower())
    years = max([int(y) for y in years], default=0)

    if years >= 8:
        return "Senior / Lead"
    elif years >= 4:
        return "Mid-level"
    elif years >= 1:
        return "Junior"
    return "Fresher"

def detect_domains(skills):
    domains = []
    s = [x.lower() for x in skills]

    if any(k in s for k in ["python","ml","ai","tensorflow","pytorch"]):
        domains.append("Data Science / AI")
    if any(k in s for k in ["react","django","javascript","node"]):
        domains.append("Web Development")
    if any(k in s for k in ["embedded","rtos","iot","c","c++"]):
        domains.append("Embedded Systems / IoT")
    if any(k in s for k in ["5g","lte","ran","telecom"]):
        domains.append("Telecommunications")
    if any(k in s for k in ["aws","azure","gcp","docker","kubernetes"]):
        domains.append("Cloud / DevOps")
    if any(k in s for k in ["cyber","security","iam","soc"]):
        domains.append("Cybersecurity")
    if any(k in s for k in ["pmp","capm","scrum","agile"]):
        domains.append("Program / Project Management")

    return domains or ["General IT"]

def resume_score(text, skills):
    structure = 0
    expertise = min(len(skills) * 5, 100)

    for sec in ["experience","education","skills","projects","certifications"]:
        if sec in text.lower():
            structure += 20

    return structure, expertise

def make_cache_key(*args):
    joined = "||".join(args)
    return hashlib.sha256(joined.encode()).hexdigest()

# ---------------- UI ----------------
st.title("🎯 CareerScope AI")

# ================= Resume Analysis =================
if section == "Resume Analysis":

    uploaded = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

    if uploaded:
        os.makedirs("uploads", exist_ok=True)
        path = f"uploads/{uploaded.name}"

        with open(path, "wb") as f:
            f.write(uploaded.getbuffer())

        st.subheader("📄 Resume Preview")
        show_pdf(path)

        resume_text = extract_text_from_pdf(path)
        st.session_state["resume_text"] = resume_text

        skills = re.findall(
            r"\b(python|java|c\+\+|c|aws|azure|gcp|docker|kubernetes|iot|rtos|5g|lte|ran|react|django|ml|ai|tensorflow|pytorch|scrum|pmp|capm)\b",
            resume_text.lower()
        )
        skills = sorted(set(skills))

        exp = detect_experience(resume_text)
        domains = detect_domains(skills)
        structure, expertise = resume_score(resume_text, skills)

        st.subheader("📊 Career Insights")

        c1, c2, c3 = st.columns(3)
        c1.metric("Experience Level", exp)
        c2.metric("Structure Score", f"{structure}%")
        c3.metric("Expertise Score", f"{expertise}%")

        st_tags("Best-fit Domains", domains, key="domains")
        st_tags("Detected Skills", skills, key="skills")

        st.video(random.choice(resume_videos))
        st.video(random.choice(interview_videos))

# ================= Job Match =================
elif section == "Job Match":

    if "resume_text" not in st.session_state:
        st.warning("Upload a resume first.")
    else:
        jd = st.text_area("Paste Job Description")

        if st.button("Analyze Job Fit"):
            resume_text = st.session_state["resume_text"]

            missing = [
                k for k in ["cloud","security","agile","leadership"]
                if k not in resume_text.lower()
            ]
            confidence = max(100 - len(missing) * 15, 40)

            st.metric("Confidence Score", f"{confidence}%")
            st.write("Missing Keywords:", ", ".join(missing) or "None 🎉")

            st.session_state["job_fit_done"] = True

        if st.session_state.get("job_fit_done") and st.button("Get AI Suggestions"):

            cache_key = make_cache_key(
                st.session_state["resume_text"],
                jd,
                "job_fit_ai"
            )

            if "ai_cache" not in st.session_state:
                st.session_state["ai_cache"] = {}

            if cache_key in st.session_state["ai_cache"]:
                st.success("Loaded from cache")
                st.write(st.session_state["ai_cache"][cache_key])
            else:
                with st.spinner("Generating AI suggestions…"):
                    prompt = f"""
You are a senior career coach.

Resume:
{st.session_state['resume_text']}

Job Description:
{jd}

Give JD-specific resume improvement suggestions.
"""
                    result = ask_ai(prompt)
                    st.session_state["ai_cache"][cache_key] = result
                    st.write(result)

# ================= About =================
else:
    st.markdown("""
### About CareerScope AI

CareerScope AI helps professionals understand:
- **Where they fit**
- **Why they fit**
- **How to improve**

Features include resume analysis, ATS gap detection,
job matching, and AI-powered improvement suggestions.

Built with ❤️ using Streamlit and Gemini.
""")
