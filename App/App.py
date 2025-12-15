import streamlit as st
import os
import io
import re
import random
import base64
from PIL import Image
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
    page_icon="🚀",
    layout="wide"
)

# ---------------- AI Client ----------------
try:
    from ai_client import ask_ai
except Exception:
    def ask_ai(prompt):
        return "AI client not configured."

# ---------------- Helpers ----------------
def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def show_pdf_all_pages(path):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <iframe src="data:application/pdf;base64,{b64}"
                width="100%" height="900"
                style="border: none;"></iframe>
        """,
        unsafe_allow_html=True
    )

def course_recommender(course_list):
    st.subheader("📚 Recommended Courses")
    k = st.slider("Number of recommendations", 1, 10, 5)
    random.shuffle(course_list)
    for i, (name, link) in enumerate(course_list[:k], 1):
        st.markdown(f"{i}. [{name}]({link})")

# ---------------- Domain Detection ----------------
def detect_domain(skills, text):
    text = text.lower()
    skills = [s.lower() for s in skills]

    if any(k in text for k in ["lte", "5g", "ran", "rf", "telecom", "wireless"]):
        return "Telecommunications"
    if any(k in text for k in ["embedded", "firmware", "microcontroller", "rtos"]):
        return "Embedded Systems"
    if any(k in skills for k in ["aws", "docker", "kubernetes", "ci/cd"]):
        return "Cloud / DevOps"
    if any(k in text for k in ["payments", "fintech", "banking", "lending"]):
        return "FinTech"
    if any(k in skills for k in ["python", "ml", "ai", "tensorflow"]):
        return "Data Science"
    return "General Software / Technology"

# ---------------- Experience Level ----------------
def detect_experience(text):
    text = text.lower()
    if "intern" in text:
        return "Early Career / Intern"
    if any(k in text for k in ["senior", "lead", "manager", "principal"]):
        return "Senior / Lead"
    return "Mid-level Professional"

# ---------------- Resume Score ----------------
def resume_score(text):
    score = 0
    sections = [
        "summary", "experience", "education",
        "skills", "projects", "certification"
    ]
    for s in sections:
        if s in text.lower():
            score += 10
    return min(score, 100)

# ================= UI =================
st.title("🚀 CareerScope AI")

section = st.sidebar.selectbox(
    "Navigate",
    ["Resume Analyzer", "Job Match", "About"]
)

# ================= Resume Analyzer =================
if section == "Resume Analyzer":

    st.subheader("Upload your resume (PDF)")
    pdf_file = st.file_uploader("Upload PDF", type=["pdf"])

    if pdf_file:
        os.makedirs("Uploaded_Resumes", exist_ok=True)
        save_path = f"Uploaded_Resumes/{pdf_file.name}"

        with open(save_path, "wb") as f:
            f.write(pdf_file.getbuffer())

        st.subheader("📄 Resume Preview")
        show_pdf_all_pages(save_path)

        resume_text = extract_text_from_pdf(save_path)
        st.session_state["resume_text"] = resume_text

        skills = []
        keywords = [
            "python","java","c++","aws","docker","kubernetes",
            "rtos","embedded","lte","5g","cloud","fintech",
            "devops","react","sql"
        ]
        for kw in keywords:
            if kw in resume_text.lower():
                skills.append(kw)

        domain = detect_domain(skills, resume_text)
        experience = detect_experience(resume_text)
        score = resume_score(resume_text)

        st.header("📊 Resume Insights")
        st.write("**Best-fit Domain:**", domain)
        st.write("**Experience Level:**", experience)
        st.write("**Resume Strength Score:**", f"{score}%")

        st.subheader("Detected Skills")
        st_tags(label="Skills", value=skills, key="skills")

# ================= Job Match =================
elif section == "Job Match":

    st.subheader("Paste Job Description")
    jd_text = st.text_area("Job Description", height=220)

    if st.button("Analyze Job Fit"):
        resume_text = st.session_state.get("resume_text", "")

        if not resume_text:
            st.warning("Please upload a resume first.")
        else:
            with st.spinner("Analyzing resume vs job description..."):
                prompt = f"""
You are a career coach.

Analyze the resume against the job description and provide:
1. Role fit assessment
2. Matching strengths
3. Missing skills / gaps
4. Clear improvement suggestions

Resume:
{resume_text}

Job Description:
{jd_text}
"""
                ai_output = ask_ai(prompt)

            st.success("🤖 AI Job Match Insights")
            st.write(ai_output)

            # -------- Buy Me a Coffee (CONTEXTUAL) --------
            st.markdown("---")
            st.markdown(
                """
                <div style="text-align: center; color: grey; font-size: 14px;">
                    <p>
                        If CareerScope AI helped you gain clarity, you can support this project ☕
                    </p>
                    <p>
                        <a href="https://www.buymeacoffee.com/revanththiruvallur"
                           target="_blank"
                           style="font-weight: bold; text-decoration: none;">
                           👉 Buy me a coffee
                        </a>
                    </p>
                </div>
                """,
                unsafe_allow_html=True
            )

# ================= About =================
else:
    st.markdown("""
### About CareerScope AI

CareerScope AI is an explainable career intelligence tool that helps professionals
understand **where their resume fits**, **how it matches a job description**, and
**what to improve** — beyond keyword stuffing.

Built as a learning and product experiment.

🔗 Live Demo: https://careerscopeai.in
""")
