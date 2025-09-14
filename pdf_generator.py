from pathlib import Path
import weasyprint

def create_pdf(html_filepath: Path) -> Path | None:
    """
    Converts a given HTML file to a PDF file.

    Args:
        html_filepath: The path to the input HTML file.

    Returns:
        The path to the generated PDF file, or None if an error occurred.
    """
    print(f"📄 Converting '{html_filepath.name}' to PDF...")
    pdf_filepath = html_filepath.with_suffix('.pdf')

    try:
        # Core WeasyPrint conversion
        weasyprint.HTML(str(html_filepath)).write_pdf(pdf_filepath)
        print(f"✅ PDF generated successfully at: {pdf_filepath}")
        return pdf_filepath

    except Exception as e:
        # Catch any potential errors during PDF generation
        print(f"❌ Error during PDF generation: {e}")
        return None
