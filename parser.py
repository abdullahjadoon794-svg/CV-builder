import os, json, sys, re
from pathlib import Path
from typing import Any, Dict, List
import docx
import pdfplumber

# NEW SDK
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Fetch key
api_key = os.getenv("GEMINI_API_KEY")

# --- Ollama Configuration ---
OLLAMA_ENDPOINT = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "qwen2.5-coder:7b" # Or any other model you have pulled

# ---- tiny cleaner to reduce LLM guesswork
def preclean(text: str) -> str:
    # normalize bullets, collapse whitespace, strip fancy quotes
    t = text.replace("•", "- ").replace("●", "- ").replace("–", "-")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = t.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return t.strip()

# ---- simple sanity check: don't trust hallucinated names
def wipe_if_not_in_source(value: str | None, source: str) -> str | None:
    if not value:
        return value
    v = re.sub(r"[^a-z]", "", value.lower())
    s = re.sub(r"[^a-z]", "", source.lower())
    return value if v in s else None

# ---- New function to handle different file types
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


# ---- JSON Schema for structured output (strict)
RESUME_SCHEMA: Dict[str, Any] = {
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
    # make top-level fields present; allow nulls/empties inside
    "required": [
        "contact_info",
        "work_experience",
        "education",
        "skills",
        "projects",
    ],
}

SYSTEM_INSTRUCTION = (
    "You are a strict resume parser. Parse ONLY from the provided text. "
    "Never invent facts. If data is missing, use null (or [] for arrays). "
    "Dates should be 'YYYY' or 'YYYY-MM'. If a section does not exist, return an empty array/object."
)

# ---- SEGMENTATION SCHEMA for first-stage text extraction
SEGMENTATION_SCHEMA: Dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "candidate_name_text": {"type": "STRING", "description": "The full name of the candidate, typically the largest text at the top."},
        "contact_info_section": {"type": "STRING"},
        "summary_section": {"type": "STRING"},
        "work_experience_section": {"type": "STRING"},
        "education_section": {"type": "STRING"},
        "skills_section": {"type": "STRING"},
        "certifications_section": {"type": "STRING"},
        "projects_section": {"type": "STRING"},
        "languages_section": {"type": "STRING"},
        "awards_section": {"type": "STRING"},
    },
    "required": ["candidate_name_text","contact_info_section", "work_experience_section", "education_section", "skills_section"]
}

# ---- Segmentation function for first-stage parsing
def segment_resume_text(text: str) -> Dict[str, str]:
    """Extract sections from resume text using Gemini API with segmentation schema."""
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"#gemini-1.5-flash,gemini-2.5-flash
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=SEGMENTATION_SCHEMA,
        system_instruction=(
            "You are a resume segmentation tool. Extract the main sections from the resume text. "
            "Return each section as a string. If a section doesn't exist, return an empty string. "
            "Be precise and only extract what's clearly present in the text."
        ),
    )
    
    prompt = f"Segment the following resume text into sections:\n\n{text}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        segments = json.loads(clean_json_text)
        return segments
    except Exception as e:
        print(f"❌ Segmentation failed: {e}")
        # Return empty segments as fallback
        return {key: "" for key in SEGMENTATION_SCHEMA["properties"].keys()}

# ---- Individual section parsing functions with error handling
def parse_work_experience_chunk(chunk: str) -> List[Dict[str, Any]]:
    """Parse work experience section from segmented text."""
    if not chunk.strip():
        return []
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    work_exp_schema = {
        "type": "ARRAY",
        "items": RESUME_SCHEMA["properties"]["work_experience"]["items"]
    }
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=work_exp_schema,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse work experience from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Work experience parsing failed: {e}")
        return []

def parse_education_chunk(chunk: str) -> List[Dict[str, Any]]:
    """Parse education section from segmented text."""
    if not chunk.strip():
        return []
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    education_schema = {
        "type": "ARRAY",
        "items": RESUME_SCHEMA["properties"]["education"]["items"]
    }
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=education_schema,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse education from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Education parsing failed: {e}")
        return []

def parse_skills_chunk(chunk: str) -> Dict[str, Any]:
    """Parse skills section from segmented text."""
    if not chunk.strip():
        return {"clinical": [], "technical": [], "soft": [], "tools": []}
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    skills_schema = RESUME_SCHEMA["properties"]["skills"]
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=skills_schema,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse skills from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Skills parsing failed: {e}")
        return {"clinical": [], "technical": [], "soft": [], "tools": []}

def parse_contact_info_chunk(chunk: str) -> Dict[str, Any]:
    """Parse contact information from segmented text."""
    if not chunk.strip():
        return {}
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    contact_schema = RESUME_SCHEMA["properties"]["contact_info"]
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=contact_schema,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse contact information from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Contact info parsing failed: {e}")
        return {}

def parse_summary_chunk(chunk: str) -> str:
    """Parse summary section from segmented text."""
    if not chunk.strip():
        return ""
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="text/plain",
        system_instruction=(
            "Extract the professional summary from the provided text. "
            "Return only the summary text as a string, not as JSON. "
            "If no summary is found, return an empty string."
        ),
    )
    
    prompt = f"Extract the professional summary from this text:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        return resp.text.strip()
    except Exception as e:
        print(f"❌ Summary parsing failed: {e}")
        return ""

