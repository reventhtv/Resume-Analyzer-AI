import streamlit as st
import os
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
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            img = page.to_image(resolution=150).original
            st.image(img, caption=f"Page {i}", use_column_width=True)

# ================= Experience =================

def detect_experience_level(text):
    if any(k in text for k in ["senior", "lead", "architect", "manager"]):
        return "Experienced"
    if any(k in text for k in ["internship", "intern", "trainee"]):
        return "Intermediate"
    return "Fresher"

# ================= Resume Structure =================

def calculate_structure_score(text):
    score = 0
    sections = [
        "summary", "education", "experience", "skills",
        "projects", "certification", "achievement", "internship"
    ]
    for sec in sections:
        if sec in text:
            score += 12
    return min(score, 100)

# ================= Domain & Expertise =================

def detect_domain_and_expertise(text):
    domain_map = {
        "Telecommunications": ["5g", "lte", "ran", "rf", "3gpp"],
        "Embedded Systems": ["embedded", "firmware", "rtos", "microcontroller"],
        "Cloud Engineering": ["terraform", "cloudformation", "iam", "vpc"],
        "DevOps / Platform": ["kubernetes", "helm", "ci/cd", "jenkins"],
        "Cybersecurity": ["soc", "siem", "pentest", "iso 27001"],
        "Data Science": ["machine learning", "tensorflow"],
        "Web Development": ["react", "django", "javascript"]
    }

    scores = {d: 0 for d in domain_map}
    matched = {d: [] for d in domain_map}

    for domain, keys in domain_map.items():
        for k in keys:
            if k in text:
                scores[domain] += 2
                matched[domain].append(k)

    if "ericsson" in text:
        scores["Telecommunications"] += 6
    if "verisure" in text:
        scores["Embedded Systems"] += 5

    best_domain = max(scores, key=scores.get)
    expertise_score = min(int((scores[best_domain] / (sum(scores.values()) or 1)) * 100), 100)

    return best_domain, expertise_score, matched

# ================= Management =================

def management_confidence(text):
    score = 0
    if "pmp" in text: score += 40
    if "capm" in text: score += 30
    if "program manager" in text: score += 30
    return min(score, 100)

# ================= JD MATCHER (v2.5) =================

def jd_matcher(resume_text, jd_text, domain, exp_level, pm_score):
    resume_words = set(resume_text.split())
    jd_words = set(jd_text.lower().split())

    matched = resume_words & jd_words
    missing = jd_words - resume_words

    skill_score = min(int(len(matched) / (len(jd_words) or 1) * 100), 100)

    domain_bonus = 25 if domain.lower() in jd_text.lower() else 0
    exp_bonus = 15 if exp_level.lower() in jd_text.lower() else 0
    pm_bonus = 10 if pm_score >= 60 else 0

    final_score = min(skill_score * 0.5 + domain_bonus + exp_bonus + pm_bonus, 100)

    return int(final_score), sorted(matched), sorted(list(missing))[:15]

# ================= UI =================

st.title("🎯 CareerScope AI")
st.caption("Career & Role Intelligence Platform")

page = st.sidebar.radio(
    "Navigate",
    ["Resume Overview", "Career Insights", "Growth & Guidance", "🎯 Job Match"]
)

pdf = st.sidebar.file_uploader("Upload Resume (PDF)", type=["pdf"])

if pdf:
    os.makedirs("Uploaded_Resumes", exist_ok=True)
    path = f"Uploaded_Resumes/{pdf.name}"
    with open(path, "wb") as f:
        f.write(pdf.getbuffer())

    text = extract_text_from_pdf(path)

    exp = detect_experience_level(text)
    structure_score = calculate_structure_score(text)
    domain, expertise_score, matched_domain_keys = detect_domain_and_expertise(text)
    pm_conf = management_confidence(text)

    # -------- Resume Overview --------
    if page == "Resume Overview":
        render_pdf_preview_all_pages(path)

        st.subheader("📊 Resume Structure Score (ATS)")
        st.progress(structure_score / 100)
        st.metric("Score", f"{structure_score}%")

        st.subheader("🧭 Experience Level")
        st.info(exp)

    # -------- Career Insights --------
    elif page == "Career Insights":
        st.subheader("🎯 Primary Domain")
        st.success(domain)

        st.subheader("🧠 Domain Expertise Score")
        st.progress(expertise_score / 100)
        st.metric("Expertise", f"{expertise_score}%")

        if pm_conf:
            st.subheader("📌 Management Readiness")
            st.progress(pm_conf / 100)
            st.metric("PM Confidence", f"{pm_conf}%")

    # -------- Growth --------
    elif page == "Growth & Guidance":
        st.subheader("📚 Course Recommendations")
        course_map = {
            "Telecommunications": ds_course,
            "Embedded Systems": android_course,
            "Cloud Engineering": web_course,
            "DevOps / Platform": web_course,
            "Cybersecurity": ds_course,
        }
        for i, (name, link) in enumerate(course_map.get(domain, [])[:5], 1):
            st.markdown(f"{i}. [{name}]({link})")

        st.subheader("🤖 AI Career Advisor")
        if st.button("Get AI Guidance"):
            st.write(ask_ai(text))

    # -------- JD MATCH --------
    else:
        st.subheader("🎯 Job Description Matcher")

        jd_text = st.text_area(
            "Paste Job Description",
            height=250,
            placeholder="Paste the job description here..."
        )

        if jd_text and st.button("Analyze Job Fit"):
            score, matched, missing = jd_matcher(
                text, jd_text, domain, exp, pm_conf
            )

            st.subheader("📊 Role Fit Score")
            st.progress(score / 100)
            st.metric("Fit Score", f"{score}%")

            st.subheader("✅ Matched Keywords")
            st.write(", ".join(matched[:20]) or "—")

            st.subheader("⚠️ Missing Keywords")
            for k in missing:
                st.write("•", k)

else:
    st.info("Upload a resume to get started.")
