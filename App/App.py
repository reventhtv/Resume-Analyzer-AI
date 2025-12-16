import streamlit as st
import os
import io
import re
import random
import base64
import time
import pdfplumber

from streamlit_tags import st_tags
from Courses import (
    ds_course, web_course, android_course,
    ios_course, uiux_course,
    resume_videos, interview_videos
)

# ==============================
# Page Configuration
# ==============================
st.set_page_config(
    page_title="CareerScope AI",
    page_icon="📊",
    layout="wide"
)

st.title("CareerScope AI")
st.caption("Understand your resume. Understand your career.")

# ==============================
# Sidebar
# ==============================
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Resume Analyzer", "About"]
)

# ==============================
# AI Client
# ==============================
try:
    from ai_client import ask_ai
except Exception:
    def ask_ai(prompt: str):
        return "AI service not configured."

# ==============================
# Helper Functions
# ==============================
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
        <iframe
            src="data:application/pdf;base64,{b64}"
            width="100%"
            height="900"
            style="border:none;"
        ></iframe>
        """,
        unsafe_allow_html=True
    )

def course_recommender(course_list):
    st.subheader("📚 Recommended Learning")
    k = st.slider("Number of courses", 1, 8, 5)
    random.shuffle(course_list)
    for i, (name, link) in enumerate(course_list[:k], 1):
        st.markdown(f"{i}. [{name}]({link})")

# ==============================
# MAIN PAGE
# ==============================
if page == "Resume Analyzer":

    st.subheader("📄 Upload your resume (PDF)")
    pdf_file = st.file_uploader("Choose a PDF file", type=["pdf"])

    if pdf_file:
        os.makedirs("Uploaded_Resumes", exist_ok=True)
        file_path = f"Uploaded_Resumes/{pdf_file.name}"

        with open(file_path, "wb") as f:
            f.write(pdf_file.getbuffer())

        # ---------- Resume Preview ----------
        st.markdown("### 📑 Resume Preview")
        show_pdf(file_path)

        # ---------- Text Extraction ----------
        resume_text = ""
        try:
            resume_text = extract_text_from_pdf(file_path)
        except Exception:
            st.error("Could not extract text from resume.")

        resume_text_lower = resume_text.lower()

        # ---------- Basic Parsing ----------
        email = re.search(r"\S+@\S+\.\S+", resume_text)
        phone = re.search(r"\+?\d[\d\s\-]{8,}", resume_text)

        skills_db = [
            "python","c","c++","embedded","rtos","linux",
            "lte","5g","ran","telecom","iot",
            "aws","azure","gcp","docker","kubernetes",
            "devops","ci/cd","terraform",
            "pmp","capm","scrum","agile",
            "machine learning","data science","sql"
        ]

        skills_found = sorted({
            skill for skill in skills_db
            if skill in resume_text_lower
        })

        pages = resume_text.count("\f") + 1 if resume_text else 1

        # ---------- Resume Strength Breakdown ----------
        st.markdown("## 🧠 Resume Strength Breakdown")

        checks = {
            "Summary / Objective": any(x in resume_text_lower for x in ["summary", "objective"]),
            "Experience Section": "experience" in resume_text_lower,
            "Projects Section": "project" in resume_text_lower,
            "Skills Section": "skill" in resume_text_lower,
            "Certifications": any(x in resume_text_lower for x in ["certification", "pmp", "capm"]),
            "Education": "education" in resume_text_lower,
            "Quantified Impact": bool(re.search(r"\d+%", resume_text))
        }

        for item, passed in checks.items():
            if passed:
                st.success(f"✔ {item}")
            else:
                st.warning(f"✖ {item}")

        # ---------- Resume Score ----------
        structure_score = int((sum(checks.values()) / len(checks)) * 100)
        expertise_score = min(100, len(skills_found) * 8)
        overall_score = int((structure_score * 0.6) + (expertise_score * 0.4))

        st.markdown("## 📊 Resume Scores")
        col1, col2, col3 = st.columns(3)

        col1.metric("Structure Score", f"{structure_score}%")
        col2.metric("Expertise Score", f"{expertise_score}%")
        col3.metric("Overall Strength", f"{overall_score}%")

        # ---------- Experience Level ----------
        st.markdown("## 🧑‍💼 Experience Level")
        if pages >= 2 or "experience" in resume_text_lower:
            st.info("Experienced Professional")
        else:
            st.info("Early Career / Fresher")

        # ---------- Skills ----------
        st.markdown("## 🧩 Detected Skills")
        st_tags(label="Skills", value=skills_found, key="skills")

        # ---------- Domain Detection ----------
        st.markdown("## 🎯 Best-fit Domain")

        domain = "General Engineering"
        if any(x in resume_text_lower for x in ["lte", "ran", "telecom", "5g", "embedded"]):
            domain = "Telecommunications & Embedded Systems"
        elif any(x in resume_text_lower for x in ["aws", "docker", "kubernetes", "devops"]):
            domain = "Cloud & DevOps"
        elif any(x in resume_text_lower for x in ["data science", "machine learning"]):
            domain = "Data Science & AI"
        elif any(x in resume_text_lower for x in ["pmp", "capm"]):
            domain = "Technical Program Management"

        st.success(domain)

        # ---------- Learning Suggestions ----------
        if domain.startswith("Telecom"):
            course_recommender(android_course)
        elif domain.startswith("Cloud"):
            course_recommender(web_course)
        elif domain.startswith("Data"):
            course_recommender(ds_course)

        # ---------- AI Suggestions ----------
        st.markdown("## 🤖 AI Career Insights")

        if st.button("Generate AI Suggestions"):
            with st.spinner("Analyzing your profile..."):
                prompt = f"""
You are a senior career advisor.

Analyze the following resume and provide:
1. Key strengths
2. Gaps or weaknesses
3. Career role recommendations
4. One improvement tip

Resume:
{resume_text}
"""
                response = ask_ai(prompt)
                st.write(response)

        # ---------- Videos ----------
        st.markdown("## 🎥 Career Tips")
        st.video(random.choice(resume_videos))
        st.video(random.choice(interview_videos))

# ==============================
# ABOUT PAGE
# ==============================
else:
    st.markdown("""
### About CareerScope AI

CareerScope AI helps professionals understand their resumes beyond keywords.

**What it does**
- Resume structure & expertise scoring
- Domain and role-fit analysis
- Explainable insights (no black box)
- AI-powered career suggestions

Built for engineers, program managers, and technical leaders.

Soft-launched. Feedback welcome.
""")
