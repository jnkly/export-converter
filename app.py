# app.py
# Minimal FastAPI app to upload a Jadu export ZIP and return a Word doc spec

from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
import zipfile
import json
import os
import shutil
from docx import Document

app = FastAPI()

UPLOAD_DIR = "temp_upload"
EXTRACT_DIR = "temp_extract"
OUTPUT_FILE = "output.docx"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(EXTRACT_DIR, exist_ok=True)


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <h2>Jadu Export → Form Spec</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
      <input type="file" name="file" accept=".zip" required />
      <button type="submit">Generate spec</button>
    </form>
    """


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    zip_path = os.path.join(UPLOAD_DIR, file.filename)

    # Save uploaded file
    with open(zip_path, "wb") as f:
        f.write(await file.read())

    # Clean extract dir
    shutil.rmtree(EXTRACT_DIR)
    os.makedirs(EXTRACT_DIR, exist_ok=True)

    # Extract zip
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(EXTRACT_DIR)

    # Find JSON file
    json_file = None
    for root, _, files in os.walk(EXTRACT_DIR):
        for f in files:
            if f.endswith(".json"):
                json_file = os.path.join(root, f)
                break

    if not json_file:
        return {"error": "No JSON file found in ZIP"}

    # Load JSON
    with open(json_file) as f:
        data = json.load(f)

    resources = data.get("resources", {})

    # Group resources
    grouped = {}
    for key, value in resources.items():
        rtype = key.split("::")[0]
        grouped.setdefault(rtype, []).append(value)

    # Build document
    doc = Document()
    doc.add_heading("Form Specification", 0)

    # Fields
    doc.add_heading("Fields", level=1)
    for field in grouped.get("case-field", []):
        label = field.get("label", "Unnamed field")
        dtype = field.get("data_type", "unknown")

        doc.add_heading(label, level=2)
        doc.add_paragraph(f"Type: {dtype}")

    # Workflow
    doc.add_heading("Workflow", level=1)
    for status in grouped.get("case-status", []):
        name = status.get("label", "Unnamed status")
        doc.add_paragraph(name)

    # Emails
    doc.add_heading("Emails", level=1)
    for email in grouped.get("alert-email-template", []):
        subject = email.get("subject", "No subject")
        doc.add_heading(subject, level=2)

    doc.save(OUTPUT_FILE)

    # Cleanup uploaded zip (optional)
    os.remove(zip_path)

    return FileResponse(OUTPUT_FILE, filename="form-spec.docx")


# requirements.txt
# fastapi
# uvicorn
# python-docx


# Procfile (for Render)
# web: uvicorn app:app --host 0.0.0.0 --port 10000
