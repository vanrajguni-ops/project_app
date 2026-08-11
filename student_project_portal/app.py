import os
import io
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy

# PDF Generation imports
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = "dev_secret_key_student_portal"

# Database Setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(BASE_DIR, 'portal.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# -------------------------------------------------------------
# Database Models
# -------------------------------------------------------------
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='student') # 'student' or 'faculty'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    student_name = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default="Pending") # Pending, Approved, Rejected
    submitted_on = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# -------------------------------------------------------------
# Routes
# -------------------------------------------------------------

# Login / Home Page
@app.route("/", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect_by_role(session.get("role"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Kripya Username aur Password dono bharein!", "warning")
            return redirect(url_for("login"))

        user = User.query.filter_by(username=username).first()

        if user and user.password == password:
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            return redirect_by_role(user.role)
        
        flash("Galat Username ya Password! Phir se try karein.", "danger")

    return render_template("login.html")

# Register Page
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "student")

        if not username or not password:
            flash("Sabhi fields bharna zaroori hai!", "warning")
            return redirect(url_for("register"))

        if len(username) < 3:
            flash("Username kam se kam 3 letters ka hona chahiye.", "warning")
            return redirect(url_for("register"))

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Ye Username pehle se liya hua hai. Dusra try karein!", "warning")
            return redirect(url_for("register"))

        new_user = User(username=username, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()

        flash("Account successfully ban gaya! Ab login karein.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# Student Dashboard
@app.route("/student", methods=["GET", "POST"])
def student_dashboard():
    if session.get("role") != "student":
        flash("Pehle Student account se Login karein!", "warning")
        return redirect(url_for("login"))

    current_user = session.get("username")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if title and description:
            new_project = Project(title=title, description=description, student_name=current_user)
            db.session.add(new_project)
            db.session.commit()
            flash("Aapka Project proposal submit ho gaya hai!", "success")
            return redirect(url_for("student_dashboard"))
        else:
            flash("Title aur Description dono bharna zaroori hai!", "danger")

    projects = Project.query.filter_by(student_name=current_user).order_by(Project.submitted_on.desc()).all()
    return render_template("student_dashboard.html", projects=projects, student=current_user)

# Faculty Dashboard
@app.route("/faculty")
def faculty_dashboard():
    if session.get("role") != "faculty":
        flash("Pehle Faculty account se Login karein!", "warning")
        return redirect(url_for("login"))

    projects = Project.query.order_by(Project.submitted_on.desc()).all()
    return render_template("faculty_dashboard.html", projects=projects)

# Status Update Route
@app.route("/update_status/<int:project_id>/<string:status>")
def update_status(project_id, status):
    if session.get("role") == "faculty":
        project = Project.query.get_or_404(project_id)
        if status in ["Approved", "Rejected"]:
            project.status = status
            db.session.commit()
            flash(f"Project #{project.id} ko {status} kar diya gaya hai.", "info")
    return redirect(url_for("faculty_dashboard"))

# PDF Download Route for Faculty
@app.route("/download_pdf")
def download_pdf():
    if session.get("role") != "faculty":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("login"))

    projects = Project.query.order_by(Project.submitted_on.desc()).all()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor("#1e293b"),
        alignment=1,
        spaceAfter=15
    )
    
    elements.append(Paragraph("Student Project Report Summary", title_style))
    elements.append(Spacer(1, 10))

    data = [["ID", "Student Name", "Project Title", "Status"]]
    for p in projects:
        data.append([str(p.id), p.student_name, p.title, p.status])

    table = Table(data, colWidths=[40, 130, 260, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2563eb")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    elements.append(table)
    doc.build(elements)

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name="Project_Report_Summary.pdf",
        mimetype="application/pdf"
    )

# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("Aap successfully Logout ho gaye hain.", "info")
    return redirect(url_for("login"))

def redirect_by_role(role):
    if role == "student":
        return redirect(url_for("student_dashboard"))
    elif role == "faculty":
        return redirect(url_for("faculty_dashboard"))
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)

    # Database Setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Local testing ke liye SQLite, Online deploy hone par Render PostgreSQL use hoga
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'portal.db'))
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False