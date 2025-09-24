import os
import json
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
import requests
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors

# Attempt to import gradient support from ReportLab.  Older versions of
# ReportLab may not provide LinearGradient, Drawing or renderPDF in the
# graphics package.  If the import fails we fall back to drawing
# simple coloured lines instead of gradients.
try:
    from reportlab.graphics.shapes import Drawing, Rect, LinearGradient
    from reportlab.graphics import renderPDF

    GRADIENT_SUPPORTED = True
except Exception:
    GRADIENT_SUPPORTED = False

"""
Flask‑based backend for a resume builder application.  Clients send resume
data as JSON to `/api/generate`, the server optionally corrects grammar
and spelling via LanguageTool, generates a PDF using ReportLab, stores
the record locally and returns a reference to the PDF.  The app also
exposes endpoints to list and download previously generated resumes.

To enable grammar correction, create a `.env` file in the project root
and define LT_USERNAME and LT_API_KEY with your LanguageTool credentials:contentReference[oaicite:0]{index=0}.
Without these variables the `correct_text` function returns the original
text.  Free usage of LanguageTool imposes request and character limits:contentReference[oaicite:1]{index=1}.
"""

# Load environment variables from .env if present
load_dotenv()
LT_USERNAME = os.getenv("LT_USERNAME")
LT_API_KEY = os.getenv("LT_API_KEY")

app = Flask(__name__, static_folder="static", template_folder="templates")

# Data directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RESUME_DIR = os.path.join(DATA_DIR, "resumes")
os.makedirs(RESUME_DIR, exist_ok=True)


# Helpers to load and save the database
def load_database():
    db_path = os.path.join(DATA_DIR, "resumes.json")
    if os.path.exists(db_path):
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return []


