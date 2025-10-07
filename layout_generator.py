import os
import json
import re
from typing import Dict, Any
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# This schema defines the structure of the AI's output: the layout plan.
LAYOUT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "pages": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "page": {"type": "INTEGER"},
                    "content": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "component": {"type": "STRING"},
                                "data_key": {"type": "STRING"}
                            },
                             "required": ["component", "data_key"]
                        }
                    }
                },
                "required": ["page", "content"]
            }
        }
    },
    "required": ["pages"]
}

def generate_layout_plan(resume_data: Dict[str, Any], template_style: str) -> Dict[str, Any]:
    """
    Uses an AI to generate a dynamic layout plan for the resume.

    Args:
        resume_data: The structured JSON data of the resume.
        template_style: The user's chosen style (e.g., "Modern", "Classic").

    Returns:
        A JSON object representing the layout plan.
    """
    client = genai.Client(api_key=api_key)
    model_name = "gemini-2.5-flash-lite"
    
    # Create a simple summary of the data to help the AI gauge content size
    content_summary = {key: len(value) if isinstance(value, list) else 1 for key, value in resume_data.items()}

    system_instruction = (
        "You are an expert graphic designer and layout architect for a resume generator. "
        "Your task is to create a JSON-based layout plan that arranges resume components onto one or more A4 pages. "
        "You must decide the best order for the components and where to place page breaks for a clean, professional look."
    )

    # --- ENHANCED PROMPT ---
    # This new prompt asks the AI to act as a "typesetter" by estimating content height.
    prompt = (
        f"You are an expert graphic designer and layout architect creating a professional, multi-page resume PDF from a JSON data object. Your task is to generate a JSON 'layout plan' that avoids awkward page breaks and content splitting.\n\n"
        f"**CONSTRAINTS & HEURISTICS:**\n"
        f"1.  **Canvas**: The target is an A4 page with margins. The usable vertical space per page is approximately **900 units**.\n"
        f"2.  **Content Estimation**: You must estimate the height of each section to decide what fits on a page. Use these heuristics:\n"
        f"    - A section title is **30 units**.\n"
        f"    - Each line of text or bullet point is **15 units**.\n"
        f"    - Add **20 units** of padding after each major section (like work experience).\n"
        f"3.  **Page Break Logic**: Your primary goal is to prevent content from splitting awkwardly. Never split a single job entry or education entry across two pages. If adding the next logical section (e.g., the entire 'Work Experience' block) will exceed the remaining space on the current page, you MUST start that section on a new page.\n"
        f"4.  **Layout Style**: The desired style is '{template_style}'.\n"
        f"5.  **Available Data**: The user has provided the following sections (summary shows number of entries/lines):\n"
        f"    {json.dumps(content_summary, indent=2)}\n\n"
        f"Based on your height calculations, generate the final JSON layout plan. Ensure the 'pages' array in your output reflects your intelligent page break decisions."
    )

    config = types.GenerateContentConfig(
        temperature=0.2,
        response_mime_type="application/json",
        response_schema=LAYOUT_SCHEMA,
    )

    try:
        resp = client.models.generate_content(
    model=model_name,
    contents=[{"role": "user", "parts": [{"text": prompt}]}],
    config=config
)
        raw_text = resp.text.strip()
        clean_json_text = re.sub(r"^```json\s*|\s*```$", "", raw_text)
        layout_plan = json.loads(clean_json_text)
        print("✅ AI Layout Plan Generated Successfully.")
        return layout_plan
    except Exception as e:
        print(f"❌ AI Layout Plan generation failed: {e}")
        # Fallback to a simple, default layout if the AI fails
        return {
            "pages": [
                {"page": 1, "content": [
                    {"component": "contact_info", "data_key": "contact_info"},
                    {"component": "summary", "data_key": "summary"},
                    {"component": "work_experience", "data_key": "work_experience"},
                    {"component": "education", "data_key": "education"},
                    {"component": "skills", "data_key": "skills"}
                ]}
            ]
        }