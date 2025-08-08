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
    
    [description, model_name, provider_name, vision_enabled, temperature, max_tokens, frequency_penalty, dalle, bash, autosave] = settings_query[0]

    chat["id"] = id
    chat["is_loaded"] = True
    chat["temperature"] = temperature
    chat["max_tokens"] = max_tokens
    chat["frequency_penalty"] = frequency_penalty
    chat["description"] = description
    chat["dalle"] = bool(dalle)
    chat["bash"] = bool(bash)
    chat["autosave"] = bool(autosave)

    # Reload models, modes, providers to get the latest configurations
    modes, models, providers = data_loader()

    # Find the complete model object from the reloaded models list
    selected_model = None
    for m in models:
        if m["name"] == model_name and m["provider"] == provider_name:
            selected_model = m
            break

    if selected_model:
        change_model(selected_model, providers)
    else:
        # Fallback if model not found in current models.json (e.g., deleted or renamed)
        change_model({"name": model_name, "provider": provider_name, "vision_enabled": bool(vision_enabled)}, providers)

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



def export_chat_by_id(cur, chat_id: int) -> dict:
    """Serialize a single chat with messages, images, and files to a dict."""
    # Chat metadata
    chat_row = cur.execute(
        "SELECT chat_id, description, model, provider, vision_enabled, temperature, max_tokens, frequency_penalty, dalle, bash, autosave FROM chats WHERE chat_id=?",
        (chat_id,),
    ).fetchone()

    if not chat_row:
        raise ValueError(f"Chat id {chat_id} not found")

    # Messages
    messages = [
        {"role": row[0], "content": row[1]}
        for row in cur.execute(
            "SELECT role, message FROM chat_messages WHERE chat_id=? ORDER BY message_id ASC",
            (chat_id,),
        ).fetchall()
    ]

    # Images
    images = [
        {
            "content": row[0],
            "name": row[1],
            "extension": row[2],
            "message_idx": int(row[4]) if row[4] is not None else -1,
        }
        for row in cur.execute(
            "SELECT content, name, extension, chat_id, message_idx FROM images WHERE chat_id=?",
            (chat_id,),
        ).fetchall()
    ]

    # Files
    files = [
        {
            "content": row[0],
            "name": row[1],
            "extension": row[2],
            "message_idx": int(row[4]) if row[4] is not None else -1,
        }
        for row in cur.execute(
            "SELECT content, name, extension, chat_id, message_idx FROM files WHERE chat_id=?",
            (chat_id,),
        ).fetchall()
    ]

    exported = {
        "version": 1,
        "chat": {
            "chat_id": chat_row[0],
            "description": chat_row[1],
            "model": chat_row[2],
            "provider": chat_row[3],
            "vision_enabled": bool(chat_row[4]),
            "temperature": float(chat_row[5]),
            "max_tokens": int(chat_row[6]),
            "frequency_penalty": float(chat_row[7]),
            "dalle": bool(chat_row[8]),
            "bash": bool(chat_row[9]),
            "autosave": bool(chat_row[10]),
        },
        "messages": messages,
        "images": images,
        "files": files,
    }
    return exported


def export_all_chats(cur) -> dict:
    """Serialize all chats to a dict with a list of chat exports."""
    chat_ids = [row[0] for row in cur.execute("SELECT chat_id FROM chats ORDER BY chat_id ASC").fetchall()]
    exports = [export_chat_by_id(cur, cid) for cid in chat_ids]
    return {"version": 1, "chats": exports}


