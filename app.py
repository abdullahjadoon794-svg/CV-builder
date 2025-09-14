import streamlit as st
from pathlib import Path
import os

# Import the functions from your upgraded scripts
from parser import parse_resume
from generator_ui import generate_html
from pdf_generator import create_pdf

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="AI Resume Builder",
    page_icon="📄",
    layout="wide"
)

# --- DIRECTORIES ---
TEMPLATES_DIR = Path("./templates")
TEMP_DIR = Path("./temp_files")
TEMP_DIR.mkdir(exist_ok=True) # Create temp directory if it doesn't exist

# --- UI ---
st.title("AI Resume Builder 🤖")
st.markdown("Upload your resume, choose a template, and let the AI do the rest!")

# Get list of available templates
try:
    template_files = [f.name for f in TEMPLATES_DIR.iterdir() if f.name.endswith('.html')]
    if not template_files:
        st.error("No template files found in the 'templates' directory. Please add some.")
        st.stop()
except FileNotFoundError:
    st.error("The 'templates' directory was not found. Please create it and add your Jinja2 templates.")
    st.stop()

# --- INPUT WIDGETS ---
uploaded_file = st.file_uploader(
    "1. Upload your resume",
    type=['txt', 'pdf', 'docx'],
    help="Upload your existing resume in .txt, .pdf, or .docx format."
)

selected_template = st.selectbox(
    "2. Choose your template",
    options=template_files,
    help="Select the visual style for your new resume."
)

generate_button = st.button("✨ Generate My AI Resume", type="primary")

st.markdown("---")

# --- LOGIC ---
if generate_button:
    if uploaded_file is None:
        st.warning("Please upload your resume first.")
    else:
        # Save the uploaded file to a temporary location
        temp_file_path = TEMP_DIR / uploaded_file.name
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("AI is parsing your resume... This might take a moment."):
            try:
                # Call the parser function
                json_output_path = parse_resume(temp_file_path)
                st.success(f"Parsing complete! JSON data saved to `{json_output_path}`")
            except Exception as e:
                st.error(f"An error occurred during parsing: {e}")
                st.stop()

        with st.spinner("Generating your beautiful new resume..."):
            try:
                # Call the generator function
                html_output_path = generate_html(json_output_path, selected_template)
                st.success(f"Resume generated! Final HTML saved to `{html_output_path}`")
            except Exception as e:
                st.error(f"An error occurred during generation: {e}")
                st.stop()

        # --- PDF GENERATION ---
        with st.spinner("Converting to PDF..."):
            pdf_output_path = create_pdf(html_output_path)
        
        # --- DISPLAY RESULTS ---
        st.subheader("Your New Resume is Ready!")
        
        # Always read and display the HTML content
        with open(html_output_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Display HTML preview in an iframe
        st.markdown("### 📄 Resume Preview")
        st.components.v1.html(html_content, height=800, scrolling=True)
        
        # Create two columns for download buttons
        col1, col2 = st.columns(2)
        
        if pdf_output_path:
            # Success - PDF was generated
            st.success("✅ PDF generation complete!")
            
            # Read the PDF file for download
            with open(pdf_output_path, "rb") as f:
                pdf_data = f.read()
            
            # Offer PDF download button in first column
            with col1:
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_data,
                    file_name=pdf_output_path.name,
                    mime="application/pdf"
                )
            
            # Clean up PDF file after reading
            os.remove(pdf_output_path)
        else:
            # PDF generation failed
            st.warning("PDF generation failed. HTML version available for download.")
        
        # Always offer HTML download button in second column
        with col2:
            st.download_button(
                label="⬇️ Download HTML",
                data=html_content,
                file_name=html_output_path.name,
                mime="text/html"
            )
        
        # Clean up remaining temp files
        os.remove(temp_file_path)
        os.remove(json_output_path)
        os.remove(html_output_path)
