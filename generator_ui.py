import json
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# NEW FUNCTION TO BE CALLED BY THE APP
def generate_html(input_json_path: Path, template_name: str) -> Path:
    """Renders an HTML file from a JSON file and a template."""
    template_dir = Path("./templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)

    with open(input_json_path, 'r', encoding='utf-8') as f:
        resume_data = json.load(f)

    rendered_html = template.render(resume_data)

    output_path = input_json_path.with_suffix('.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rendered_html)
    
    return output_path


def main():
    if len(sys.argv) < 3:
        print("Usage: python generator.py <path_to_json_file> <template_name.html>")
        sys.exit(1)

    input_json_path = Path(sys.argv[1])
    template_name = sys.argv[2]
    
    output_path = generate_html(input_json_path, template_name)
    print(f"✅ Success! Your resume has been generated at: {output_path}")

if __name__ == "__main__":
    main()