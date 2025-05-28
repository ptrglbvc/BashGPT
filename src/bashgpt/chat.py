from typing import TypedDict, Literal, List, Optional
import json
from bashgpt.data_loader import data_loader
from bashgpt.util_functions import is_succinct, alert
from bashgpt.load_defaults import load_defaults
from bashgpt.path import get_path

(modes, models, providers) = data_loader()
path = get_path()

defaults = load_defaults(path)

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
    temperature: float
    frequency_penalty: float
    max_tokens: int
    extra_body: dict
    smooth_streaming: bool  # Add this line

chat: Chat = {
    "all_messages": [],
    "images": [],
    "files": [],
    "is_loaded": False,
    "id": None,
    "mode": "short",
    "model": "gemini-2.0-flash",
    "vision_enabled": False,
    "api_key_name": "OPENAI_API_KEY",
    "base_url": "https://api.openai.com/v1",
    "provider": "google",
    "color": "purple",
    "load_last": False,
    "description": "",
    "auto_turns": 0,
    "auto_message": "",
    "bash": False,
    "dalle": False,
    "autosave": False,
    "temperature": 0.7,
    "frequency_penalty": 1,
    "max_tokens": 4048,
    "extra_body": {},
    "smooth_streaming": True
}

# Add a default for smooth_streaming
if "smooth_streaming" not in chat:
    chat["smooth_streaming"] = True

def reset_chat():
    global chat
    chat["all_messages"] = []
    chat["images"] = []
    chat["files"] = []
    chat["is_loaded"] = False
    chat["description"] = ""
    chat["bash"] = False
    chat["dalle"] = False

def add_message_to_chat(role: Literal['user', 'assistant', 'system'], content: str) -> None:
    global chat
    if role not in ['user', 'assistant', 'system']:
        raise ValueError("Invalid role. Must be 'user', 'assistant', or 'system'.")
    message: Message = {
        "role": role,
        "content": content,
    }
    chat["all_messages"].append(message)


def load_chat(cur, id):
    global chat
    
    chat["all_messages"] = []
    chat["images"] = []
    chat["files"] = []
    
    message_data = cur.execute("SELECT role, message FROM chat_messages WHERE chat_id=?", (id,)).fetchall()
    
    settings_query = cur.execute(
        "SELECT description, model, provider, vision_enabled, temperature, max_tokens, frequency_penalty, dalle, bash, autosave " +
        "FROM chats WHERE chat_id=?", 
        (id,)
    ).fetchall()
    
    if not settings_query:
        raise ValueError(f"No chat found with ID {id}")
    
    [description, model, provider, vision_enabled, temperature, max_tokens, frequency_penalty, dalle, bash, autosave] = settings_query[0]

    chat["id"] = id
    chat["is_loaded"] = True
    chat["temperature"] = temperature
    chat["max_tokens"] = max_tokens
    chat["frequency_penalty"] = frequency_penalty
    chat["description"] = description
    chat["dalle"] = bool(dalle)
    chat["bash"] = bool(bash)
    chat["autosave"] = bool(autosave)

    change_model({"name": model, "provider": provider, "vision_enabled": bool(vision_enabled)}, providers)

    for row in message_data:
        add_message_to_chat(row[0], row[1])

    load_images(cur, id)
    load_files(cur, id)
    
    print(f"Loaded chat {id} with {len(chat['all_messages'])} messages")


def change_model(new_model, providers):
    global chat

    chat["provider"] = new_model["provider"]
    chat["model"] = new_model["name"]
    chat["vision_enabled"] = new_model["vision_enabled"]
    
    if "extra_body" in new_model:
        chat["extra_body"] = new_model["extra_body"]
    else: 
        chat["extra_body"] = {}

    # this updates the base url and the api key variable name
    # we don't need that for non-openai-sdk models
    if chat["provider"] not in ["google", "anthropic"]:
        chat.update(providers[new_model["provider"]])


def load_images(cur, id):
    global chat
    data = cur.execute("SELECT content, name, extension, message_idx FROM images WHERE chat_id=?", (id, )).fetchall()
    for row in data:
        chat["images"].append({
            "content": row[0],
            "name": row[1],
            "extension": row[2],
            "message_idx": row[3]
        })

def load_files(cur, id):
    global chat
    data = cur.execute("SELECT content, name, extension, message_idx FROM files WHERE chat_id=?", (id, )).fetchall()
    for row in data:
        chat["files"].append({
            "content": row[0],
            "name": row[1],
            "extension": row[2],
            "message_idx": row[3]
        })