def save_database(entries):
    with open(os.path.join(DATA_DIR, "resumes.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


# Grammar correction using LanguageTool
def correct_text(text: str) -> str:
    if not text or not isinstance(text, str) or not text.strip():
        return text
    url = "https://api.languagetoolplus.com/v2/check"
    data = {"text": text, "language": "auto"}
    if LT_USERNAME and LT_API_KEY:
        data["username"] = LT_USERNAME
        data["apiKey"] = LT_API_KEY
    try:
        response = requests.post(url, data=data, timeout=10)
        if response.status_code != 200:
            return text
        result = response.json()
        matches = result.get("matches", [])
        corrected = text
        # Sort matches by offset descending to avoid shifting positions
        for match in sorted(matches, key=lambda m: m["offset"], reverse=True):
            replacements = match.get("replacements", [])
            if replacements:
                replacement = replacements[0].get("value", "")
                start, end = match["offset"], match["offset"] + match["length"]
                corrected = corrected[:start] + replacement + corrected[end:]
        return corrected
    except Exception:
        return text


# Recursively correct every string in the resume
def correct_resume(data):
    if isinstance(data, dict):
        return {k: correct_resume(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [correct_resume(item) for item in data]
    elif isinstance(data, str):
        return correct_text(data)
    return data


def generate_pdf(resume, filepath):
    """
    Generate a polished resume PDF.  Headings are black, section titles
    have a gradient line drawn immediately beneath them, and extra
    spacing dynamically adjusts to content length.
    """
    c = canvas.Canvas(filepath, pagesize=letter)
    _, height = letter
    y = height - 40

    # Colours: headings black, body dark grey, contacts lighter grey
    heading_color = colors.black
    body_color = colors.Color(0.2, 0.2, 0.2)
    contact_color = colors.Color(0.35, 0.35, 0.35)

    # Name at the top
    name = resume.get("personal", {}).get("name", "Resume")
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(heading_color)
    c.drawString(50, y, name)
    y -= 28

    # Contact details
    personal = resume.get("personal", {})
    contacts = []
    if personal.get("email"):
        contacts.append(f"Email: {personal['email']}")
    if personal.get("phone"):
        contacts.append(f"Phone: {personal['phone']}")
    if personal.get("address"):
        contacts.append(f"Address: {personal['address']}")
    c.setFont("Helvetica", 10)
    c.setFillColor(contact_color)
    for line in contacts:
        c.drawString(50, y, line)
        y -= 14
    y -= 12

    # Helper to draw headings with close gradient lines
    def add_section_header(title):
        nonlocal y
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(heading_color)
        c.drawString(50, y, title)
        y -= 4  # small gap after heading
        y -= draw_gradient_line(c, y)  # draw gradient immediately below
        y -= 8  # space before content

    # Summary section
    summary = resume.get("summary", "")
    if summary:
        add_section_header("Summary")
        c.setFont("Helvetica", 10)
        c.setFillColor(body_color)
        for line in split_text(summary, 500):
            c.drawString(50, y, line)
            y -= 12
        y -= 12

    # Skills section
    skills = resume.get("skills", [])
    if skills:
        add_section_header("Skills")
        c.setFont("Helvetica", 10)
        c.setFillColor(body_color)
        skill_line = ", ".join(skills)
        for line in split_text(skill_line, 500):
            c.drawString(50, y, line)
            y -= 12
        y -= 12

    # Experience section
    experience = resume.get("experience", [])
    if experience:
        add_section_header("Experience")
        for exp in experience:
            title = f"{exp.get('position','')} at {exp.get('company','')}".strip()
            dates = (
                f"{exp.get('startDate','')} – {exp.get('endDate','Present')}".strip()
            )
            desc = exp.get("description", "")
            c.setFont("Helvetica-Bold", 12)
            c.setFillColor(body_color)
            c.drawString(50, y, title)
            y -= 14
            if dates:
                c.setFont("Helvetica-Oblique", 8)
                c.drawString(50, y, dates)
                y -= 12
            if desc:
                c.setFont("Helvetica", 10)
                for line in split_text(desc, 500):
                    c.drawString(50, y, line)
                    y -= 12
            y -= 8  # small gap between entries
        y -= 12  # larger gap after entire experience section

    # Education section
    education = resume.get("education", [])
    if education:
        add_section_header("Education")
        for edu in education:
            degree = f"{edu.get('degree','')} at {edu.get('institution','')}".strip()
            dates = f"{edu.get('startDate','')} – {edu.get('endDate','')}".strip()
            desc = edu.get("description", "")
            c.setFont("Helvetica-Bold", 12)
            c.setFillColor(body_color)
            c.drawString(50, y, degree)
            y -= 14
            if dates:
                c.setFont("Helvetica-Oblique", 8)
                c.drawString(50, y, dates)
                y -= 12
            if desc:
                c.setFont("Helvetica", 10)
                for line in split_text(desc, 500):
                    c.drawString(50, y, line)
                    y -= 12
            y -= 8  # small gap between entries
        y -= 12  # larger gap after entire education section

    c.save()


def draw_gradient_line(c, y, width=500, height=3):
    """
    Draw a horizontal decorative line at the specified y coordinate.  If
    gradient support is available in ReportLab, a linear gradient from
    light green to blue is used; otherwise a solid teal line is drawn.
    Returns the total vertical space consumed (line height + a small
    intrinsic gap).
    """
    if GRADIENT_SUPPORTED:
        d = Drawing(width, height)
        gradient = LinearGradient(
            0,
            0,
            width,
            0,
            [
                (0, colors.Color(0.5, 0.95, 0.75)),  # light green
                (1, colors.Color(0.2, 0.6, 1.0)),  # blue
            ],
        )
        rect = Rect(0, 0, width, height, fillColor=gradient, strokeWidth=0)
        d.add(rect)
        renderPDF.draw(d, c, 50, y - height)
    else:
        c.setFillColor(colors.Color(0.3, 0.8, 0.9))
        c.rect(50, y - height, width, height, fill=1, stroke=0)
    return height + 2


def split_text(text, max_width):
    """
    Splits a string into a list of lines, ensuring that each line when
    drawn with the current font does not exceed max_width points.  This
    simplistic implementation estimates 5 points per character.
    """
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = current + (" " if current else "") + word
        if len(test) * 5 > max_width:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.get_json()
    if not data or not data.get("personal", {}).get("name"):
        return jsonify({"error": "Missing required field: personal.name"}), 400
    corrected = correct_resume(data)
    resume_id = str(int(datetime.utcnow().timestamp() * 1000))
    filename = f"{resume_id}.pdf"
    pdf_path = os.path.join(RESUME_DIR, filename)
    generate_pdf(corrected, pdf_path)
    entries = load_database()
    entries.append(
        {
            "id": resume_id,
            "createdAt": datetime.utcnow().isoformat() + "Z",
            "fileName": filename,
            "data": corrected,
        }
    )
    save_database(entries)
    return jsonify({"id": resume_id, "pdfUrl": f"/api/resumes/{resume_id}"})


@app.route("/api/resumes", methods=["GET"])
def list_resumes():
    entries = load_database()
    return jsonify([{"id": e["id"], "createdAt": e.get("createdAt")} for e in entries])


@app.route("/api/resumes/<resume_id>", methods=["GET"])
def download_resume(resume_id):
    entries = load_database()
    record = next((e for e in entries if e["id"] == resume_id), None)
    if not record:
        return "Resume not found", 404
    return send_from_directory(RESUME_DIR, record["fileName"], as_attachment=True)


if __name__ == "__main__":
    app.run(debug=True)
