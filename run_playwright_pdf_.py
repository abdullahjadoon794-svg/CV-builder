# Save this as run_playwright_pdf.py
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

def convert_html_to_pdf(html_filepath_str: str):
    """Takes a path to an HTML file and converts it to a PDF."""
    
    html_filepath = Path(html_filepath_str)
    pdf_filepath = html_filepath.with_suffix('.pdf')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{html_filepath.resolve()}")
            page.pdf(
                path=str(pdf_filepath),
                format='A4',
                print_background=True,
                margin={"top": "0.75in", "right": "0.75in", "bottom": "0.75in", "left": "0.75in"}
            )
            browser.close()
        
        # Emoji removed from the following print statement
        print(f"Success! PDF generated successfully at: {pdf_filepath}")
        # This print statement is crucial for the app to know the output path
        print(f"PDF_PATH:{pdf_filepath}") 
    except Exception as e:
        # Emoji removed from the following print statement
        print(f"Failed! Error during Playwright PDF generation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_playwright_pdf.py <path_to_html_file>")
        sys.exit(1)
    
    input_html_path = sys.argv[1]
    convert_html_to_pdf(input_html_path)