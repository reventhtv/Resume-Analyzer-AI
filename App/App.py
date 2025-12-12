# App/UploadedResumes/App.py
# Cleaned & resilient version of the original App.py
# - Keeps pyresparser usage
# - Makes optional libs safe
# - Ensures NLTK + spaCy model attempts before importing pyresparser
# - Unified PDF extraction helper (pdfminer.six preferred, pdfplumber fallback)
# - Optional DB writes (only if connection successfully established)
# - AI suggestions section kept (uses ai_client.ask_ai)

import os
import io
import base64
import random
import time
import datetime
import socket
import platform
import secrets as pysecrets  # avoid name clash with `secrets` logic
from PIL import Image

# ----------------- Safe optional imports -----------------
_missing_libs = []

def _try_import(name, alias=None):
    try:
        module = __import__(name)
        if alias:
            globals()[alias] = module
        else:
            globals()[name] = module
        return module
    except Exception:
        _missing_libs.append(name)
        globals()[alias or name] = None
        return None

# required core
import streamlit as st
import pandas as pd
import requests

# optional (try to import; if missing, we will degrade gracefully)
_try_import("pymysql")        # database (optional)
_try_import("geocoder")       # IP -> latlong (optional)
_try_import("geopy")          # geocoding (optional)
_try_import("plotly.express", "px")   # plotting (optional)
_try_import("plotly.graph_objects", "go")
_try_import("streamlit_tags") # tags input
_try_import("pdfplumber")     # pdf fallback
# pdfminer will be imported below in a safe manner

# ----------------- Ensure NLTK data present BEFORE importing pyresparser -----------------
import nltk

NLTK_DATA_DIR = os.path.join(os.getcwd(), "nltk_data")
os.makedirs(NLTK_DATA_DIR, exist_ok=True)
if NLTK_DATA_DIR not in nltk.data.path:
    nltk.data.path.insert(0, NLTK_DATA_DIR)

_required_nltk = ["stopwords", "punkt", "averaged_perceptron_tagger"]
for pkg in _required_nltk:
    try:
        if pkg == "punkt":
            nltk.data.find(f"tokenizers/{pkg}")
        elif pkg == "averaged_perceptron_tagger":
            nltk.data.find(f"taggers/{pkg}")
        else:
            nltk.data.find(f"corpora/{pkg}")
    except LookupError:
        try:
            nltk.download(pkg, download_dir=NLTK_DATA_DIR, quiet=True)
        except Exception:
            # log to console; Streamlit logs will capture this
            print(f"Warning: failed to download NLTK package: {pkg}")

# ----------------- Ensure spaCy + model available (for pyresparser) -----------------
# pyresparser expects spaCy (usually v2) and en_core_web_sm model.
_spacy_ok = False
try:
    import spacy
    # try loading model
    try:
        _ = spacy.load("en_core_web_sm")
        _spacy_ok = True
    except Exception:
        # Try programmatic download (may take time on first run)
        try:
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
            _ = spacy.load("en_core_web_sm")
            _spacy_ok = True
        except Exception as e:
            print("spaCy model en_core_web_sm not available and automatic download failed:", e)
            _spacy_ok = False
except Exception:
    _spacy_ok = False

# ----------------- Import pyresparser (now that NLTK prepared) -----------------
try:
    from pyresparser import ResumeParser
except Exception as e:
    # If import fails, set to None and show helpful message later
    ResumeParser = None
    print("Warning: pyresparser not available or failed to import:", e)

# ----------------- Robust pdfminer/pdfplumber support -----------------
_pdfminer_available = False
pdfminer_extract_text = None
try:
    # prefer pdfminer.six imports
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import TextConverter
    from pdfminer.layout import LAParams
    from pdfminer.pdfpage import PDFPage
    def _pdfminer_extract_text(path_or_file):
        # path_or_file can be path or file-like
        resource_manager = PDFResourceManager()
        fake_file_handle = io.StringIO()
        laparams = LAParams()
        converter = TextConverter(resource_manager, fake_file_handle, laparams=laparams)
        interpreter = PDFPageInterpreter(resource_manager, converter)
        # handle file path
        if isinstance(path_or_file, str):
            fh = open(path_or_file, "rb")
            close_after = True
        else:
            fh = path_or_file
            close_after = False
        try:
            for page in PDFPage.get_pages(fh, caching=True, check_extractable=True):
                interpreter.process_page(page)
            text = fake_file_handle.getvalue()
        finally:
            converter.close()
            fake_file_handle.close()
            if close_after:
                fh.close()
        return text
    pdfminer_extract_text = _pdfminer_extract_text
    _pdfminer_available = True
