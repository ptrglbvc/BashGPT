import html2text

def extract_text_from_html(html):
    converter = html2text.HTML2Text()
    converter.ignore_links = True  # Ignore links
    converter.ignore_images = True  # Ignore images
    text = converter.handle(html)
    return text