def save_chat(con, cur):
    # if the message is too short, or more precisely, it's just the role message and the
    # first user message, there was most likely some error and there's no need to save it.
    if chat["is_loaded"]:

        # deletes the chat, but the now message is saved under a newer number.
        cur.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM chats WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM images WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM files WHERE chat_id=?", (chat["id"], ))
        con.commit()
        # this is totally unecessary since chat["id"] is always true in this scenario because it's loaded but pyright is annoying
        max_chat_id = 0
        if chat["id"]: max_chat_id = chat["id"] - 1


    else:
        max_chat_id = cur.execute(
            "SELECT MAX(chat_id) AS max FROM chats").fetchone()[0]
        if not max_chat_id:
            max_chat_id = 0

    if not chat["description"]:
        chat["description"] = "Unnamed one"

    dalle = 1 if chat["dalle"] else 0
    bash = 1 if chat["bash"] else 0
    autosave = 1 if chat["autosave"] else 0


    cur.execute("INSERT INTO chats (chat_id, description, model, provider, vision_enabled, temperature, max_tokens, frequency_penalty, dalle, bash, autosave) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (max_chat_id+1, chat["description"], chat["model"], chat["provider"], chat["vision_enabled"], chat["temperature"], chat["max_tokens"],chat["frequency_penalty"], dalle, bash, autosave))
    con.commit()


    for message in chat["all_messages"]:
        cur.execute("INSERT INTO chat_messages (chat_id, role, message) VALUES (?, ?, ?)",
            (max_chat_id+1, message["role"], message["content"]))
        con.commit()

    for image in chat["images"]:
        cur.execute("INSERT INTO images (content, name, extension, chat_id, message_idx) VALUES (?, ?, ?, ?, ?)",
            (image["content"], image["name"], image["extension"], max_chat_id+1, image["message_idx"], ))
        con.commit()

    for file in chat["files"]:
        cur.execute("INSERT INTO files (content, name, extension, chat_id, message_idx) VALUES (?, ?, ?, ?, ?)",
            (file["content"], file["name"], file["extension"], max_chat_id+1, file["message_idx"], ))
        con.commit()

    update_chat_ids(con, cur)



def delete_chat(con, cur):
    global chat
    if chat["is_loaded"]:
        cur.execute("DELETE FROM chats WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM images WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM files WHERE chat_id=?", (chat["id"], ))
        con.commit()
        update_chat_ids(con, cur)
    exit()


def update_chat_ids(con, cur):
    old_chat_ids = cur.execute("SELECT chat_id FROM chats;").fetchall()

    # this checks if there are no chats left in the db
    if not old_chat_ids or not old_chat_ids[0]: return

    old_chat_ids_list = [id[0] for id in old_chat_ids]

    # ok so the basic idea here is that we just check if the chat_ids are in order, which should match perfectly with
    # idx + 1, given that the old_versions of the chat is deleted and the new one is inserted at the very end of the table. And this also works for keeping them succint!
    if old_chat_ids_list != sorted(old_chat_ids_list) or old_chat_ids_list[0] != 1 or not is_succinct(old_chat_ids_list):
        for (idx, chat_id) in enumerate(old_chat_ids_list):
            if idx+1 != chat_id:
                cur.execute("UPDATE chats SET chat_id = ? WHERE chat_id = ?",
                    (idx+1, chat_id, ))
                cur.execute("UPDATE images SET chat_id = ? WHERE chat_id = ?",
                    (idx+1, chat_id, ))
                cur.execute("UPDATE files SET chat_id = ? WHERE chat_id = ?",
                    (idx+1, chat_id, ))
                cur.execute("UPDATE chat_messages SET chat_id = ? WHERE chat_id = ?",
                    (idx+1, chat_id, ))
                con.commit()



def apply_defaults():
    global chat
    if defaults.get("color"):
        chat["color"] = defaults["color"]
    if defaults.get("model"):
        change_model(defaults["model"], providers)
    if defaults.get("mode"):
        chat["mode"] = defaults["mode"]["name"]
    if "smooth_streaming" in defaults:
        chat["smooth_streaming"] = defaults["smooth_streaming"]

def change_defaults(target, newValue):
    match target:
        case "color":
            try:
                defaults["color"] = newValue
                alert(f"Changed default color to {newValue}")
            except:
                alert("Color is not valid")
        case "model":
            valid_model = False
            for model in models:
                if model["shortcut"] == newValue or model["name"] == newValue:
                    defaults["model"] = model
                    valid_model = True
                    alert(f"Changed default model to {model['name']}")
                    break
            if not valid_model:
                alert("Invalid model")
        case "mode":
            valid_mode = False
            for mode in modes:
                if mode["shortcut"] == newValue or mode["name"] == newValue:
                    defaults["mode"] = mode
                    valid_mode = True
                    alert(f"Changed default mode to {mode['name']}")
                    break
            if not valid_mode:
                alert("Invalid mode")
        case "smooth_streaming":
            try:
                val = newValue.lower() if isinstance(newValue, str) else newValue
                if val in ["true", "false", True, False]:
                    defaults["smooth_streaming"] = val == "true" or val is True
                    alert(f"Changed default smooth_streaming to {defaults['smooth_streaming']}")
                else:
                    alert("Value must be 'true' or 'false'")
            except Exception as e:
                alert(f"Invalid value for smooth_streaming: {e}")
            # Save to file
            with open(path + "defaults.json", "w") as def_file:
                def_file.write(json.dumps(defaults, indent=4))
            return
        case _:
            alert("Invalid default property")

    with open(path + "defaults.json", "w") as def_file:
        def_file.write(json.dumps(defaults, indent=4))
