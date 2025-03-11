from typing import TypedDict, Literal, List, Optional

class Message(TypedDict):
    role: Literal['user', 'assistant', 'system']
    content: str


class Chat(TypedDict):
    all_messages: List[Message]
    images: List[dict]    # You can further define the structure of images if needed
    files: List[dict]     # Similarly, define the structure for files
    is_loaded: bool
    id: Optional[int]
    mode: str
    model: str
    vision_enabled: bool
    api_key_name: str
    base_url: str
    provider: str
    color: str
    load_last: bool
    description: str
    auto_turns: int
    auto_message: str
    bash: bool
    dalle: bool
    autosave: bool

chat: Chat = {
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
    "provider": "openai",
    "color": "purple",
    "load_last": False,
    "description": "",
    "auto_turns": 0,
    "auto_message": "",
    "bash": False,
    "dalle": False,
    "autosave": False
}

def add_message_to_chat(role: Literal['user', 'assistant', 'system'], content: str) -> None:
    if role not in ['user', 'assistant', 'system']:
        raise ValueError("Invalid role. Must be 'user', 'assistant', or 'system'.")
    message: Message = {
        "role": role,
        "content": content
    }
    chat["all_messages"].append(message)