def parse_certifications_chunk(chunk: str) -> List[Dict[str, Any]]:
    """Parse certifications section from segmented text."""
    if not chunk.strip():
        return []
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    cert_schema = {
        "type": "ARRAY",
        "items": RESUME_SCHEMA["properties"]["certifications"]["items"]
    }
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=cert_schema,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse certifications from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Certifications parsing failed: {e}")
        return []

def parse_projects_chunk(chunk: str) -> List[Dict[str, Any]]:
    """Parse projects section from segmented text."""
    if not chunk.strip():
        return []
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    projects_schema = {
        "type": "ARRAY",
        "items": RESUME_SCHEMA["properties"]["projects"]["items"]
    }
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=projects_schema,
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse projects from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Projects parsing failed: {e}")
        return []

def parse_languages_chunk(chunk: str) -> List[str]:
    """Parse languages section from segmented text."""
    if not chunk.strip():
        return []
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema={"type": "ARRAY", "items": {"type": "STRING"}},
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse languages from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Languages parsing failed: {e}")
        return []

def parse_awards_chunk(chunk: str) -> List[str]:
    """Parse awards section from segmented text."""
    if not chunk.strip():
        return []
    
    client = genai.Client(api_key=api_key)
    model_name = "gemini-1.5-flash"
    
    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema={"type": "ARRAY", "items": {"type": "STRING"}},
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    prompt = f"Parse awards from:\n\n{chunk}"
    
    try:
        resp = client.models.generate_content(model=model_name, contents=prompt, config=config)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        return json.loads(clean_json_text)
    except Exception as e:
        print(f"❌ Awards parsing failed: {e}")
        return []

# ---- Refactored main parsing function with two-stage pipeline
def parse_resume(src_path: Path) -> Path:
    """Parses a resume file using two-stage pipeline and returns the path to the output JSON."""
    text = preclean(read_file_content(src_path))
    
    # First stage: Segment the resume text
    segments = segment_resume_text(text)
    
    # Second stage: Parse each section individually with error handling
    parsed_data = {}
    
    # --- MODIFIED CONTACT INFO & NAME HANDLING ---
    try:
        # 1. Parse the contact info block for details like email, phone, etc.
        contact_info = parse_contact_info_chunk(segments.get("contact_info_section", ""))
        
        # 2. Get the candidate's name from its dedicated, high-priority segment.
        candidate_name = segments.get("candidate_name_text", "")
        
        # 3. Explicitly add the captured name to the contact_info dictionary.
        if candidate_name:
            contact_info["name"] = candidate_name
        
        # 4. Run the final validation check on the name.
        if contact_info and "name" in contact_info:
            contact_info["name"] = wipe_if_not_in_source(contact_info.get("name"), text)
            
        parsed_data["contact_info"] = contact_info or {}
    except Exception as e:
        print(f"⚠️ Contact info parsing error: {e}")
        parsed_data["contact_info"] = {}
    
    # --- (The rest of the function remains the same) ---

    # Work experience
    try:
        parsed_data["work_experience"] = parse_work_experience_chunk(segments.get("work_experience_section", ""))
    except Exception as e:
        print(f"⚠️ Work experience parsing error: {e}")
        parsed_data["work_experience"] = []
    
    # Education
    try:
        parsed_data["education"] = parse_education_chunk(segments.get("education_section", ""))
    except Exception as e:
        print(f"⚠️ Education parsing error: {e}")
        parsed_data["education"] = []
    
    # Skills
    try:
        parsed_data["skills"] = parse_skills_chunk(segments.get("skills_section", ""))
    except Exception as e:
        print(f"⚠️ Skills parsing error: {e}")
        parsed_data["skills"] = {"clinical": [], "technical": [], "soft": [], "tools": []}
    
    # Optional sections with fallbacks
    try:
        parsed_data["summary"] = parse_summary_chunk(segments.get("summary_section", ""))
    except Exception as e:
        print(f"⚠️ Summary parsing error: {e}")
        parsed_data["summary"] = ""
    
    try:
        parsed_data["certifications"] = parse_certifications_chunk(segments.get("certifications_section", ""))
    except Exception as e:
        print(f"⚠️ Certifications parsing error: {e}")
        parsed_data["certifications"] = []
    
    try:
        parsed_data["projects"] = parse_projects_chunk(segments.get("projects_section", ""))
    except Exception as e:
        print(f"⚠️ Projects parsing error: {e}")
        parsed_data["projects"] = []
    
    try:
        parsed_data["languages"] = parse_languages_chunk(segments.get("languages_section", ""))
    except Exception as e:
        print(f"⚠️ Languages parsing error: {e}")
        parsed_data["languages"] = []
    
    try:
        parsed_data["awards"] = parse_awards_chunk(segments.get("awards_section", ""))
    except Exception as e:
        print(f"⚠️ Awards parsing error: {e}")
        parsed_data["awards"] = []
    
    # Ensure required fields are present
    for field in RESUME_SCHEMA["required"]:
        if field not in parsed_data:
            if field == "contact_info":
                parsed_data[field] = {}
            elif field == "skills":
                parsed_data[field] = {"clinical": [], "technical": [], "soft": [], "tools": []}
            else:
                parsed_data[field] = []
    
    # Save to JSON file
    out_path = src_path.with_suffix(".parsed.json")
    out_path.write_text(json.dumps(parsed_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Parsed JSON saved to: {out_path}")
    return out_path
def main():
    if len(sys.argv) < 2:
        print("Usage: python gemini_parser.py path/to/sample.txt")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    parse_resume(src_path)

if __name__ == "__main__":
    main()