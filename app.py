from flask import Flask, render_template, request, redirect, Response, send_file
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

UPLOAD_FOLDER = "uploads"
CERT_FOLDER = "certificates"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CERT_FOLDER, exist_ok=True)

# ================= DATABASE (SUPABASE POSTGRES) ================= #
import psycopg2

def get_db():
    return psycopg2.connect(
        "postgresql://postgres.rngdjfuywdsyxrhbyvxn:Arasu%401011%23vinay@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres",
        sslmode="require"
    )
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
"""

        msg = MIMEText(msg_text)
        msg['Subject'] = "Registration Received"
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
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

    content = []

    content.append(Paragraph("CERTIFICATE OF ACHIEVEMENT", styles["Title"]))
    content.append(Spacer(1, 20))

    content.append(Paragraph("This is to certify that", styles["Normal"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph(f"<b>{name}</b>", styles["Heading2"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph("has participated in", styles["Normal"]))
    content.append(Spacer(1, 10))

    content.append(Paragraph("Arasutech Global Handwriting Contest 2026", styles["Normal"]))
    content.append(Spacer(1, 30))

    content.append(Paragraph("Authorized Signature", styles["Normal"]))

    doc.build(content)
    return file_path

# ================= EMAIL CERTIFICATE ================= #

def send_certificate(email, name, file_path):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    msg['Subject'] = "Your Certificate"

    body = f"Dear {name},\n\nPlease find your certificate attached."
    msg.attach(MIMEText(body, 'plain'))

    with open(file_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={name}.pdf")
        msg.attach(part)

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)

# ================= ROUTES ================= #

@app.route('/')
def home():
    return render_template("home.html")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        grade = request.form['grade']
        school = request.form['school']
        email = request.form['email']
        file = request.files['file']

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

# ================= ADMIN ================= #

@app.route('/admin')
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

# ================= EXPORT ================= #

@app.route('/download')
def download():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT name, grade, school, email FROM participants")
    rows = c.fetchall()
    conn.close()

    df = pd.DataFrame(rows, columns=["Name", "Grade", "School", "Email"])
    file_path = "registrations.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# ================= GENERATE CERT ================= #

@app.route('/generate/<int:id>')
def generate(id):
    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT name, email FROM participants WHERE id=%s", (id,))
    user = c.fetchone()

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

    return f"Certificate sent to {name}"

# ================= RUN ================= #

if __name__ == "__main__":
    app.run(debug=True)
