import json
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from layout_generator import generate_layout_plan

def generate_html(input_json_path: Path, template_name: str, force_regenerate: bool = False) -> Path:
    """
    Generates an HTML file. It will use a cached layout plan if one exists,
    unless force_regenerate is True.
    """
    template_dir = Path("./templates")
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)

    # Define the path for the cached layout plan
    layout_plan_path = input_json_path.with_suffix('.layout.json')

    with open(input_json_path, 'r', encoding='utf-8') as f:
        resume_data = json.load(f)

    layout_plan = None
    # Check for a cached layout plan, unless regeneration is forced
    if not force_regenerate and layout_plan_path.exists():
        print("✅ Found cached layout plan. Loading from disk...")
        with open(layout_plan_path, 'r', encoding='utf-8') as f:
            layout_plan = json.load(f)
    
    # If no cached plan, generate a new one via API call
    if layout_plan is None:
        print("🧠 No cached layout plan found. Generating new plan with AI...")
        layout_plan = generate_layout_plan(resume_data, template_name)
        # Save the new plan to the cache file for next time
        with open(layout_plan_path, 'w', encoding='utf-8') as f:
            json.dump(layout_plan, f, indent=2)
        print(f"💾 AI Layout Plan saved to: {layout_plan_path}")


    rendered_html = template.render(
        resume_data=resume_data, 
        layout_plan=layout_plan
    )

    output_path = input_json_path.with_suffix('.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(rendered_html)
    
    print(f"✅ HTML generated successfully at: {output_path}")
    return output_path


def main():
    """
    Command-line interface for testing the generator.
    Allows forcing the regeneration of the layout plan.
    """
    import argparse
    parser = argparse.ArgumentParser(description="Generate an HTML resume from a JSON data file.")
    parser.add_argument("json_file", help="Path to the .parsed.json file.")
    parser.add_argument("template", help="Name of the template file (e.g., template1.html).")
    parser.add_argument(
        "--force-regen",
        action="store_true",
        help="Force regeneration of the AI layout plan, ignoring any cached version."
    )
    args = parser.parse_args()

    input_path = Path(args.json_file)
    template_name = args.template
    
    generate_html(input_path, template_name, args.force_regen)


if __name__ == "__main__":
    main()