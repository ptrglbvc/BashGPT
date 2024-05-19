chat = {
        "all_messages": [],
        "images": [],
        "files": [],
        "is_loaded": False,
        "id": None,
        "mode": "short", 
        "model": "gpt-3.5-turbo", 
        "vision_enabled": False,
        "api_key_name": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "provider" : "openai",
        "color": "purple",
        "description": "",
        "auto_turns": 0,
        "auto_message": "",
        "bash": False}

def add_message_to_chat(role, content):
    global chat
    chat["all_messages"].append({"role": role, "content": content})