def import_chat_data(con, cur, data: dict) -> list[int]:
    """Import chats from a JSON-serializable dict. Returns list of new chat_ids.

    Accepts either a single-chat export (keys: chat, messages, images, files)
    or a multi-chat export with key 'chats' being a list of single-chat exports.
    """
    def _insert_single(single: dict) -> int:
        chat_meta = single.get("chat", {})
        messages = single.get("messages", [])
        images = single.get("images", [])
        files = single.get("files", [])

        # Determine next chat_id (append)
        max_chat_id = cur.execute("SELECT MAX(chat_id) FROM chats").fetchone()[0]
        new_chat_id = (max_chat_id or 0) + 1

        # Insert chat row
        cur.execute(
            "INSERT INTO chats (chat_id, description, model, provider, vision_enabled, dalle, bash, temperature, frequency_penalty, max_tokens, autosave) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                new_chat_id,
                chat_meta.get("description", f"Imported #{new_chat_id}"),
                chat_meta.get("model", chat["model"]),
                chat_meta.get("provider", chat["provider"]),
                1 if chat_meta.get("vision_enabled", chat.get("vision_enabled", False)) else 0,
                1 if chat_meta.get("dalle", False) else 0,
                1 if chat_meta.get("bash", False) else 0,
                float(chat_meta.get("temperature", chat.get("temperature", 0.7))),
                float(chat_meta.get("frequency_penalty", chat.get("frequency_penalty", 1))),
                int(chat_meta.get("max_tokens", chat.get("max_tokens", 4048))),
                1 if chat_meta.get("autosave", False) else 0,
            ),
        )
        con.commit()

        # Insert messages
        for m in messages:
            cur.execute(
                "INSERT INTO chat_messages (chat_id, role, message) VALUES (?, ?, ?)",
                (new_chat_id, m.get("role", "user"), m.get("content", "")),
            )
        con.commit()

        # Insert images
        for img in images:
            cur.execute(
                "INSERT INTO images (content, name, extension, chat_id, message_idx) VALUES (?, ?, ?, ?, ?)",
                (
                    img.get("content", ""),
                    img.get("name", "image"),
                    img.get("extension", "png"),
                    new_chat_id,
                    int(img.get("message_idx", -1)),
                ),
            )
        con.commit()

        # Insert files
        for f in files:
            cur.execute(
                "INSERT INTO files (content, name, extension, chat_id, message_idx) VALUES (?, ?, ?, ?, ?)",
                (
                    f.get("content", ""),
                    f.get("name", "file"),
                    f.get("extension", "txt"),
                    new_chat_id,
                    int(f.get("message_idx", -1)),
                ),
            )
        con.commit()

        return new_chat_id

    new_ids: list[int] = []
    if "chats" in data and isinstance(data["chats"], list):
        for single in data["chats"]:
            new_ids.append(_insert_single(single))
        update_chat_ids(con, cur)
        return new_ids
    else:
        new_id = _insert_single(data)
        update_chat_ids(con, cur)
        return [new_id]

def export_current_chat_dict() -> dict:
    """Export the in-memory current chat state to a JSON-serializable dict."""
    meta = {
        "chat_id": chat.get("id"),
        "description": chat.get("description", ""),
        "model": chat.get("model"),
        "provider": chat.get("provider"),
        "vision_enabled": bool(chat.get("vision_enabled", False)),
        "temperature": float(chat.get("temperature", 0.7)),
        "max_tokens": int(chat.get("max_tokens", 4048)),
        "frequency_penalty": float(chat.get("frequency_penalty", 1)),
        "dalle": bool(chat.get("dalle", False)),
        "bash": bool(chat.get("bash", False)),
        "autosave": bool(chat.get("autosave", False)),
    }
    return {
        "version": 1,
        "chat": meta,
        "messages": list(chat["all_messages"]),
        "images": list(chat["images"]),
        "files": list(chat["files"]),
    }

def overwrite_current_chat_from_import(single: dict) -> None:
    """Overwrite in-memory current chat with contents from a single-chat export dict."""
    global chat
    chat_meta = single.get("chat", {})
    messages = single.get("messages", [])
    images = single.get("images", [])
    files = single.get("files", [])

    # Preserve existing id if present to allow in-place save to DB
    current_id = chat.get("id")

    # Clear current content
    chat["all_messages"] = []
    chat["images"] = []
    chat["files"] = []

    # Apply settings
    description = chat_meta.get("description", chat.get("description", ""))
    model_name = chat_meta.get("model", chat.get("model"))
    provider_name = chat_meta.get("provider", chat.get("provider"))
    vision_enabled = bool(chat_meta.get("vision_enabled", chat.get("vision_enabled", False)))

    # Rebuild model via change_model for consistency
    selected_model = {"name": model_name, "provider": provider_name, "vision_enabled": vision_enabled}
    change_model(selected_model, providers)

    chat["description"] = description
    chat["temperature"] = float(chat_meta.get("temperature", chat.get("temperature", 0.7)))
    chat["max_tokens"] = int(chat_meta.get("max_tokens", chat.get("max_tokens", 4048)))
    chat["frequency_penalty"] = float(chat_meta.get("frequency_penalty", chat.get("frequency_penalty", 1)))
    chat["dalle"] = bool(chat_meta.get("dalle", False))
    chat["bash"] = bool(chat_meta.get("bash", False))
    chat["autosave"] = bool(chat_meta.get("autosave", False))

    # Messages, images, files
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        add_message_to_chat(role, content)

    chat["images"].extend(images)
    chat["files"].extend(files)

    # Restore ID and mark as loaded
    chat["id"] = current_id
    chat["is_loaded"] = bool(current_id)

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
