from flask import Flask, render_template, request, redirect, send_file
import os
import psycopg2
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import pandas as pd

app = Flask(__name__)

UPLOAD_FOLDER = "/tmp/uploads"
CERT_FOLDER = "/tmp/certificates"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CERT_FOLDER, exist_ok=True)

# ================= DATABASE ================= #

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            id SERIAL PRIMARY KEY,
            name TEXT,
            grade TEXT,
            school TEXT,
            email TEXT,
            filename TEXT,
            cert_file TEXT,
            cert_status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()

# ================= EMAIL ================= #

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def send_email_async(to_email, name):
    try:
        msg_text = f"""
Dear {name},

🎉 Registration received successfully.

Please complete payment to confirm participation.

Regards,
Arasutech Global Team
Email: arasutechcontests@gmail.com
Phone: 9092196653
"""

        msg = MIMEText(msg_text)
        msg["Subject"] = "Registration Received - Arasutech Global"
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print("Email error:", e)


def send_email(to_email, name):
    threading.Thread(target=send_email_async, args=(to_email, name)).start()

# ================= CERTIFICATE ================= #

def generate_certificate(name):
    file_path = os.path.join(CERT_FOLDER, f"{name}.pdf")

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = [
        Paragraph("CERTIFICATE OF ACHIEVEMENT", styles["Title"]),
        Spacer(1, 20),
        Paragraph("This is to certify that", styles["Normal"]),
        Spacer(1, 10),
        Paragraph(f"<b>{name}</b>", styles["Heading2"]),
        Spacer(1, 10),
        Paragraph("has participated in", styles["Normal"]),
        Spacer(1, 10),
        Paragraph("Arasutech Global Competition 2026", styles["Normal"]),
        Spacer(1, 30),
        Paragraph("Authorized Signature", styles["Normal"]),
    ]

    doc.build(content)
    return file_path


def send_certificate(email, name, file_path):
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = email
        msg["Subject"] = "Your Certificate - Arasutech Global"

        body = f"Dear {name},\n\nPlease find your certificate attached.\n\nRegards,\nArasutech Global Team"
        msg.attach(MIMEText(body, "plain"))

        with open(file_path, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={name}.pdf")
            msg.attach(part)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print("Certificate email error:", e)

# ================= ROUTES ================= #

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/competitions")
def competitions():
    return render_template("competitions.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        grade = request.form.get("grade")
        school = request.form.get("school")
        email = request.form.get("email")
        file = request.files.get("file")

        filename = ""

        if file and file.filename:
            filename = file.filename
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

        conn = get_db()
        c = conn.cursor()

        c.execute("""
            INSERT INTO participants (name, grade, school, email, filename, cert_file)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, grade, school, email, filename, ""))

        conn.commit()
        conn.close()

        send_email(email, name)

        return redirect("https://rzp.io/rzp/spGbyfRa")

    return render_template("register.html")


@app.route("/admin")
def admin():
    key = request.args.get("key")

    if key != "arasutech@2026":
        return "Unauthorized"

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM participants ORDER BY id DESC")
    data = c.fetchall()
    conn.close()

    return render_template("admin.html", data=data)


@app.route("/download")
def download():
    key = request.args.get("key")

    if key != "arasutech@2026":
        return "Unauthorized"

    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, grade, school, email, filename, cert_status, created_at FROM participants")
    rows = c.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=[
        "Name", "Grade", "School", "Email", "File", "Certificate Status", "Registered At"
    ])

    file_path = "/tmp/registrations.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)


@app.route("/generate/<int:id>")
def generate(id):
    key = request.args.get("key")

    if key != "arasutech@2026":
        return "Unauthorized"

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT name, email FROM participants WHERE id=%s", (id,))
    user = c.fetchone()

    if not user:
        conn.close()
        return "User not found"

    name, email = user

    cert_path = generate_certificate(name)

    c.execute("""
        UPDATE participants
        SET cert_file=%s, cert_status='generated'
        WHERE id=%s
    """, (cert_path, id))

    conn.commit()
    conn.close()

    send_certificate(email, name, cert_path)

    return f"Certificate generated and sent to {name}"


@app.route("/health")
def health():
    return "OK"


# ================= RUN ================= #

if __name__ == "__main__":
    app.run(debug=True)
