# tools/pdf_tool.py
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
import markdown
import os
import re

def md_to_pdf(md_path: str, pdf_out: str):
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(pdf_out), exist_ok=True)
    
    # Read markdown content
    with open(md_path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # Convert markdown to HTML then to plain text for PDF
    html = markdown.markdown(md_content, extensions=['fenced_code', 'tables'])
    
    # Simple HTML to text conversion for PDF
    text = re.sub('<[^<]+?>', '', html)  # Remove HTML tags
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    
    # Create PDF
    doc = SimpleDocTemplate(pdf_out)
    styles = getSampleStyleSheet()
    story = []
    
    # Split text into paragraphs and add to story
    paragraphs = text.split('\n\n')
    for para in paragraphs:
        if para.strip():
            story.append(Paragraph(para.strip(), styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
    
    doc.build(story)
    return pdf_out