except Exception:
    _pdfminer_available = False

# pdfplumber fallback
_pdfplumber_available = False
try:
    import pdfplumber as _pdfplumber
    _pdfplumber_available = True
except Exception:
    _pdfplumber_available = False

def extract_text_from_pdf(path_or_file):
    """
    Unified PDF extraction helper. Accepts path string or file-like object.
    Tries pdfminer.six first, then pdfplumber.
    """
    if _pdfminer_available:
        try:
            return pdfminer_extract_text(path_or_file)
        except Exception as e:
            print("pdfminer extraction failed, falling back to pdfplumber:", e)

    if _pdfplumber_available:
        try:
            if isinstance(path_or_file, str):
                with _pdfplumber.open(path_or_file) as pdf:
                    pages = [p.extract_text() or "" for p in pdf.pages]
            else:
                with _pdfplumber.open(path_or_file) as pdf:
                    pages = [p.extract_text() or "" for p in pdf.pages]
            return "\n".join(pages)
        except Exception as e:
            print("pdfplumber extraction failed:", e)

    raise RuntimeError("No PDF extraction backend available. Install pdfminer.six or pdfplumber.")

# ----------------- Import other utilities -----------------
try:
    from streamlit_tags import st_tags
except Exception:
    # fallback function if st_tags not available
    def st_tags(label="", text="", value=None, key=None):
        # display simple text list
        if value:
            st.write(f"{label} {', '.join(value)}")
        else:
            st.write(label)

# ----------------- Courses list import (local) -----------------
try:
    from Courses import ds_course,web_course,android_course,ios_course,uiux_course,resume_videos,interview_videos
except Exception:
    # Fallback small lists if Courses.py missing
    ds_course = web_course = android_course = ios_course = uiux_course = []
    resume_videos = interview_videos = []

# ----------------- Safe DB connection (optional) -----------------
_db_conn = None
_db_cursor = None
try:
    # If Streamlit Secrets provide DB config, use them; otherwise attempt localhost default
    DB_HOST = os.environ.get("DB_HOST") or (st.secrets.get("DB_HOST") if hasattr(st, "secrets") else None) or "localhost"
    DB_USER = os.environ.get("DB_USER") or (st.secrets.get("DB_USER") if hasattr(st, "secrets") else None) or "root"
    DB_PASS = os.environ.get("DB_PASS") or (st.secrets.get("DB_PASS") if hasattr(st, "secrets") else None) or ""
    DB_NAME = os.environ.get("DB_NAME") or (st.secrets.get("DB_NAME") if hasattr(st, "secrets") else None) or "cv"
    if globals().get("pymysql"):
        try:
            _db_conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, db=DB_NAME)
            _db_cursor = _db_conn.cursor()
        except Exception as e:
            print("DB connection failed or DB not accessible:", e)
            _db_conn = None
            _db_cursor = None
except Exception as e:
    print("Pymysql import/connection issue:", e)
    _db_conn = None
    _db_cursor = None

