from pathlib import Path
from playwright.sync_api import sync_playwright

def create_pdf(html_filepath: Path) -> Path | None:
    """
    Converts a given HTML file to a PDF file using the SYNCHRONOUS Playwright API.

    Args:
        html_filepath: The path to the input HTML file.

    Returns:
        The path to the generated PDF file, or None if an error occurred.
    """
    print(f"📄 Converting '{html_filepath.name}' to PDF using Playwright (Sync)...")
    pdf_filepath = html_filepath.with_suffix('.pdf')

    try:
        with sync_playwright() as p:
            # Launch the browser
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # Navigate to the local HTML file
            page.goto(f"file://{html_filepath.resolve()}")
            
            # Generate the PDF
            page.pdf(
                path=str(pdf_filepath),
                format='A4',
                print_background=True,
                margin={"top": "0.75in", "right": "0.75in", "bottom": "0.75in", "left": "0.75in"}
            )
            
            # Close the browser
            browser.close()
            
        print(f"✅ PDF generated successfully at: {pdf_filepath}")
        return pdf_filepath
        
    except Exception as e:
        print(f"❌ Error during Playwright PDF generation: {e}")
        return None