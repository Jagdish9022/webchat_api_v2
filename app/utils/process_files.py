
import io
import traceback
import xml.etree.ElementTree as ET
import PyPDF2
from fastapi import HTTPException, logger

from app.utils.common import preprocess_text


def process_pdf(file_content: bytes) -> str:
    """Extract text from PDF file."""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += preprocess_text(page_text) + "\n"
        return text
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Error processing PDF file: {str(e)}")

def process_svg(file_content: bytes) -> str:
    """Extract text from SVG file."""
    try:
        svg_content = file_content.decode('utf-8')
        root = ET.fromstring(svg_content)
        # Extract text elements from SVG
        text_elements = root.findall(".//{http://www.w3.org/2000/svg}text")
        text = "\n".join([elem.text for elem in text_elements if elem.text])
        return preprocess_text(text)
    except Exception as e:
        logger.error(f"Error processing SVG: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Error processing SVG file: {str(e)}")

def process_text_file(file_content: bytes) -> str:
    """Process text-based files."""
    try:
        text = file_content.decode('utf-8')
        return preprocess_text(text)
    except Exception as e:
        logger.error(f"Error processing text file: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=400, detail=f"Error processing text file: {str(e)}")