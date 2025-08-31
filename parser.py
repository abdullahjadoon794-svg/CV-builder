import os, json, sys, re
from pathlib import Path
from typing import Any, Dict

# NEW SDK
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Fetch key
api_key = os.getenv("GEMINI_API_KEY")

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
                    "start_date": {"type": "STRING"},  # YYYY or YYYY-MM
                    "end_date": {"type": "STRING"},    # YYYY or YYYY-MM or "Present"
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

def main():
    if len(sys.argv) < 2:
        print("Usage: python gemini_parser.py path/to/sample.txt")
        sys.exit(1)

    src_path = Path(sys.argv[1])
    text = preclean(src_path.read_text(encoding="utf-8", errors="ignore"))

    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    # Use the model you asked for; stick to 1.5 Flash for cost/speed
    model_name = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    config = types.GenerateContentConfig(
        temperature=0.0,
        response_mime_type="application/json",
        response_schema=RESUME_SCHEMA,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    prompt = (
        "Parse the following resume-like text into the JSON schema. "
        "If the person is a surgical technician or similar, capture clinical skills accurately.\n\n"
        f"=== START TEXT ===\n{text}\n=== END TEXT ==="
    )

    resp = client.models.generate_content(model=model_name, contents=prompt, config=config)

    # SDK returns JSON text when response_mime_type=application/json
    raw = resp.text.strip()

    # belts & suspenders: strip backticks if any slipped in
    raw = re.sub(r"^```json\s*|\s*```$", "", raw)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # fallback: try to extract the first {...} block
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if not m:
            print("❌ Could not find JSON in response. Raw below:\n", raw[:1000])
            sys.exit(2)
        parsed = json.loads(m.group(0))

    # sanity check: don't keep names that aren't in the source text
    ci = parsed.get("contact_info", {}) or {}
    ci["name"] = wipe_if_not_in_source(ci.get("name"), text)
    parsed["contact_info"] = ci

    out_path = src_path.with_suffix(".parsed.json")
    out_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Parsed JSON saved to: {out_path}")

if __name__ == "__main__":
    main()
