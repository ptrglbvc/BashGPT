from bashgpt.extract_text import extract_text_from_html, extract_text_from_pdf
from bashgpt.util_functions import alert
from bashgpt.chat import chat

import httpx
import os

def get_file(file_url):
    clean_file_url = file_url.replace("\ ", " ")
    file_name = clean_file_url.split("/")[-1]

    if clean_file_url[0:4] == "http":
        # this is to check if the web address contains those ?search=boobs things in the search bar. we want to ignore those
        try:
            question_idx = file_name.index("?")
            dot_idx = file_name.index(".")
            file_name = file_name[:question_idx] if dot_idx < question_idx else file_name
        except:
            pass
        response = httpx.get(clean_file_url)
        content_type = response.headers.get("Content-Type")
        print(response.encoding)
        if content_type.startswith("text/html") or content_type == "application/xhtml+xml":
            chat["files"].append({
                "content" : extract_text_from_html(response.text),
                "name": file_name, 
                "message_idx": len(chat["all_messages"]),
                "extension": "html"
                })

        # prob don't need the first check 
        elif file_name.split(".")[-1] == "pdf" or content_type == "application/pdf":
            alert("pdf attached")
            chat["files"].append({
                "content": extract_text_from_pdf(response.content, is_stream=True),
                "name": file_name,
                "message_idx": len(chat["all_messages"]),
                "extension": "pdf" 
            })
        else:
            alert("File is not utf-8 encoded")

    elif os.path.isfile(clean_file_url):
        try:
            with open(clean_file_url, "r", encoding="utf-8") as file:
                file_contents = file.read()
                chat["files"].append({
                    "content" : file_contents, 
                    "name": file_name, 
                    "message_idx" : len(chat["all_messages"]),
                    "extension": file_name.split(".")[-1]
                    })
        except: 
            if file_name.split(".")[-1] == "pdf":
                chat["files"].append({
                    "content": extract_text_from_pdf(clean_file_url),
                    "name": file_name,
                    "message_idx": len(chat["all_messages"]),
                    "extension": "pdf" 
                })
            else: 
                alert("File not supported")
                
    else:
        alert("Invalid file path")
