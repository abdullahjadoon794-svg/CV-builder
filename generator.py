import json
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

def main():
    """
    Renders a resume by combining a JSON data file with a Jinja2 template.
    """
    # --- 1. Argument Check ---
    # Ensure the user provides the JSON file and template name.
    if len(sys.argv) < 3:
        print("Usage: python generator.py <path_to_json_file> <template_name.html>")
        print("Example: python generator.py resumes/my_resume.parsed.json template_1.html")
        sys.exit(1)

    input_json_path = Path(sys.argv[1])
    template_name = sys.argv[2]
    
    # Check if the input files exist
    if not input_json_path.is_file():
        print(f"❌ Error: JSON file not found at '{input_json_path}'")
        sys.exit(1)

    # --- 2. Set up Jinja2 Environment ---
    # This tells Jinja2 where to find your templates.
    template_dir = Path("./templates")
    if not template_dir.is_dir():
        print(f"❌ Error: 'templates' directory not found. Make sure it exists in the same folder as this script.")
        sys.exit(1)
        
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Check if the chosen template exists
    try:
        template = env.get_template(template_name)
    except Exception:
        print(f"❌ Error: Template '{template_name}' not found in the 'templates' directory.")
        sys.exit(1)

    # --- 3. Load the JSON Data ---
    print(f"📄 Loading data from '{input_json_path}'...")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        resume_data = json.load(f)

    # --- 4. Render the Template ---
    # This is the magic step: merge the data with the template.
    print(f"🎨 Rendering with '{template_name}'...")
    rendered_html = template.render(resume_data)

    # --- 5. Save the Output ---
    # The output file will be saved next to the original JSON with a .html extension.
    output_path = input_json_path.with_suffix('.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rendered_html)

    print(f"\n✅ Success! Your resume has been generated at: {output_path}")


if __name__ == "__main__":
    main()