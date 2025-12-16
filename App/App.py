import streamlit as st
import os
import io
import re
import random
import base64
import pdfplumber
from PIL import Image

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
st.sidebar.caption("AI-powered career clarity")

section = st.sidebar.radio(
    "Navigate",
    ["Resume Analysis", "Job Match", "About"]
)

# ---- Buy Me a Coffee (SAFE + ALWAYS VISIBLE) ----
st.sidebar.markdown("---")
st.sidebar.subheader("☕ Support the project")

if st.sidebar.button("Buy me a coffee"):
    st.sidebar.markdown(
        "[Click here to support ❤️](https://www.buymeacoffee.com/revanththiruvallur)",
        unsafe_allow_html=True
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
        width="100%" height="900" type="application/pdf"></iframe>
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

    skillset = [s.lower() for s in skills]

    if any(k in skillset for k in ["python","ml","ai","tensorflow","pytorch"]):
        domains.append("Data Science / AI")
    if any(k in skillset for k in ["react","django","javascript","node"]):
        domains.append("Web Development")
    if any(k in skillset for k in ["embedded","rtos","c","c++","iot"]):
        domains.append("Embedded Systems / IoT")
    if any(k in skillset for k in ["5g","lte","ran","telecom"]):
        domains.append("Telecommunications")
    if any(k in skillset for k in ["aws","azure","gcp","docker","kubernetes"]):
        domains.append("Cloud / DevOps")
    if any(k in skillset for k in ["security","cyber","iam","soc"]):
        domains.append("Cybersecurity")
    if any(k in skillset for k in ["pmp","capm","scrum","agile"]):
        domains.append("Program / Project Management")

    return domains or ["General IT"]

def resume_score(text, skills):
    structure = 0
    expertise = 0

    sections = ["experience","education","skills","projects","certifications"]
    for sec in sections:
        if sec in text.lower():
            structure += 20

    expertise = min(len(skills) * 5, 100)
    return structure, expertise

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

        try:
            resume_text = extract_text_from_pdf(path)
        except Exception:
            resume_text = ""

        st.session_state["resume_text"] = resume_text

        # ---- Skill Extraction (safe fallback) ----
        skills = re.findall(
            r"\b(python|java|c\+\+|c|aws|azure|gcp|docker|kubernetes|iot|rtos|5g|lte|ran|react|django|ml|ai|tensorflow|pytorch|scrum|pmp|capm)\b",
            resume_text.lower()
        )
        skills = sorted(set(skills))

        # ---- Analysis ----
        exp_level = detect_experience(resume_text)
        domains = detect_domains(skills)
        structure_score, expertise_score = resume_score(resume_text, skills)

        st.subheader("📊 Career Insights")

        col1, col2, col3 = st.columns(3)
        col1.metric("Experience Level", exp_level)
        col2.metric("Structure Score", f"{structure_score}%")
        col3.metric("Expertise Score", f"{expertise_score}%")

        st.markdown("**Best-fit Domains:**")
        st_tags(label="Domains", value=domains, key="domains")

        st.markdown("**Detected Skills:**")
        st_tags(label="Skills", value=skills, key="skills")

        st.subheader("🎥 Learning Resources")
        st.video(random.choice(resume_videos))
        st.video(random.choice(interview_videos))

# ================= Job Match =================
elif section == "Job Match":

    if "resume_text" not in st.session_state:
        st.warning("Please upload a resume first.")
    else:
        jd = st.text_area("Paste Job Description")

        if st.button("Analyze Job Fit"):
            resume_text = st.session_state["resume_text"]

            missing = [
                w for w in ["cloud","security","agile","leadership"]
                if w not in resume_text.lower()
            ]

            confidence = max(100 - len(missing) * 15, 40)

            st.subheader("🎯 Job Fit Summary")
            st.metric("Confidence Score", f"{confidence}%")

            st.markdown("**Missing / Weak Keywords:**")
            st.write(", ".join(missing) if missing else "None 🎉")

            st.session_state["job_fit_done"] = True

        if st.session_state.get("job_fit_done"):
            st.subheader("🤖 AI Improvement Suggestions")

            if st.button("Get AI Suggestions"):
                with st.spinner("Analyzing with AI…"):
                    prompt = f"""
You are a senior career coach.

Resume:
{st.session_state['resume_text']}

Job Description:
{jd}

Suggest improvements to maximize role fit.
"""
                    st.write(ask_ai(prompt))

# ================= About =================
else:
    st.markdown("""
### About CareerScope AI

CareerScope AI helps professionals understand **where they fit**,  
**why they fit**, and **how to improve** for their next role.

**What it does:**
- Resume analysis
- Domain detection
- ATS gap identification
- Job description matching
- AI-powered improvement suggestions

Built with ❤️ using Streamlit & Gemini.
""")
