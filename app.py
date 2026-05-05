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
    try:
        # Save uploaded file
        zip_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(zip_path, "wb") as f:
            f.write(await file.read())

        # Reset extract folder
        if os.path.exists(EXTRACT_DIR):
            shutil.rmtree(EXTRACT_DIR)
        os.makedirs(EXTRACT_DIR, exist_ok=True)

        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)

        # Find valid Jadu JSON
        json_file = None

        for root, _, files in os.walk(EXTRACT_DIR):
            for fname in files:
                if fname.endswith(".json"):
                    path = os.path.join(root, fname)

                    # Skip empty files
                    if os.path.getsize(path) == 0:
                        continue

                    try:
                        with open(path, encoding="utf-8", errors="replace") as f:
                            data = json.load(f)

                        if "resources" in data:
                            json_file = path
                            break

                    except Exception:
                        continue

            if json_file:
                break

        if not json_file:
            return {"error": "No valid Jadu JSON file found in ZIP"}

        # Load JSON (safe encoding)
        with open(json_file, encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        resources = data.get("resources", {})

        # Group resources
        grouped = {}
        for key, value in resources.items():
            rtype = key.split("::")[0]
            grouped.setdefault(rtype, []).append(value)

        # Build Word doc
        doc = Document()
        doc.add_heading("Form Specification", 0)

        # Fields
        doc.add_heading("Fields", level=1)
        for field in grouped.get("case-field", []):
            if not isinstance(field, dict):
                continue

            label = field.get("label", "Unnamed field")
            dtype = field.get("data_type", "unknown")

            doc.add_heading(label, level=2)
            doc.add_paragraph(f"Type: {dtype}")

        # Workflow
        doc.add_heading("Workflow", level=1)
        for status in grouped.get("case-status", []):
            if not isinstance(status, dict):
                continue

            name = status.get("label", "Unnamed status")
            doc.add_paragraph(name)

        # Emails
        doc.add_heading("Emails", level=1)
        for email in grouped.get("alert-email-template", []):
            if not isinstance(email, dict):
                continue

            subject = email.get("subject", "No subject")
            doc.add_heading(subject, level=2)

        doc.save(OUTPUT_FILE)

        # Cleanup upload
        os.remove(zip_path)

        return FileResponse(OUTPUT_FILE, filename="form-spec.docx")

    except Exception as e:
        return {"error": str(e)}
