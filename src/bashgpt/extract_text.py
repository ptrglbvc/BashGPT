import html2text
import fitz
from docx import Document
from markdownify import markdownify as md

def extract_text_from_html(html):
    converter = html2text.HTML2Text()
    converter.ignore_links = True  # Ignore links
    converter.ignore_images = True  # Ignore images
    text = converter.handle(html)
    return text

def extract_text_from_pdf(pdf_path, is_stream=False):
    doc = fitz.open(stream=pdf_path, filetype="pdf") if is_stream else fitz.open(pdf_path, filetype="pdf")
    text_content = ""
    text_content += "<file-start>"
    for idx, page in enumerate(doc.pages()):
        text_content += f"<page {idx + 1}>"
        text = page.get_text()
        text_content += text
        text_content += f"</page {idx + 1}>"
    text_content += "<file-end>"
    return text_content

def extract_text_from_docx(docx_path):
    doc = Document(docx_path)
    content = "\n".join([paragraph.text for paragraph in doc.paragraphs])
    markdown_content = "<file-start>\n" + md(content) + "\n<file-end>\n"

    if markdown_content: return markdown_content
    else: return "Error reading file"
