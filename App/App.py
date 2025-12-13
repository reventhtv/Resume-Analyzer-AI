import streamlit as st
import os
import re
import csv
import random
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
    page_title="CareerScope AI",
    page_icon="🎯",
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
                img = page.to_image(resolution=150).original
                st.image(img, caption=f"Page {i}", use_column_width=True)
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
        "summary", "education", "experience", "skills",
        "projects", "certification", "achievement", "internship"
    ]
    for sec in sections:
        if sec in text:
            score += 12
    return min(score, 100)

# ================= Domain Detection (v2.0) =================

def detect_domain_with_confidence(text):
    scores = {
        "Embedded Systems": 0,
        "Telecommunications": 0,
        "Cloud Engineering": 0,
        "DevOps / Platform": 0,
        "Cybersecurity": 0,
        "Data Science": 0,
        "Web Development": 0,
    }

    strong_signals = {
        "Embedded Systems": ["embedded", "firmware", "rtos", "microcontroller", "c++", "iot"],
        "Telecommunications": ["telecom", "lte", "5g", "rf", "ran", "3gpp"],
        "Cloud Engineering": ["terraform", "cloudformation", "vpc", "iam", "eks", "gke"],
        "DevOps / Platform": ["kubernetes", "helm", "ci/cd", "jenkins", "sre"],
        "Cybersecurity": ["siem", "soc", "pentest", "threat modeling", "iso 27001"],
        "Data Science": ["machine learning", "tensorflow", "pytorch"],
        "Web Development": ["react", "django", "javascript"]
    }

    weak_signals = {
        "Cloud Engineering": ["aws", "azure", "gcp"],
        "DevOps / Platform": ["docker", "linux"],
        "Cybersecurity": ["security"]
    }

    for domain, keys in strong_signals.items():
        for k in keys:
            if k in text:
                scores[domain] += 3

    for domain, keys in weak_signals.items():
        for k in keys:
            if k in text:
                scores[domain] += 1

    # Company boosts
    if "ericsson" in text:
        scores["Telecommunications"] += 6
    if "verisure" in text:
        scores["Embedded Systems"] += 5

    best_domain = max(scores, key=scores.get)
    total = sum(scores.values()) or 1
    confidence = int((scores[best_domain] / total) * 100)

    return best_domain, confidence

# ================= Management =================

def management_confidence(text):
    score = 0
    if "pmp" in text: score += 40
    if "capm" in text: score += 30
    if any(k in text for k in ["program manager", "project manager", "roadmap"]):
        score += 30
    return min(score, 100)

# ================= ATS Gap =================

ATS_KEYWORDS = {
    "Telecommunications": ["3gpp", "o-ran", "link budget", "mac layer"],
    "Embedded Systems": ["bare metal", "interrupts", "spi", "i2c"],
    "Cloud Engineering": ["autoscaling", "disaster recovery", "load balancer"],
    "DevOps / Platform": ["canary deployment", "infra as code"],
    "Cybersecurity": ["incident response", "risk assessment"]
}

def ats_gap(domain, text):
    return [k for k in ATS_KEYWORDS.get(domain, []) if k not in text]

# ================= Role Fit =================

def suggest_roles(domain, exp_level, pm_conf):
    base_roles = {
        "Telecommunications": ["RAN Engineer", "Wireless Systems Engineer"],
        "Embedded Systems": ["Embedded Systems Engineer", "Firmware Engineer"],
        "Cloud Engineering": ["Cloud Engineer", "Site Reliability Engineer"],
        "DevOps / Platform": ["DevOps Engineer", "Platform Engineer"],
        "Cybersecurity": ["Security Engineer", "SOC Analyst"],
    }

    roles = base_roles.get(domain, []).copy()

    if exp_level == "Experienced":
        roles = [f"Senior {r}" for r in roles]

    if pm_conf >= 60:
        roles.append(f"Technical Program Manager ({domain})")

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

st.title("🎯 CareerScope AI")
st.caption("Career & Role Intelligence Platform")

choice = st.sidebar.selectbox("Navigate", ["Career Analysis", "About"])

if choice == "Career Analysis":

    pdf = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

    if pdf:
        os.makedirs("Uploaded_Resumes", exist_ok=True)
        path = f"Uploaded_Resumes/{pdf.name}"
        with open(path, "wb") as f:
            f.write(pdf.getbuffer())

        render_pdf_preview_all_pages(path)

        text = extract_text_from_pdf(path)
        pages = text.count("\f") + 1

        # -------- Career Insights --------
        st.header("Career Insights")

        exp = detect_experience_level(text, pages)
        st.subheader("🧭 Experience Level")
        st.info(exp)

        st.subheader("📊 Resume Strength Score")
        st.progress(calculate_resume_score(text) / 100)

        domain, conf = detect_domain_with_confidence(text)
        st.subheader("🎯 Primary Technical Domain")
        st.success(f"{domain} ({conf}% confidence)")

        # -------- Skills --------
        skill_keywords = [
            "python","c","c++","java","aws","docker","kubernetes","rtos",
            "5g","lte","ran","terraform","jenkins","linux","security"
        ]
        detected_skills = sorted({k for k in skill_keywords if k in text})

        st.subheader("🧠 Detected Skills")
        st_tags(label="Skills", value=detected_skills, key="skills")

        # -------- ATS --------
        missing = ats_gap(domain, text)
        if missing:
            st.subheader("⚠️ ATS Keyword Gaps")
            for k in missing:
                st.write("•", k)

        # -------- Management --------
        pm_conf = management_confidence(text)
        if pm_conf:
            st.subheader("📌 Management Readiness")
            st.progress(pm_conf / 100)
            st.metric("PM Confidence", f"{pm_conf}%")

        # -------- Role Fit --------
        st.subheader("🎯 Best-fit Roles")
        for r in suggest_roles(domain, exp, pm_conf):
            st.write("•", r)

        # -------- Courses --------
        st.subheader("📚 Course Recommendations")

        domain_course_map = {
            "Telecommunications": ds_course,
            "Embedded Systems": android_course,
            "Cloud Engineering": web_course,
            "DevOps / Platform": web_course,
            "Cybersecurity": ds_course,
            "Data Science": ds_course,
            "Web Development": web_course
        }

        course_list = domain_course_map.get(domain)
        if course_list:
            for i, (name, link) in enumerate(course_list[:5], 1):
                st.markdown(f"{i}. [{name}]({link})")

        # -------- AI Advisor --------
        st.markdown("---")
        st.subheader("🤖 AI Career Advisor")
        if st.button("Get AI Guidance"):
            st.write(ask_ai(text))

        # -------- Videos --------
        st.subheader("🎥 Resume Tips")
        st.video(random.choice(resume_videos))

        st.subheader("🎥 Interview Tips")
        st.video(random.choice(interview_videos))

        # -------- Feedback --------
        st.markdown("---")
        st.subheader("⭐ Feedback")
        with st.form("feedback"):
            name = st.text_input("Name (optional)")
            rating = st.slider("Rating", 1, 5, 4)
            comment = st.text_area("Comment")
            if st.form_submit_button("Submit"):
                save_feedback(name, rating, comment)
                st.success("Thanks for helping improve CareerScope AI 🙌")

else:
    st.markdown("""
    ## CareerScope AI (v2.1)

    A career intelligence platform that provides:
    - Accurate domain detection
    - ATS gap analysis
    - Role-fit recommendations
    - Management readiness insights

    Built with ❤️ using Streamlit.
    """)
