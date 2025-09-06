import os, json, sys, re
from pathlib import Path
from typing import Any, Dict
import docx
import pdfplumber

from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# ---- (Keep your preclean and wipe_if_not_in_source functions exactly as they are) ---
def preclean(text: str) -> str:
    # normalize bullets, collapse whitespace, strip fancy quotes
    t = text.replace("•", "- ").replace("●", "- ").replace("–", "-")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = t.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return t.strip()

def wipe_if_not_in_source(value: str | None, source: str) -> str | None:
    if not value:
        return value
    v = re.sub(r"[^a-z]", "", value.lower())
    s = re.sub(r"[^a-z]", "", source.lower())
    return value if v in s else None

# ---- (Keep your read_file_content function exactly as it is) ----
def read_file_content(filepath: Path) -> str:
    """Reads the content of a .txt, .pdf, or .docx file."""
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    if filepath.suffix == ".txt":
        return filepath.read_text(encoding="utf-8", errors="ignore")
    elif filepath.suffix == ".docx":
        doc = docx.Document(filepath)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)
    elif filepath.suffix == ".pdf":
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    else:
        raise ValueError(f"Unsupported file type: {filepath.suffix}. Supported types are .txt, .docx, and .pdf")

# ---- (Keep your RESUME_SCHEMA dictionary exactly as it is) ----
RESUME_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "contact_info": {
            "type": "OBJECT",
            "properties": {
                "name": {"type": "STRING"},
                "email": {"type": "STRING"},
                "phone": {"type": "STRING"},
                "location": {"type": "STRING"},
                "linkedin": {"type": "STRING"},
                "github": {"type": "STRING"},
                "website": {"type": "STRING"},
            },
        },
        "summary": {"type": "STRING"},
        "work_experience": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "role": {"type": "STRING"},
                    "company": {"type": "STRING"},
                    "location": {"type": "STRING"},
                    "start_date": {"type": "STRING"},
                    "end_date": {"type": "STRING"},
                    "is_current": {"type": "BOOLEAN"},
                    "bullets": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
        "education": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "degree": {"type": "STRING"},
                    "field": {"type": "STRING"},
                    "institution": {"type": "STRING"},
                    "location": {"type": "STRING"},
                    "start_date": {"type": "STRING"},
                    "end_date": {"type": "STRING"},
                    "gpa": {"type": "STRING"},
                    "honors": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
            },
        },
        "certifications": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "issuer": {"type": "STRING"},
                    "date": {"type": "STRING"},
                },
            },
        },
        "skills": {
            "type": "OBJECT",
            "properties": {
                "clinical": {"type": "ARRAY", "items": {"type": "STRING"}},
                "technical": {"type": "ARRAY", "items": {"type": "STRING"}},
                "soft": {"type": "ARRAY", "items": {"type": "STRING"}},
                "tools": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
        },
        "projects": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "description": {"type": "STRING"},
                    "technologies": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "link": {"type": "STRING"},
                },
            },
        },
        "languages": {"type": "ARRAY", "items": {"type": "STRING"}},
        "awards": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": [
        "contact_info",
        "work_experience",
        "education",
        "skills",
    ],
}

# REVERTED FUNCTION TO BE CALLED BY THE APP
def parse_resume(src_path: Path) -> Path:
    """Parses a resume file and returns the path to the output JSON."""
    text = preclean(read_file_content(src_path))
    
    # Use the genai.Client method
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    # Define the generation config with the schema
    generation_config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=RESUME_SCHEMA,
        
    )

    system_instruction = (
        "You are a strict resume parser. Parse ONLY from the provided text. "
        "Never invent facts. If data is missing, use null (or [] for arrays). "
        "Dates should be 'YYYY' or 'YYYY-MM'. If a section does not exist, return an empty array/object."
    )
    
    prompt = f"{system_instruction}\n\nParse the following resume:\n\n{text}"

    # Make the API call
    resp = client.models.generate_content(model=model_name, contents=prompt, config=generation_config)


    # Process the response text to get JSON
    raw_text = resp.text.strip()
    clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
    parsed_data = json.loads(clean_json_text)

    # Post-processing and saving
    ci = parsed_data.get("contact_info", {}) or {}
    ci["name"] = wipe_if_not_in_source(ci.get("name"), text)
    parsed_data["contact_info"] = ci

    out_path = src_path.with_suffix(".parsed.json")
    out_path.write_text(json.dumps(parsed_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Parsed JSON saved to: {out_path}")
    return out_path


def main():
    if len(sys.argv) < 2:
        print("Usage: python parser.py path/to/sample.txt")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    parse_resume(src_path)

if __name__ == "__main__":
    main()