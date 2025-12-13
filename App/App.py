import streamlit as st
import os
import re
import random
import csv
import datetime
import pdfplumber
from streamlit_tags import st_tags

from Courses import (
    ds_course, web_course, android_course,
    ios_course, uiux_course,
    resume_videos, interview_videos
)

# ---------- Page config ----------
st.set_page_config(
    page_title="AI Resume Analyzer",
    page_icon="📄",
    layout="wide"
)

# ---------- AI client ----------
try:
    from ai_client import ask_ai
except Exception:
    def ask_ai(prompt):
        return "AI client not configured."

# ================= Helpers =================

def extract_text_from_pdf(path):
    text = ""
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def render_pdf_preview_all_pages(path):
    st.subheader("📄 Resume Preview")
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                image = page.to_image(resolution=150).original
                st.image(image, caption=f"Page {i}", use_column_width=True)
    except Exception:
        st.info("Preview not available.")

# ================= Feature 1: Experience =================

def detect_experience_level(resume_text, pages):
    text = resume_text.lower()
    if any(k in text for k in ["senior", "lead", "manager", "architect"]):
        return "Experienced"
    if any(k in text for k in ["internship", "intern", "trainee"]):
        return "Intermediate"
    if pages >= 2:
        return "Intermediate"
    return "Fresher"

# ================= Feature 2: Resume Score =================

def calculate_resume_score(resume_text):
    text = resume_text.lower()
    score = 0
    feedback = []

    sections = {
        "Summary / Objective": (["summary", "objective"], 10),
        "Education": (["education", "degree"], 15),
        "Experience": (["experience", "work experience"], 20),
        "Skills": (["skills"], 15),
        "Projects": (["project"], 15),
        "Certifications": (["certification"], 10),
        "Achievements": (["achievement"], 10),
        "Internships": (["internship"], 5),
    }

    for name, (keys, pts) in sections.items():
        if any(k in text for k in keys):
            score += pts
        else:
            feedback.append(f"Add a {name} section.")

    return min(score, 100), feedback

# ================= Feature 3: Domain Detection (FIXED) =================

def detect_domain(skills, resume_text):
    text = resume_text.lower()
    skills = [s.lower() for s in skills]

    scores = {
        "Embedded Systems": 0,
        "Telecommunications": 0,
        "Data Science": 0,
        "Web Development": 0,
        "Android Development": 0,
        "iOS Development": 0,
        "UI/UX Design": 0,
    }

    keyword_map = {
        "Embedded Systems": (["embedded", "firmware", "rtos", "microcontroller", "c", "c++", "iot"], 3),
        "Telecommunications": (["telecom", "lte", "5g", "rf", "ran", "wireless", "protocol"], 3),
        "Data Science": (["machine learning", "deep learning", "tensorflow", "pytorch"], 2),
        "Web Development": (["react", "django", "javascript"], 2),
        "Android Development": (["android", "kotlin", "flutter"], 2),
        "iOS Development": (["ios", "swift"], 2),
        "UI/UX Design": (["figma", "ux", "ui"], 2),
    }

    for domain, (keys, weight) in keyword_map.items():
        for k in keys:
            if k in skills or k in text:
                scores[domain] += weight

    # Company-based boosts
    if "ericsson" in text:
        scores["Telecommunications"] += 5
    if "verisure" in text:
        scores["Embedded Systems"] += 4

    # Python = weak DS signal
    if "python" in skills:
        scores["Data Science"] += 1

    best_domain = max(scores, key=scores.get)
    if scores[best_domain] == 0:
        return "General / Undetermined", []

    domain_courses = {
        "Data Science": ds_course,
        "Web Development": web_course,
        "Android Development": android_course,
        "iOS Development": ios_course,
        "UI/UX Design": uiux_course,
        "Embedded Systems": [],
        "Telecommunications": []
    }

    return best_domain, domain_courses.get(best_domain, [])

# ================= Feature 4: Management Qualification =================

def detect_management_qualification(resume_text):
    text = resume_text.lower()
    signals = {
        "PMP Certified": ["pmp", "project management professional"],
        "CAPM Certified": ["capm", "certified associate in project management"],
        "Agile / Scrum": ["scrum", "agile", "sprint"],
        "Program / Project Management Experience": [
            "program manager", "project manager",
            "technical program manager", "stakeholder",
            "milestones", "delivery", "roadmap"
        ]
    }

    detected = []
    for label, keys in signals.items():
        if any(k in text for k in keys):
            detected.append(label)
    return detected

# ================= Feature 5: Feedback (CSV) =================

FEEDBACK_FILE = "feedback.csv"

def save_feedback(name, rating, comment):
    exists = os.path.exists(FEEDBACK_FILE)
    with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["timestamp", "name", "rating", "comment"])
        writer.writerow([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            name, rating, comment
        ])

# ================= UI =================

st.title("AI-Powered Resume Analyzer")
choice = st.sidebar.selectbox("Choose section", ["User", "About"])

# ================= USER =================

if choice == "User":

    pdf_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

    if pdf_file:
        os.makedirs("Uploaded_Resumes", exist_ok=True)
        path = f"Uploaded_Resumes/{pdf_file.name}"
        with open(path, "wb") as f:
            f.write(pdf_file.getbuffer())

        render_pdf_preview_all_pages(path)

        resume_text = extract_text_from_pdf(path)
        pages = resume_text.count("\f") + 1

        skills = []
        skill_keywords = [
            "python","c","c++","java","rtos","embedded","firmware",
            "lte","5g","rf","telecom","iot","react","django",
            "tensorflow","kotlin","swift","figma"
        ]

        for k in skill_keywords:
            if k in resume_text.lower():
                skills.append(k)

        st.header("Resume Analysis")

        st.subheader("🧭 Experience Level")
        st.info(detect_experience_level(resume_text, pages))

        st.subheader("📊 Resume Score")
        score, tips = calculate_resume_score(resume_text)
        st.progress(score / 100)
        st.metric("Score", f"{score}/100")
        for t in tips:
            st.write("•", t)

        domain, courses = detect_domain(skills, resume_text)
        st.subheader("🎯 Primary Technical Domain")
        st.success(domain)

        mgmt = detect_management_qualification(resume_text)
        if mgmt:
            st.subheader("📌 Management Qualification Detected")
            for m in mgmt:
                st.info(m)

        st.subheader("🧠 Detected Skills")
        st_tags(label="Skills", value=skills, key="skills")

        if courses:
            st.subheader("📚 Course Recommendations")
            for c in courses[:5]:
                st.markdown(f"- [{c[0]}]({c[1]})")

        st.markdown("---")
        st.subheader("🤖 AI Suggestions")
        if st.button("Get AI Suggestions"):
            with st.spinner("Analyzing with Gemini…"):
                st.write(ask_ai(resume_text))

        st.subheader("⭐ Feedback")
        with st.form("feedback"):
            name = st.text_input("Name (optional)")
            rating = st.slider("Rating", 1, 5, 4)
            comment = st.text_area("Comment")
            submit = st.form_submit_button("Submit")
            if submit:
                save_feedback(name, rating, comment)
                st.success("Thank you for your feedback!")

# ================= ABOUT =================

else:
    st.markdown("""
    ### AI Resume Analyzer

    - Multi-page resume preview  
    - Correct domain detection (Embedded & Telecom aware)  
    - PMP / CAPM & Program Management recognition  
    - Resume scoring & experience detection  
    - AI feedback (Gemini)  
    - No database, cloud-safe  

    Built with ❤️ using Streamlit.
    """)
