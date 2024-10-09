import html2text
import fitz

def extract_text_from_html(html):
    converter = html2text.HTML2Text()
    converter.ignore_links = True  # Ignore links
    converter.ignore_images = True  # Ignore images
    text = converter.handle(html)
    return text

def extract_text_from_pdf(pdf, is_stream=False):
    doc = fitz.open(stream=pdf, filetype="pdf") if is_stream else fitz.open(pdf, filetype="pdf")
    text_content = ""
    text_content += "<file-start>"
    for idx, page in enumerate(doc.pages()):
        text_content += f"<page {idx + 1}>"
        text = page.get_text()
        text_content += text
        text_content += f"</page {idx + 1}>"
    text_content += "<file-end>"
    return text_content

def extract_text_from_docx():
    return "Dev is too lazy to implement the docx reading function rn"
