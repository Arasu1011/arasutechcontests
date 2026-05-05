from flask import Flask, render_template, request, redirect
import sqlite3
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
CERT_FOLDER = 'certificates'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ✅ Create folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CERT_FOLDER, exist_ok=True)

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            grade TEXT,
            school TEXT,
            email TEXT,
            filename TEXT,
            cert_file TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ---------------- EMAIL ---------------- #

import threading
import os

SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

def send_email_async(to_email, name):
    try:
        message = f"""
Dear {name},

🎉 Congratulations!

You have successfully registered for Arasutechcontests.

Please complete your payment to confirm your participation.

Regards,
Arasutechcontests Team
"""

        msg = MIMEText(message)
        msg['Subject'] = "Registration Successful - Arasutechcontests"
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email

        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print("Email failed:", e)


def send_email(to_email, name):
    threading.Thread(target=send_email_async, args=(to_email, name)).start()

# ---------------- CERTIFICATE ---------------- #

def generate_certificate(name):
    file_path = os.path.join(CERT_FOLDER, f"{name}.pdf")

    doc = SimpleDocTemplate(file_path)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("CERTIFICATE OF ACHIEVEMENT", styles['Title']))
    content.append(Spacer(1, 20))

    content.append(Paragraph("This is to certify that", styles['Normal']))
    content.append(Spacer(1, 10))

    content.append(Paragraph(f"<b>{name}</b>", styles['Heading2']))
    content.append(Spacer(1, 10))

    content.append(Paragraph("has successfully participated in", styles['Normal']))
    content.append(Spacer(1, 10))

    content.append(Paragraph("Arasutech Global Handwriting Competition 2026", styles['Normal']))
    content.append(Spacer(1, 30))

    content.append(Paragraph("Authorized Signature", styles['Normal']))

    doc.build(content)

    return file_path

# ---------------- SEND CERTIFICATE ---------------- #

def send_certificate(to_email, name, file_path):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = "Your Certificate - Arasutechcontests"

    body = f"Dear {name},\n\nPlease find your certificate attached.\n\nRegards,\nArasutechcontests Team"
    msg.attach(MIMEText(body, 'plain'))

    with open(file_path, "rb") as f:
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{name}.pdf"')
        msg.attach(part)

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)

# ---------------- ROUTES ---------------- #

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/competitions')
def competitions():
    return render_template('competitions.html')

@app.route('/about')
def about():
    return render_template('about.html')

# ---------------- REGISTER ---------------- #

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

        # Save to DB
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute(
            "INSERT INTO participants (name, grade, school, email, filename, cert_file) VALUES (?, ?, ?, ?, ?, ?)",
            (name, grade, school, email, filename, "")
        )
        conn.commit()
        conn.close()

        # Send email
        send_email(email, name)

        # 🔥 Redirect to Payment Link (replace with your Razorpay link)
        payment_link = f"https://rzp.io/rzp/UcnDezR1"
        return redirect(payment_link)

    return render_template('register.html')

# ---------------- ADMIN ---------------- #

@app.route('/admin')
def admin():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM participants")
    data = c.fetchall()
    conn.close()

    return render_template('admin.html', data=data)

# ---------------- GENERATE CERTIFICATE ---------------- #

@app.route('/generate/<int:id>')
def generate(id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT name, email FROM participants WHERE id=?", (id,))
    user = c.fetchone()

    name, email = user

    cert_path = generate_certificate(name)

    # update DB
    c.execute("UPDATE participants SET cert_file=? WHERE id=?", (cert_path, id))
    conn.commit()
    conn.close()

    # send certificate email
    send_certificate(email, name, cert_path)

    return f"Certificate generated and sent to {name}"

# ---------------- RUN ---------------- #

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
