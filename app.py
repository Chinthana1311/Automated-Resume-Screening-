import os
import re
import sqlite3
import uuid
import smtplib

from flask import Flask, render_template, request, redirect, send_from_directory, session
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "secret123"

# -------- UPLOAD CONFIG --------
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------- EMAIL CONFIG --------
SENDER_EMAIL = "chinthana10ap@gmail.com"
SENDER_PASSWORD = "tzesnljdpdkurlru"

COMPANY_NAME = "ABC Technologies"
JOB_TITLE = "Software Developer Intern"

# -------- DATABASE --------
def get_db():
    return sqlite3.connect("database.db")


def create_tables():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS student(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            education TEXT,
            year TEXT,
            resume TEXT,
            shortlisted INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS skills(
            student_id INTEGER,
            skill TEXT
        )
    """)

    conn.commit()
    conn.close()


create_tables()

# -------- HOME --------
@app.route("/")
def index():
    return render_template("index.html")

# -------- RECRUITER LOGIN --------
@app.route("/recruiter", methods=["GET", "POST"])
def recruiter_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin":
            conn = get_db()
            cur = conn.cursor()
            cur.execute("UPDATE student SET shortlisted = 0")
            conn.commit()
            conn.close()

            session['skill_input'] = ''
            return redirect("/dashboard")

    return render_template("recruiter_login.html")

# -------- DASHBOARD --------
@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    results = []
    message = ""
    count = 0
    skill_input = ""

    if request.method == "POST":
        skill_input = request.form["skill"].lower()
        session['skill_input'] = skill_input
    else:
        skill_input = request.args.get('skill', session.get('skill_input', ''))
        if skill_input:
            session['skill_input'] = skill_input

    if skill_input:
        skills = [s.strip() for s in skill_input.split(",")]
        placeholders = ",".join(["?"] * len(skills))

        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT DISTINCT student.id, student.name, student.email,
                            student.resume, student.shortlisted
            FROM student
            JOIN skills ON student.id = skills.student_id
            WHERE skills.skill IN ({placeholders})
        """, skills)

        results = cur.fetchall()
        conn.close()

        count = len(results)
        if count == 0:
            message = "No candidates matched for this skill."

    return render_template(
        "recruiter_dashboard.html",
        results=results,
        message=message,
        count=count
    )

# -------- MOVE TO SHORTLIST --------
@app.route("/shortlist_move/<int:id>")
def shortlist_move(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE student SET shortlisted = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect("/dashboard#results")

# -------- UNDO SHORTLIST --------
@app.route("/undo_shortlist/<int:id>")
def undo_shortlist(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE student SET shortlisted = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect("/dashboard#results")

# -------- SHORTLIST PAGE --------
@app.route("/shortlist")
def shortlist():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, email, resume
        FROM student
        WHERE shortlisted = 1
    """)
    data = cur.fetchall()
    conn.close()

    return render_template("shortlist.html", data=data)

# -------- SEND MAIL --------
@app.route("/send_mail", methods=["POST"])
def send_mail():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT name, email FROM student WHERE shortlisted = 1")
    students = cur.fetchall()
    conn.close()

    for student in students:
        name = student[0]
        email = student[1]

        mail_body = f"""
Dear {name},

We are pleased to inform you that you have been shortlisted for the next stage of the selection process for the position of {JOB_TITLE} at {COMPANY_NAME}.

Your profile has been reviewed, and we found your qualifications and skills to be a strong match for the role. Further details regarding the next steps, including the interview schedule, will be shared with you shortly.

Congratulations on being shortlisted. We wish you success in the upcoming process.

If you have any queries, feel free to contact us.

Best Regards,
Recruitment Team
{COMPANY_NAME}
"""

        msg = MIMEText(mail_body)
        msg["Subject"] = f"Shortlisted for {JOB_TITLE} - {COMPANY_NAME}"
        msg["From"] = SENDER_EMAIL
        msg["To"] = email

        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
        except Exception as e:
            print("Error sending mail:", e)

    return "Emails sent successfully!"

# -------- STUDENT REGISTER --------
@app.route("/student", methods=["GET", "POST"])
def student_register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        edu = request.form["education"]
        year = request.form["year"]
        resume = request.files["resume"]

        filename = str(uuid.uuid4()) + "_" + secure_filename(resume.filename)
        path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        resume.save(path)

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO student(name, email, education, year, resume)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, edu, year, filename))

        sid = cur.lastrowid

        reader = PdfReader(path)
        text = ""
        for page in reader.pages:
            if page.extract_text():
                text += page.extract_text().lower()

        words = set(re.sub(r"[^a-z\s]", " ", text).split())

        skills = {
            "python", "linux", "frontend", "backend", "ui", "ux",
            "uiux", "cpp", "devops", "networking",
            "java", "sql", "html", "css", "javascript", "flask"
        }

        for w in words:
            if w in skills:
                cur.execute(
                    "INSERT INTO skills VALUES (?, ?)",
                    (sid, w)
                )

        conn.commit()
        conn.close()

        return "Uploaded Successfully!"

    return render_template("student_register.html")

# -------- DOWNLOAD RESUME --------
@app.route("/uploads/<filename>")
def download(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# -------- RUN --------
if __name__ == "__main__":
    app.run(debug=True)
