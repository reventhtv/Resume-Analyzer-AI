import streamlit as st
import os
import re
import base64
import random
import pdfplumber
from streamlit_tags import st_tags
from Courses import (
    ds_course, web_course, android_course,
    ios_course, uiux_course,
    resume_videos, interview_videos
)

# ================= Page Config =================
st.set_page_config(
    page_title="CareerScope AI",
    page_icon="🎯",
    layout="wide"
)

# ================= AI Client =================
try:
    from ai_client import ask_ai
except Exception:
    def ask_ai(prompt):
        return "AI service temporarily unavailable."

# ================= Helpers =================
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
        f"<iframe src='data:application/pdf;base64,{b64}' width='100%' height='800'></iframe>",
        unsafe_allow_html=True
    )

def normalize(text):
    return text.lower() if text else ""

# ================= App Header =================
st.title("🎯 CareerScope AI")
st.caption("Career & Role Intelligence Platform")

# ================= Sidebar =================
page = st.sidebar.radio(
    "Navigate",
    ["Resume Overview", "Career Insights", "Growth & Guidance", "Job Match"]
)

st.sidebar.markdown("---")
pdf_file = st.sidebar.file_uploader("Upload Resume (PDF)", type=["pdf"])

if pdf_file:
    os.makedirs("Uploaded_Resumes", exist_ok=True)
    path = f"Uploaded_Resumes/{pdf_file.name}"
    with open(path, "wb") as f:
        f.write(pdf_file.getbuffer())

    resume_text = extract_text_from_pdf(path)
    st.session_state["resume_text"] = resume_text
    st.session_state["resume_uploaded"] = True

# ======================================================
# ================= RESUME OVERVIEW ====================
# ======================================================
if page == "Resume Overview":

    if not st.session_state.get("resume_uploaded"):
        st.info("Upload a resume to begin.")
    else:
        st.subheader("📄 Resume Preview")
        show_pdf(path)

        text = normalize(st.session_state["resume_text"])

        structure_score = min(100, len(re.findall(r"\n", text)) * 2)
        st.subheader("📊 Resume Structure Score (ATS Readiness)")
        st.progress(structure_score / 100)
        st.write(f"Score: **{structure_score}%**")

# ======================================================
# ================= CAREER INSIGHTS ===================
# ======================================================
elif page == "Career Insights":

    if not st.session_state.get("resume_uploaded"):
        st.info("Upload a resume to view insights.")
    else:
        text = normalize(st.session_state["resume_text"])

        # Experience Level
        if any(k in text for k in ["lead", "manager", "architect", "principal"]):
            experience = "Experienced"
        elif "intern" in text:
            experience = "Entry / Intermediate"
        else:
            experience = "Mid-level"

        st.subheader("🧠 Experience Level")
        st.success(experience)

        # Domain Detection
        domains = {
            "Telecommunications": ["ran", "lte", "5g", "telecom", "ericsson"],
            "Embedded Systems": ["embedded", "rtos", "firmware"],
            "Cloud / DevOps": ["aws", "docker", "kubernetes", "terraform"],
            "FinTech": ["fintech", "payments", "banking"],
            "Cybersecurity": ["security", "siem", "soc"],
            "Program Management": ["pmp", "capm", "roadmap", "stakeholder"]
        }

        domain_scores = {d: sum(1 for k in v if k in text) for d, v in domains.items()}
        primary_domain = max(domain_scores, key=domain_scores.get)

        st.subheader("🎯 Primary Domain")
        st.success(primary_domain)

        # Expertise Score
        expertise_score = min(100, domain_scores[primary_domain] * 20)
        st.subheader("🧠 Domain Expertise Score")
        st.progress(expertise_score / 100)
        st.write(f"Expertise: **{expertise_score}%**")

        # Management Readiness
        pm_confidence = 100 if any(k in text for k in ["pmp", "capm"]) else 60
        st.subheader("📌 Management Readiness")
        st.progress(pm_confidence / 100)
        st.write(f"PM Confidence: **{pm_confidence}%**")

# ======================================================
# ================= GROWTH & GUIDANCE ==================
# ======================================================
elif page == "Growth & Guidance":

    if not st.session_state.get("resume_uploaded"):
        st.info("Upload a resume to view guidance.")
    else:
        st.subheader("📚 Course Recommendations")
        for i, (name, link) in enumerate(web_course[:5], 1):
            st.markdown(f"{i}. [{name}]({link})")

        st.subheader("🎥 Resume Tips")
        st.video(random.choice(resume_videos))

        st.subheader("🎥 Interview Tips")
        st.video(random.choice(interview_videos))

# ======================================================
# ================= JOB MATCH ==========================
# ======================================================
elif page == "Job Match":

    if not st.session_state.get("resume_uploaded"):
        st.info("Upload a resume to match with a job description.")
    else:
        jd = st.text_area("📌 Paste Job Description")

        if st.button("Analyze Job Fit"):
            st.session_state["job_fit_done"] = True

            combined = normalize(st.session_state["resume_text"] + jd)

            role_keywords = {
                "Technical Program Manager": ["program", "roadmap", "stakeholder"],
                "RAN Engineer": ["ran", "lte", "5g"],
                "Embedded Lead": ["embedded", "firmware", "rtos"],
                "Cloud Engineer": ["aws", "kubernetes"],
                "DevOps Engineer": ["ci/cd", "pipeline", "terraform"]
            }

            scores = {r: sum(1 for k in v if k in combined) for r, v in role_keywords.items()}
            best_roles = sorted(scores, key=scores.get, reverse=True)[:3]
            fit_score = min(100, sum(scores.values()) * 10)

            st.success("### ✅ Job Fit Summary")
            st.write("**Best-fit Roles:**")
            for r in best_roles:
                st.write(f"- {r}")
            st.write(f"**Role Fit Score:** {fit_score}%")

        # ========== Buy Me a Coffee (FIXED) ==========
        if st.session_state.get("job_fit_done"):
            st.markdown(
                """
                <div style="
                    background-color:#f8f9fa;
                    padding:18px;
                    border-radius:12px;
                    border:1px solid #e0e0e0;
                    text-align:center;
                    margin-top:24px;
                    margin-bottom:24px;
                ">
                    <h4>☕ Found CareerScope AI useful?</h4>
                    <p style="font-size:15px;">
                        If this helped you gain clarity on your career direction,
                        you can support the project with a coffee.
                    </p>
                    <a href="https://www.buymeacoffee.com/revanththiruvallur"
                       target="_blank"
                       style="
                         display:inline-block;
                         padding:10px 20px;
                         background-color:#ffdd00;
                         color:#000;
                         font-weight:600;
                         border-radius:8px;
                         text-decoration:none;
                       ">
                       Buy me a coffee ☕
                    </a>
                </div>
                """,
                unsafe_allow_html=True
            )

        # AI Suggestions
        if st.session_state.get("job_fit_done"):
            st.subheader("🤖 AI JD-Specific Resume Improvements")
            if st.button("Get AI Improvement Suggestions"):
                with st.spinner("Generating AI insights…"):
                    prompt = f"""
                    You are a senior hiring manager.
                    Suggest resume improvements for this job.

                    RESUME:
                    {st.session_state["resume_text"]}

                    JOB DESCRIPTION:
                    {jd}
                    """
                    st.write(ask_ai(prompt))
