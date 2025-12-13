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
    return text.lower()

def render_pdf_preview_all_pages(path):
    st.subheader("📄 Resume Preview")
    try:
        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                image = page.to_image(resolution=150).original
                st.image(image, caption=f"Page {i}", use_column_width=True)
    except Exception:
        st.info("Preview not available.")

# ================= Experience =================

def detect_experience_level(text, pages):
    if any(k in text for k in ["senior", "lead", "architect", "manager"]):
        return "Experienced"
    if any(k in text for k in ["internship", "intern", "trainee"]):
        return "Intermediate"
    if pages >= 2:
        return "Intermediate"
    return "Fresher"

# ================= Resume Score =================

def calculate_resume_score(text):
    score = 0
    sections = [
        "summary", "education", "experience",
        "skills", "projects", "certification",
        "achievement", "internship"
    ]
    for sec in sections:
        if sec in text:
            score += 12
    return min(score, 100)

# ================= Domain + Confidence =================

def detect_domain_with_confidence(text, skills):
    scores = {
        "Embedded Systems": 0,
        "Telecommunications": 0,
        "Data Science": 0,
        "Web Development": 0,
    }

    keywords = {
        "Embedded Systems": ["embedded", "firmware", "rtos", "microcontroller", "c", "c++", "iot"],
        "Telecommunications": ["telecom", "lte", "5g", "rf", "ran", "wireless", "protocol", "3gpp"],
        "Data Science": ["machine learning", "tensorflow", "pytorch"],
        "Web Development": ["react", "django", "javascript"]
    }

    for domain, keys in keywords.items():
        for k in keys:
            if k in text or k in skills:
                scores[domain] += 3

    if "ericsson" in text:
        scores["Telecommunications"] += 6
    if "verisure" in text:
        scores["Embedded Systems"] += 5

    if "python" in skills:
        scores["Data Science"] += 1

    best = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    confidence = int((scores[best] / total) * 100)

    return best, confidence

# ================= Management =================

def management_confidence(text):
    score = 0
    if "pmp" in text: score += 40
    if "capm" in text: score += 30
    if any(k in text for k in ["program manager", "project manager", "roadmap", "delivery"]):
        score += 30
    return min(score, 100)

# ================= ATS Gap =================

ATS_KEYWORDS = {
    "Telecommunications": ["3gpp", "o-ran", "link budget", "ran", "mac layer"],
    "Embedded Systems": ["bare metal", "interrupts", "dma", "spi", "i2c"],
}

def ats_gap(domain, text):
    return [k for k in ATS_KEYWORDS.get(domain, []) if k not in text]

# ================= Role Fit (NEW v1.8) =================

def suggest_roles(domain, exp_level, pm_conf, text):
    roles = []

    if domain == "Telecommunications":
        roles.append("RAN Engineer")
        roles.append("Wireless Systems Engineer")
        if exp_level == "Experienced":
            roles.append("Senior Telecom Engineer")

    if domain == "Embedded Systems":
        roles.append("Embedded Systems Engineer")
        roles.append("Firmware Engineer")
        if exp_level == "Experienced":
            roles.append("Embedded Systems Lead")

    if pm_conf >= 60:
        roles.append("Technical Program Manager")
        roles.append("Program Manager")

    if domain in ["Telecommunications", "Embedded Systems"] and pm_conf >= 60:
        roles.append("Technical Program Manager (Domain-specific)")

    # Remove duplicates
    return list(dict.fromkeys(roles))

# ================= Feedback =================

FEEDBACK_FILE = "feedback.csv"

def save_feedback(name, rating, comment):
    exists = os.path.exists(FEEDBACK_FILE)
    with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not exists:
            writer.writerow(["timestamp", "name", "rating", "comment"])
        writer.writerow([datetime.datetime.now(), name, rating, comment])

# ================= UI =================

st.title("AI-Powered Resume Analyzer")
choice = st.sidebar.selectbox("Choose section", ["User", "About"])

if choice == "User":
    pdf = st.file_uploader("Upload your resume (PDF)", type=["pdf"])
    if pdf:
        os.makedirs("Uploaded_Resumes", exist_ok=True)
        path = f"Uploaded_Resumes/{pdf.name}"
        with open(path, "wb") as f:
            f.write(pdf.getbuffer())

        render_pdf_preview_all_pages(path)

        text = extract_text_from_pdf(path)
        pages = text.count("\f") + 1

        skills = [k for k in [
            "python","c","c++","rtos","lte","5g","rf",
            "iot","react","django","tensorflow","pmp","capm"
        ] if k in text]

        st.header("Resume Analysis")

        exp = detect_experience_level(text, pages)
        st.subheader("🧭 Experience Level")
        st.info(exp)

        st.subheader("📊 Resume Score")
        st.progress(calculate_resume_score(text) / 100)

        domain, conf = detect_domain_with_confidence(text, skills)
        st.subheader("🎯 Primary Technical Domain")
        st.success(f"{domain} ({conf}% confidence)")

        missing = ats_gap(domain, text)
        if missing:
            st.subheader("⚠️ ATS Keyword Gaps")
            for k in missing:
                st.write("•", k)

        pm_conf = management_confidence(text)
        if pm_conf > 0:
            st.subheader("📌 Program / Project Management Readiness")
            st.progress(pm_conf / 100)
            st.metric("PM Confidence", f"{pm_conf}%")

        st.subheader("🎯 Best-fit Roles (v1.8)")
        roles = suggest_roles(domain, exp, pm_conf, text)
        for r in roles:
            st.write("•", r)

        st.subheader("🧠 Detected Skills")
        st_tags(label="Skills", value=skills, key="skills")

        st.markdown("---")
        st.subheader("🤖 AI Suggestions")
        if st.button("Get AI Suggestions"):
            st.write(ask_ai(text))

        st.subheader("⭐ Feedback")
        with st.form("feedback"):
            name = st.text_input("Name")
            rating = st.slider("Rating", 1, 5, 4)
            comment = st.text_area("Comment")
            if st.form_submit_button("Submit"):
                save_feedback(name, rating, comment)
                st.success("Thanks for your feedback!")

else:
    st.markdown("""
    ### AI Resume Analyzer (v1.8)

    - Role fit suggestions (TPM, RAN Engineer, Embedded Lead)
    - Domain confidence scoring
    - ATS keyword gaps
    - PMP / CAPM detection
    - Resume preview & scoring

    Built with ❤️ using Streamlit.
    """)
