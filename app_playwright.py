import streamlit as st
from pathlib import Path
import os

# Import the NEW synchronous function
from ignore_files.pdf_generator_playwright import create_pdf
from parser import parse_resume
from generator_ui_layout import generate_html

# --- PAGE CONFIG ---
st.set_page_config(page_title="AI Resume Builder", page_icon="📄", layout="wide")

# --- DIRECTORIES ---
TEMPLATES_DIR = Path("./templates")
TEMP_DIR = Path("./temp_files")
TEMP_DIR.mkdir(exist_ok=True)

# --- UI ---
st.title("AI Resume Builder 🤖")
st.markdown("Upload your resume, choose a template, and let the AI do the rest!")

# Get list of available templates
try:
    template_files = [f.name for f in TEMPLATES_DIR.iterdir() if f.name.endswith('.html')]
    if not template_files:
        st.error("No template files found in the 'templates' directory.")
        st.stop()
except FileNotFoundError:
    st.error("The 'templates' directory was not found.")
    st.stop()

# --- INPUT WIDGETS ---
uploaded_file = st.file_uploader("1. Upload your resume", type=['txt', 'pdf', 'docx'])
selected_template = st.selectbox("2. Choose your template", options=template_files)
generate_button = st.button("✨ Generate My AI Resume", type="primary")

st.markdown("---")

# --- LOGIC ---
if generate_button:
    if uploaded_file is None:
        st.warning("Please upload your resume first.")
    else:
        temp_file_path = TEMP_DIR / uploaded_file.name
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        with st.spinner("AI is parsing your resume..."):
            json_output_path = parse_resume(temp_file_path)
            st.success("Parsing complete!")

        with st.spinner("Generating resume HTML..."):
            html_output_path = generate_html(json_output_path, selected_template)
            st.success("HTML generated!")

        with st.spinner("Converting to PDF using headless browser..."):
            # Now a simple, direct function call. No asyncio needed.
            pdf_output_path = create_pdf(html_output_path)
        
        st.subheader("Your New Resume is Ready!")
        
        with open(html_output_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        st.markdown("### 📄 Resume Preview")
        st.components.v1.html(html_content, height=800, scrolling=True)
        
        col1, col2 = st.columns(2)
        
        if pdf_output_path:
            st.success("✅ PDF generation complete!")
            with open(pdf_output_path, "rb") as f:
                pdf_data = f.read()
            
            with col1:
                st.download_button("⬇️ Download PDF", data=pdf_data, file_name=pdf_output_path.name, mime="application/pdf")
            os.remove(pdf_output_path)
        else:
            st.warning("PDF generation failed.")
        
        with col2:
            st.download_button("⬇️ Download HTML", data=html_content, file_name=html_output_path.name, mime="text/html")
        
        os.remove(temp_file_path)
        os.remove(json_output_path)
        os.remove(html_output_path)