# Helper DB insert functions (no-op if DB not connected)
def insert_data(*args, **kwargs):
    if _db_conn and _db_cursor:
        try:
            sec_token, ip_add, host_name, dev_user, os_name_ver, latlong, city, state, country, act_name, act_mail, act_mob, name, email, res_score, timestamp, no_of_pages, reco_field, cand_level, skills, recommended_skills, courses, pdf_name = args
            DB_table_name = 'user_data'
            insert_sql = "insert into " + DB_table_name + """
            values (0,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
            rec_values = (str(sec_token),str(ip_add),host_name,dev_user,os_name_ver,str(latlong),city,state,country,act_name,act_mail,act_mob,name,email,str(res_score),timestamp,str(no_of_pages),reco_field,cand_level,skills,recommended_skills,courses,pdf_name)
            _db_cursor.execute(insert_sql, rec_values)
            _db_conn.commit()
        except Exception as e:
            print("DB insert_data error:", e)
    else:
        print("DB not configured; skipping insert_data.")

def insertf_data(feed_name,feed_email,feed_score,comments,Timestamp):
    if _db_conn and _db_cursor:
        try:
            DBf_table_name = 'user_feedback'
            insertfeed_sql = "insert into " + DBf_table_name + """
            values (0,%s,%s,%s,%s,%s)"""
            rec_values = (feed_name, feed_email, feed_score, comments, Timestamp)
            _db_cursor.execute(insertfeed_sql, rec_values)
            _db_conn.commit()
        except Exception as e:
            print("DB insertf_data error:", e)
    else:
        print("DB not configured; skipping insertf_data.")

# ----------------- Utility helpers -----------------
def get_csv_download_link(df, filename, text):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href

def show_pdf(file_path):
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error("Unable to preview PDF: " + str(e))

def course_recommender(course_list):
    st.subheader("**Courses & Certificates Recommendations 👨‍🎓**")
    random.shuffle(course_list)
    no_of_reco = st.slider('Choose Number of Course Recommendations:', 1, 10, 5)
    rec_course = []
    c = 0
    for c_name, c_link in course_list:
        c += 1
        st.markdown(f"({c}) [{c_name}]({c_link})")
        rec_course.append(c_name)
        if c == no_of_reco:
            break
    return rec_course

# ----------------- Page config -----------------
st.set_page_config(page_title="AI Resume Analyzer", page_icon='./Logo/recommend.png')

# ----------------- Main application -----------------
def run():
    # header / sidebar
    try:
        img = Image.open('./Logo/RESUM.png')
        st.image(img)
    except Exception:
        st.title("AI Resume Analyzer")

    st.sidebar.markdown("# Choose Something...")
    activities = ["User", "Feedback", "About", "Admin"]
    choice = st.sidebar.selectbox("Choose among the given options:", activities)
    link = '<b>Built with 🤍 by <a href="https://dnoobnerd.netlify.app/" style="text-decoration: none; color: #021659;">Deepak Padhi</a></b>'
    st.sidebar.markdown(link, unsafe_allow_html=True)

    # create upload folder if not exists
    os.makedirs("./Uploaded_Resumes", exist_ok=True)

    # Create DB tables if DB connected
    if _db_conn and _db_cursor:
        try:
            cursor = _db_cursor
            cursor.execute("CREATE DATABASE IF NOT EXISTS CV;")
            # create tables (simple - same as before)
            cursor.execute("""CREATE TABLE IF NOT EXISTS user_data (
                                ID INT NOT NULL AUTO_INCREMENT,
                                sec_token varchar(20) NOT NULL,
                                ip_add varchar(50) NULL,
                                host_name varchar(50) NULL,
                                dev_user varchar(50) NULL,
                                os_name_ver varchar(50) NULL,
                                latlong varchar(50) NULL,
                                city varchar(50) NULL,
                                state varchar(50) NULL,
                                country varchar(50) NULL,
                                act_name varchar(50) NOT NULL,
                                act_mail varchar(50) NOT NULL,
                                act_mob varchar(20) NOT NULL,
                                Name varchar(500) NOT NULL,
                                Email_ID VARCHAR(500) NOT NULL,
                                resume_score VARCHAR(8) NOT NULL,
                                Timestamp VARCHAR(50) NOT NULL,
                                Page_no VARCHAR(5) NOT NULL,
                                Predicted_Field BLOB NOT NULL,
                                User_level BLOB NOT NULL,
                                Actual_skills BLOB NOT NULL,
                                Recommended_skills BLOB NOT NULL,
                                Recommended_courses BLOB NOT NULL,
                                pdf_name varchar(50) NOT NULL,
                                PRIMARY KEY (ID)
                            );""")
            cursor.execute("""CREATE TABLE IF NOT EXISTS user_feedback (
                                ID INT NOT NULL AUTO_INCREMENT,
                                feed_name varchar(50) NOT NULL,
                                feed_email VARCHAR(50) NOT NULL,
                                feed_score VARCHAR(5) NOT NULL,
                                comments VARCHAR(100) NULL,
                                Timestamp VARCHAR(50) NOT NULL,
                                PRIMARY KEY (ID)
                            );""")
        except Exception as e:
            print("DB table creation skipped or failed:", e)

    # ----------------- USER flow -----------------
    if choice == 'User':
        # Basic info
        act_name = st.text_input('Name*')
        act_mail = st.text_input('Mail*')
        act_mob  = st.text_input('Mobile Number*')
        sec_token = pysecrets.token_urlsafe(12)

        # host/ip info (safe fallbacks)
        try:
            host_name = socket.gethostname()
        except Exception:
            host_name = "unknown"
        try:
            ip_add = socket.gethostbyname(host_name)
        except Exception:
            ip_add = ""

        try:
            dev_user = os.getlogin()
        except Exception:
            dev_user = os.environ.get("USER") or "unknown"

        os_name_ver = platform.system() + " " + platform.release()

        # geolocation (optional)
        latlong = None
        city = state = country = ""
        try:
            if globals().get("geocoder"):
                g = geocoder.ip('me')
                latlong = g.latlng
            if globals().get("geopy"):
                geolocator = geopy.geocoders.Nominatim(user_agent="http")
                if latlong:
                    try:
                        location = geolocator.reverse(latlong, language='en')
                        address = location.raw.get('address', {})
                        city = address.get('city', '') or address.get('town', '') or address.get('village','')
                        state = address.get('state', '')
                        country = address.get('country', '')
                    except Exception:
                        city = state = country = ""
        except Exception:
            latlong = None
            city = state = country = ""

        # Upload Resume
        st.markdown('''<h5 style='text-align: left; color: #021659;'> Upload Your Resume, And Get Smart Recommendations</h5>''',unsafe_allow_html=True)
        pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])
        if pdf_file is not None:
            with st.spinner('Hang On While We Cook Magic For You...'):
                time.sleep(1)

            # save file server-side for parsing (safe)
            save_image_path = os.path.join('./Uploaded_Resumes', pdf_file.name)
            pdf_name = pdf_file.name
            with open(save_image_path, "wb") as f:
                f.write(pdf_file.getbuffer())

            # preview
            try:
                show_pdf(save_image_path)
            except Exception:
                pass

            # Extract text using unified helper
            try:
                resume_text = extract_text_from_pdf(save_image_path)
            except Exception as e:
                st.error("Failed to extract text from PDF: " + str(e))
                resume_text = ""

            # Parse with pyresparser if available
            resume_data = {}
            if ResumeParser:
                try:
                    parsed = ResumeParser(save_image_path).get_extracted_data()
                    resume_data = parsed or {}
                except Exception as e:
                    print("pyresparser parse error:", e)
                    resume_data = {}
            else:
                resume_data = {}

            # UI: analysis
            if resume_data:
                st.header("**Resume Analysis 🤘**")
                try:
                    st.success("Hello "+ str(resume_data.get('name','')))
                    st.subheader("**Your Basic info 👀**")
                    st.text('Name: ' + str(resume_data.get('name','')))
                    st.text('Email: ' + str(resume_data.get('email','')))
                    st.text('Contact: ' + str(resume_data.get('mobile_number','')))
                    st.text('Degree: '+ str(resume_data.get('degree','')))
                    st.text('Resume pages: '+str(resume_data.get('no_of_pages','')))
                except Exception:
                    pass

                # Estimate level
                cand_level = "Fresher"
                try:
                    no_of_pages = int(resume_data.get('no_of_pages') or 0)
                except Exception:
                    no_of_pages = 0
                # very naive heuristics (kept from original)
                if no_of_pages < 1:
                    cand_level = "NA"
                    st.markdown("<h4 style='text-align: left; color: #d73b5c;'>You are at Fresher level!</h4>", unsafe_allow_html=True)
                elif 'INTERNSHIP' in resume_text.upper():
                    cand_level = "Intermediate"
                    st.markdown("<h4 style='text-align: left; color: #1ed760;'>You are at intermediate level!</h4>", unsafe_allow_html=True)
                elif 'EXPERIENCE' in resume_text.upper():
                    cand_level = "Experienced"
                    st.markdown("<h4 style='text-align: left; color: #fba171;'>You are at experience level!</h4>", unsafe_allow_html=True)
                else:
                    cand_level = "Fresher"
                    st.markdown("<h4 style='text-align: left; color: #fba171;'>You are at Fresher level!!</h4>", unsafe_allow_html=True)

                # skills (use pyresparser skills if available)
                st.subheader("**Skills Recommendation 💡**")
                skills_list = resume_data.get('skills') or []
                keywords = st_tags(label='### Your Current Skills', text='See our skills recommendation below', value=skills_list, key='1')

                # determine recommended skills + course recommendations (kept logic)
                # ... (kept original keyword lists and logic) ...
                ds_keyword = ['tensorflow','keras','pytorch','machine learning','deep learning','flask','streamlit']
                web_keyword = ['react', 'django', 'node js', 'react js', 'php', 'laravel', 'magento', 'wordpress','javascript', 'angular js', 'c#', 'asp.net', 'flask']
                android_keyword = ['android','android development','flutter','kotlin','xml','kivy']
                ios_keyword = ['ios','ios development','swift','cocoa','cocoa touch','xcode']
                uiux_keyword = ['ux','adobe xd','figma','zeplin','balsamiq','ui','prototyping','wireframes','adobe photoshop','photoshop','illustrator']
                n_any = ['english','communication','writing', 'microsoft office', 'leadership','customer management', 'social media']

                recommended_skills = []
                reco_field = ''
                rec_course = ''

                for i in skills_list:
                    if i is None: 
                        continue
                    il = str(i).lower()
                    if il in ds_keyword:
                        reco_field = 'Data Science'
                        st.success("** Our analysis says you are looking for Data Science Jobs.**")
                        recommended_skills = ['Data Visualization','Predictive Analysis','Statistical Modeling','Data Mining','Clustering & Classification','Data Analytics','Quantitative Analysis','Web Scraping','ML Algorithms','Keras','Pytorch','Probability','Scikit-learn','Tensorflow','Flask','Streamlit']
                        st_tags(label='### Recommended skills for you.', text='Recommended skills generated from System', value=recommended_skills, key='2')
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>Adding these skills to resume will boost🚀 the chances of getting a Job</h5>", unsafe_allow_html=True)
                        rec_course = course_recommender(ds_course)
                        break
                    elif il in web_keyword:
                        reco_field = 'Web Development'
                        st.success("** Our analysis says you are looking for Web Development Jobs **")
                        recommended_skills = ['React','Django','Node JS','React JS','PHP','Laravel','Magento','Wordpress','Javascript','Angular JS','C#','Flask','SDK']
                        st_tags(label='### Recommended skills for you.', text='Recommended skills generated from System', value=recommended_skills, key='3')
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>Adding these skills to resume will boost🚀 the chances of getting a Job💼</h5>", unsafe_allow_html=True)
                        rec_course = course_recommender(web_course)
                        break
                    elif il in android_keyword:
                        reco_field = 'Android Development'
                        st.success("** Our analysis says you are looking for Android App Development Jobs **")
                        recommended_skills = ['Android','Android development','Flutter','Kotlin','XML','Java','Kivy','GIT','SDK','SQLite']
                        st_tags(label='### Recommended skills for you.', text='Recommended skills generated from System', value=recommended_skills, key='4')
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>Adding these skills to resume will boost🚀 the chances of getting a Job💼</h5>", unsafe_allow_html=True)
                        rec_course = course_recommender(android_course)
                        break
                    elif il in ios_keyword:
                        reco_field = 'IOS Development'
                        st.success("** Our analysis says you are looking for IOS App Development Jobs **")
                        recommended_skills = ['IOS','IOS Development','Swift','Cocoa','Cocoa Touch','Xcode','Objective-C','SQLite','Plist','StoreKit','UI-Kit','AV Foundation','Auto-Layout']
                        st_tags(label='### Recommended skills for you.', text='Recommended skills generated from System', value=recommended_skills, key='5')
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>Adding these skills to resume will boost🚀 the chances of getting a Job💼</h5>", unsafe_allow_html=True)
                        rec_course = course_recommender(ios_course)
                        break
                    elif il in uiux_keyword:
                        reco_field = 'UI-UX Development'
                        st.success("** Our analysis says you are looking for UI-UX Development Jobs **")
                        recommended_skills = ['UI','User Experience','Adobe XD','Figma','Zeplin','Balsamiq','Prototyping','Wireframes','Storyframes','Adobe Photoshop','Editing','Illustrator','After Effects','Premier Pro','Indesign']
                        st_tags(label='### Recommended skills for you.', text='Recommended skills generated from System', value=recommended_skills, key='6')
                        st.markdown("<h5 style='text-align: left; color: #1ed760;'>Adding these skills to resume will boost🚀 the chances of getting a Job💼</h5>", unsafe_allow_html=True)
                        rec_course = course_recommender(uiux_course)
                        break
                    elif il in n_any:
                        reco_field = 'NA'
                        st.warning("** Currently our tool only predicts and recommends for Data Science, Web, Android, IOS and UI/UX Development**")
                        recommended_skills = ['No Recommendations']
                        st_tags(label='### Recommended skills for you.', text='Currently No Recommendations', value=recommended_skills, key='7')
                        st.markdown("<h5 style='text-align: left; color: #092851;'>Maybe Available in Future Updates</h5>", unsafe_allow_html=True)
                        rec_course = "Sorry! Not Available for this Field"
                        break

                # Resume scoring (kept logic but simplified)
                st.subheader("**Resume Tips & Ideas 🥂**")
                resume_score = 0
                text_upper = resume_text.upper() if isinstance(resume_text, str) else ""
                if "OBJECTIVE" in text_upper or "SUMMARY" in text_upper:
                    resume_score += 6
                    st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Objective/Summary</h5>", unsafe_allow_html=True)
                else:
                    st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add your career objective, it will give your career intention to the Recruiters.</h5>", unsafe_allow_html=True)

                if "EDUCATION" in text_upper or "SCHOOL" in text_upper or "COLLEGE" in text_upper:
                    resume_score += 12
                    st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Education Details</h5>", unsafe_allow_html=True)
                else:
                    st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Education. It will give Your Qualification level to the recruiter</h5>", unsafe_allow_html=True)

                if "EXPERIENCE" in text_upper:
                    resume_score += 16
                    st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Experience</h5>", unsafe_allow_html=True)
                else:
                    st.markdown("<h5 style='text-align: left; color: #000000;'>[-] Please add Experience. It will help you to stand out from crowd</h5>", unsafe_allow_html=True)

                if "INTERNSHIP" in text_upper or "INTERNSHIPS" in text_upper:
                    resume_score += 6
                    st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Internships</h5>", unsafe_allow_html=True)

                if "SKILL" in text_upper or "SKILLS" in text_upper:
                    resume_score += 7
                    st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added Skills</h5>", unsafe_allow_html=True)

                if "PROJECT" in text_upper or "PROJECTS" in text_upper:
                    resume_score += 19
                    st.markdown("<h5 style='text-align: left; color: #1ed760;'>[+] Awesome! You have added your Projects</h5>", unsafe_allow_html=True)

                # Score progress bar
                st.subheader("**Resume Score 📝**")
                my_bar = st.progress(0)
                for percent_complete in range(min(resume_score, 100)):
                    time.sleep(0.01)
                    my_bar.progress(percent_complete + 1)
                st.success(f'** Your Resume Writing Score: {resume_score} **')
                st.warning("** Note: This score is calculated based on the content that you have in your Resume. **")

                # timestamp and DB insert
                ts = time.time()
                cur_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                cur_time = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
                timestamp = str(cur_date + '_' + cur_time)

                insert_data(str(sec_token), str(ip_add), host_name, dev_user, os_name_ver, latlong, city, state, country, act_name, act_mail, act_mob, resume_data.get('name',''), resume_data.get('email',''), str(resume_score), timestamp, str(resume_data.get('no_of_pages','')), reco_field, cand_level, str(resume_data.get('skills','')), str(recommended_skills), str(rec_course), pdf_name)

                # Bonus videos
                try:
                    st.header("**Bonus Video for Resume Writing Tips💡**")
                    resume_vid = random.choice(resume_videos) if resume_videos else None
                    if resume_vid:
                        st.video(resume_vid)
                except Exception:
                    pass
                try:
                    st.header("**Bonus Video for Interview Tips💡**")
                    interview_vid = random.choice(interview_videos) if interview_videos else None
                    if interview_vid:
                        st.video(interview_vid)
                except Exception:
                    pass

                st.balloons()
            else:
                st.error('Something went wrong while parsing resume. If parsing fails, try a different resume or paste text into the AI suggestions area.')

    # ----------------- FEEDBACK flow -----------------
    elif choice == 'Feedback':
        ts = time.time()
        cur_date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        cur_time = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S')
        timestamp = str(cur_date+'_'+cur_time)

        with st.form("my_form"):
            st.write("Feedback form")
            feed_name = st.text_input('Name')
            feed_email = st.text_input('Email')
            feed_score = st.slider('Rate Us From 1 - 5', 1, 5)
            comments = st.text_input('Comments')
            Timestamp = timestamp
            submitted = st.form_submit_button("Submit")
            if submitted:
                insertf_data(feed_name, feed_email, feed_score, comments, Timestamp)
                st.success("Thanks! Your Feedback was recorded.")
                st.balloons()

        # show past feedback if DB is available
        if _db_conn and _db_cursor:
            try:
                plotfeed_data = pd.read_sql('select * from user_feedback', _db_conn)
                labels = plotfeed_data.feed_score.unique()
                values = plotfeed_data.feed_score.value_counts()
                if px:
                    fig = px.pie(values=values, names=labels, title="Chart of User Rating Score From 1 - 5", color_discrete_sequence=px.colors.sequential.Aggrnyl)
                    st.plotly_chart(fig)
                else:
                    st.write("Plotly not available to show charts.")
                cursor = _db_cursor
                cursor.execute('select feed_name, comments from user_feedback')
                plfeed_cmt_data = cursor.fetchall()
                st.subheader("**User Comment's**")
                dff = pd.DataFrame(plfeed_cmt_data, columns=['User', 'Comment'])
                st.dataframe(dff, width=1000)
            except Exception as e:
                st.write("Feedback data unavailable:", e)

    # ----------------- ABOUT flow -----------------
    elif choice == 'About':
        st.subheader("**About The Tool - AI RESUME ANALYZER**")
        st.markdown("""
        <p>A tool which parses information from a resume using natural language processing and finds the keywords, cluster them onto sectors based on their keywords. And lastly show recommendations, predictions, analytics to the applicant based on keyword matching.</p>
        <p><b>How to use it:</b> Upload your resume as PDF. Use Feedback to give feedback. Admin can login to view DB analytics.</p>
        <p>Built with 🤍 by <a href="https://dnoobnerd.netlify.app/">Deepak Padhi</a>.</p>
        """, unsafe_allow_html=True)

    # ----------------- ADMIN flow -----------------
    else:
        st.success('Welcome to Admin Side')
        ad_user = st.text_input("Username")
        ad_password = st.text_input("Password", type='password')

        if st.button('Login'):
            if ad_user == 'admin' and ad_password == 'admin@resume-analyzer':
                # fetch user_data if available
                if _db_conn and _db_cursor:
                    try:
                        cursor = _db_cursor
                        cursor.execute('''SELECT ID, ip_add, resume_score, convert(Predicted_Field using utf8), convert(User_level using utf8), city, state, country from user_data''')
                        datanalys = cursor.fetchall()
                        plot_data = pd.DataFrame(datanalys, columns=['Idt', 'IP_add', 'resume_score', 'Predicted_Field', 'User_Level', 'City', 'State', 'Country'])
                        st.success(f"Welcome Deepak ! Total {plot_data.Idt.count()} User's Have Used Our Tool : )")
                    except Exception as e:
                        st.write("Unable to fetch admin analytics:", e)

                    try:
                        cursor.execute('''SELECT ID, sec_token, ip_add, act_name, act_mail, act_mob, convert(Predicted_Field using utf8), Timestamp, Name, Email_ID, resume_score, Page_no, pdf_name, convert(User_level using utf8), convert(Actual_skills using utf8), convert(Recommended_skills using utf8), convert(Recommended_courses using utf8), city, state, country, latlong, os_name_ver, host_name, dev_user from user_data''')
                        data = cursor.fetchall()
                        df = pd.DataFrame(data, columns=['ID', 'Token', 'IP Address', 'Name', 'Mail', 'Mobile Number', 'Predicted Field', 'Timestamp',
                                                         'Predicted Name', 'Predicted Mail', 'Resume Score', 'Total Page',  'File Name',
                                                         'User Level', 'Actual Skills', 'Recommended Skills', 'Recommended Course',
                                                         'City', 'State', 'Country', 'Lat Long', 'Server OS', 'Server Name', 'Server User',])
                        st.dataframe(df)
                        st.markdown(get_csv_download_link(df,'User_Data.csv','Download Report'), unsafe_allow_html=True)
                    except Exception as e:
                        st.write("Unable to fetch full user data for admin:", e)

                    # show pie charts (if plotly available)
                    try:
                        cursor.execute('select * from user_feedback')
                        plotfeed_data = pd.read_sql('select * from user_feedback', _db_conn)
                        labels = plotfeed_data.feed_score.unique()
                        values = plotfeed_data.feed_score.value_counts()
                        if px:
                            fig = px.pie(values=values, names=labels, title="Chart of User Rating Score From 1 - 5", color_discrete_sequence=px.colors.sequential.Aggrnyl)
                            st.plotly_chart(fig)
                    except Exception as e:
                        st.write("Admin charts unavailable:", e)
                else:
                    st.write("DB not configured - admin analytics disabled.")
            else:
                st.error("Wrong ID & Password Provided")

    # ----------------- AI Suggestions Section -----------------
    try:
        from ai_client import ask_ai
    except Exception as _e:
        def ask_ai(prompt: str):
            return "AI suggestions not configured. Add AI_API_KEY to Streamlit secrets to enable."

    st.markdown("---")
    st.subheader("AI-powered Suggestions")

    _possible_keys = ["resume_text", "text", "doc_text", "parsed_text", "resume_str", "extracted_text"]
    resume_text = None

    # 1) Check globals
    for k in _possible_keys:
        if k in globals() and globals().get(k):
            resume_text = globals().get(k)
            break

    # 2) Check session_state
    if not resume_text:
        for k in _possible_keys:
            if st.session_state.get(k):
                resume_text = st.session_state.get(k)
                break

    # 3) Fallback: let user paste text
    if not resume_text:
        st.info("No parsed resume text detected. Paste resume text here to get AI suggestions.")
        resume_text = st.text_area("Paste resume text (optional)", value="", height=200)

    if st.button("Get AI suggestions"):
        with st.spinner("Generating AI suggestions..."):
            try:
                prompt = (
                    "You are an expert career coach. Analyze this resume and provide:\n"
                    "1) Top strengths\n"
                    "2) Weaknesses or missing items\n"
                    "3) Key ATS keywords to add\n"
                    "4) Improvements to professional summary\n\n"
                    f"Resume:\n{resume_text}"
                )
                ai_out = ask_ai(prompt)
                st.success("AI Suggestions")
                st.write(ai_out)
            except Exception as e:
                st.error(f"AI error: {e}")

# run app
if __name__ == "__main__":
    run()
