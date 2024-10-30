#!/Users/petar/Projects/Python/BashGPT/env/bin/python
import base64
import copy
import json
import os
import shlex
import tempfile
import curses
import threading
from time import sleep
from multiprocessing import Process
from pathlib import Path
from sys import argv
from typing import cast, Literal
from subprocess import run

import anthropic
import google.ai.generativelanguage as glm
import google.generativeai as googleai
import httpx
import vlc
from anthropic import Anthropic
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from openai import (APIConnectionError, APIError, APIResponseValidationError,
                    APIStatusError, APITimeoutError, AuthenticationError,
                    BadRequestError, ConflictError, InternalServerError,
                    NotFoundError, OpenAI, OpenAIError, PermissionDeniedError,
                    RateLimitError, UnprocessableEntityError)

from bashgpt.autonomous import auto_system_message, parse_auto_message
from bashgpt.bash import bash, bash_system_message
from bashgpt.chat import add_message_to_chat, chat
from bashgpt.dalle import dalle_mode, dalle_system_message
from bashgpt.db_and_key import setup_db
from bashgpt.get_file import get_file
from bashgpt.load_defaults import load_defaults
from bashgpt.modes_and_models import models, modes, models_path, modes_path
from bashgpt.terminal_codes import terminal
from bashgpt.util_functions import (alert, is_succinct, loading_bar, parse_md, use_text_editor)
from bashgpt.whisper import record, whisper


all_messages = chat["all_messages"]

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
googleai.configure(api_key=os.getenv("GOOGLEAI_API_KEY"))


#this has honestly been one of the hardest part of this project. Without the library, I had to resort to really big workarounds
path = str(Path(os.path.realpath(__file__)).parent) + "/"
audio_location = path + "audio.wav"

defaults = load_defaults(path)

def main():
    apply_defaults()

    con = cur = None

    if len(argv) > 1:
        status = quick_input()
        if status != 0:
            exit()  # Exit if there was an error

    if chat.get('load_last'):
        (con, cur) = setup_db(path)
        last_id = cur.execute("SELECT MAX(chat_id) FROM chat_messages").fetchone()[0]
        if last_id:
            load_chat(cur, last_id)
            load_images(cur, last_id)
            load_files(cur, last_id)
            print_chat()
        else:
            alert("No previous chats found.")
    else:
        if not all_messages:
            (con, cur) = setup_db(path)
            history_exists = cur.execute("SELECT MAX(message_id) AS max FROM chat_messages").fetchone()[0]

            if history_exists:
                history_input = input("\nWould you like to resume a previous conversation? (y/n) ").lower().strip()
                if history_input and history_input[0] == "y":
                    choose_chat(cur)
                    chat["mode"] = remember_mode()

            if not chat["all_messages"]:
                choose_mode()


    while True:
        if chat["auto_turns"] == 0:
            message = ""

            if not len(all_messages) == 2:
                message = input("You: ").strip()
        else:
            message = chat["auto_message"] if chat["auto_message"] else f"You have freedom for {chat['auto_turns']} more turns"
            chat["auto_message"] = ""
            print(f"You: {message}")

        print()

        if message and message[0] == "/" and len(message) > 1:
            output = command(message, con, cur)
            if output == 1: continue
            elif output == 2: message = ""
            elif output: message = output



        if (message):
            add_message_to_chat("user", message)

        get_and_print_response()

        if chat["bash"]:
            last_message = chat["all_messages"][-1]["content"]
            bash(last_message)

        if chat["dalle"]:
            threading.Thread(target=dalle_mode, args=[client]).start()

        if chat["auto_turns"] > 0:
            chat["auto_message"] = parse_auto_message(chat["all_messages"][-1]["content"])
            chat["auto_turns"] -= 1


def command(message, con, cur):
    command = shlex.split(message[1:])

    match command[0]:
        case "q":
            if len(command) == 1:
                if not chat["is_loaded"]:
                    (con, cur) = setup_db(path)
                save_chat(con, cur)
                exit()
            elif len(command) == 2:
                chat["description"] = command[1]
                if not chat["is_loaded"]:
                    (con, cur) = setup_db(path)
                save_chat(con, cur)
                exit()
            else:
                alert("Too many arguments")
                return 1

        case "q!":
            print("\033[1A", end="")
            exit()

        case "rm!":
            if chat["id"]:
                delete_chat(con, cur)
            else:
                print("\033[1A", end="")
                exit()

        case "nuclear!!!":
            nuclear(con, cur)

        case "l":
            message = use_text_editor("")
            print(message, end="\n\n")
            return message

        case "v":
            try:
                message = voice_input()
            except:
                alert("Recording doesn't work on you device.")
                message = use_text_editor("")
                print(message, end="\n\n")
            finally:
                return message

        case "dl":
            if len(command) == 1:
                delete_messages()

            elif (command[1] and command[1].isnumeric()):
                no_of_messages = int(command[1])
                delete_messages(no_of_messages)

            else:
                alert("Invalid argument for message deletion")
            return 1

        case "model":
            if (len(command) == 1):
                curses.wrapper(get_models)
            elif (len(command) == 2):
                is_a_model = False
                for model in models:
                    if model["name"] == command[1] or model["shortcut"] == command[1]:
                        change_model(model)
                        is_a_model = True
                        alert(f"Changed model to: {model['name']}")
                        break

                if not is_a_model:
                    alert("Model not found")

            else:
                alert("Invalid arguments for changing the model")
            return 1

        case "image" | "i":
            if len(command) == 2:
                get_image(command[1])
            else:
                alert("Invalid arguments")
            return 1

        case "file" | "f":
            if len(command) == 2:
                get_file(command[1])
            else:
                alert("Invalid arguments")
            return 1

        case "color":
            if len(command) == 2 and command[1] in terminal:
                chat["color"] = command[1]
                print_chat()
                alert(f"Changed color to {command[1]}")
            else:
                alert("Invalid color")
            return 1

        case "edit":
            if len(command) == 1:
                edit_message(1)
                print_chat()
            elif command[1] == "-1" or command[1] == "sys":
                edit_message(0)
                print_chat()

            elif len(command) == 2 and command[1].isnumeric():
                if int(command[1]) > len(chat["all_messages"]):
                    alert(f"Index too large. Max index is: {len(chat['all_messages'])}")
                else:
                    edit_message(int(command[1]))
                    print_chat()

            elif len(command) > 3:
                alert("Too many arguments")

            return 1

        case "rg":
            delete_messages(1)
            alert("Regenerating message")
            print_chat()

            return 2


        case "speak":
            if len(command) == 2:
                voice = command[1]
                validated_voice = cast(VoicesLiteral, voice)
                alert("Speech will begin shortly")
                threading.Thread(target=speak, args=[all_messages[-1]["content"], validated_voice]).start()
                alert("Invalid voice")
                return 1
            elif len(command) == 1:
                alert("Speech will begin shortly")
                threading.Thread(target=speak, args=[all_messages[-1]["content"]]).start()
                return 1
            alert("Invalid voice")

        case "cd" | "change-default":
            if len(command) == 3:
                change_defaults(command[1], command[2])
            else:
                alert("Invalid number of args")
            return 1

        case "auto":
            if len(command) == 2:
                try:
                    chat["auto_turns"] = int(command[1])
                except:
                    alert("Invalid number of turns")
            elif len(command) == 3:
                try:
                    chat["auto_turns"] = int(command[1])
                    return command[2]
                except:
                    alert("Invalid number of turns")


            else:
                alert("Invalid number of turns. Proper usage: /auto 5")
            return 1

        case "bash":
            alert(f"Bash has been turned {'off' if chat['bash'] else 'on'}.")
            chat["bash"] = not chat["bash"]
            return 1

        case "dalle":
            alert(f"Image generation has been turned {'off' if chat['dalle'] else 'on'}.")
            chat["dalle"] = not chat["dalle"]
            return 1

        case _:
            alert("Invalid command")
            return 1


def get_image(image_url):
    global chat
    clean_image_url = image_url.replace(r"\ ", " ")
    image_name = clean_image_url.split("/")[-1]

    #images from links can oftentimes have those variables like ?v=somethingblabla&
    #this will be a problem when trying to parse the image extension, well need to handle that
    try:
        question_idx = image_name.index("?")
        dot_idx = image_name.index(".")
        image_name = image_name[:question_idx] if dot_idx < question_idx else image_name
    except:
        pass

    image_extension = image_name.split(".")[-1]
    if image_extension == "jpg": image_extension = "jpeg"
    if image_extension not in ["jpeg", "png", "webp"]:
        alert("Invalid image format")
        return


    if clean_image_url[0:4] == "http":
        image = base64.b64encode(httpx.get(clean_image_url).content).decode("utf-8")
        chat["images"].append({
            "content" : image,
            "name": image_name,
            "extension": image_extension,
            "message_idx": len(chat["all_messages"])
            })
        alert(f"Image attached: \033[3m{image_name}\033[0m")

    elif os.path.isfile(clean_image_url):
        with open(clean_image_url, "rb") as image_file:
            image = base64.b64encode(image_file.read()).decode('utf-8')
            chat["images"].append({
                "content" : image,
                "name": image_name,
                "extension": image_extension,
                "message_idx" : len(chat["all_messages"]),
                })
            alert(f"Image attached: \033[3m{image_name}\033[0m")

    else:
        alert("Invalid url")


def apply_defaults():
    global chat
    if defaults["color"]:
        chat["color"] = defaults["color"]
    if defaults["model"]:
        change_model(defaults["model"])
    if defaults["mode"]:
        chat["mode"] = defaults["mode"]["name"]


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
        case _:
            alert("Invalid default property")

    with open(path + "defaults.json", "w") as def_file:
        def_file.write(json.dumps(defaults, indent=4))


def voice_input():
    print("\033[2A" + "        \r", end="")
    audio_location = record()
    print("You: ", end=" ")
    stop = threading.Event()
    bar_thread = threading.Thread(target=loading_bar, args=[chat, stop])

    transcription = whisper(audio_location)
    os.remove(audio_location)

    if stop.is_set() == False:
        stop.set()
        bar_thread.join()

    print(transcription + "\n")
    return transcription


def save_chat(con, cur):
    # if the message is too short, or more precisely, it's just the role message and the
    # first user message, there was most likely some error and there's no need to save it.
    if len(all_messages) > 2:
        print("Saving chat. Hold on a minute...")
        if chat["is_loaded"]:

            # deletes the chat, but the now message is saved under a newer number.
            cur.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat["id"], ))
            cur.execute("DELETE FROM images WHERE chat_id=?", (chat["id"], ))
            con.commit()
            # this is totally unecessary since chat["id"] is always true in this scenario because it's loaded but pyright is annoying
            max_chat_id = 0
            if chat["id"]: max_chat_id = chat["id"] - 1


        else:
            max_chat_id = cur.execute(
                "SELECT MAX(chat_id) AS max FROM chat_messages").fetchone()[0]
            if not max_chat_id:
                max_chat_id = 0

        if not chat["description"]:
            if discription:=generate_description(chat["all_messages"]):
                chat["description"] = discription


        for message in all_messages:
            cur.execute("INSERT INTO chat_messages (chat_id, role, message, description) VALUES (?, ?, ?, ?)",
                (max_chat_id+1, message["role"], message["content"], chat["description"], ))
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


def choose_chat(cur):
    options = cur.execute(
        "SELECT DISTINCT chat_id, description FROM chat_messages").fetchall()
    print()
    option_ids = []
    for option in options:
        option_ids.append(option[0])
        print(f"{option[0]}: {option[1]}")

    while 1:
        option_input = input("\nWhich message do you want to continue? ")
        if option_input.isnumeric() and (choice := int(option_input)) in option_ids:
            load_chat(cur, choice)
            load_images(cur, choice)
            load_files(cur, choice)
            print_chat()
            break

VoicesLiteral = Literal['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']

def is_valid_voice(value: str) -> bool:
    allowed_values = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
    return value in allowed_values

def speak(message, voice="nova"):
    try:
        speech_file_path = Path(__file__).parent / "speech.mp3"
        if not is_valid_voice(voice):
            voice="nova"
        response = client.audio.speech.create(
            model="tts-1",
            voice=cast(VoicesLiteral, voice),
            input=message
            )
        response.stream_to_file(speech_file_path)
        player = vlc.MediaPlayer(speech_file_path)
        player.play() # type: ignore
    except Exception as e:
        alert(f"Error: {e}")


def load_chat(cur, choice):
    data = cur.execute("SELECT role, message, description FROM chat_messages WHERE chat_id=?", (choice, )).fetchall()

    chat["id"] = choice
    chat["is_loaded"] = True
    chat["description"] = data[0][2]
    for row in data:
        add_message_to_chat(row[0], row[1])


def load_images(cur, id):
    data = cur.execute("SELECT content, name, extension, message_idx FROM images WHERE chat_id=?", (id, )).fetchall()
    for row in data:
        chat["images"].append({
            "content": row[0],
            "name": row[1],
            "extension": row[2],
            "message_idx": row[3]
        })

def load_files(cur, id):
    data = cur.execute("SELECT content, name, extension, message_idx FROM files WHERE chat_id=?", (id, )).fetchall()
    for row in data:
        chat["files"].append({
            "content": row[0],
            "name": row[1],
            "extension": row[2],
            "message_idx": row[3]
        })

# TODO: #13 modify this function so it works with the new system, where we put the image
# into the chat before we send it to the server.
def print_chat():
    global chat
    global terminal

    print("\x1b\x5b\x48\x1b\x5b\x32\x4a")

    for idx, message in enumerate(chat["all_messages"]):
        if message["role"] == "user":
            print("You: " + message["content"] + "\n")
            for image in chat["images"]:
                if idx == image["message_idx"]:
                    alert(f"Attached image: \033[3m{image['name']}\033[0m")
            for file in chat["files"]:
                if idx == file["message_idx"]:
                    alert(f"Attached file: \033[3m{file['name']}\033[0m")
        if message["role"] == "assistant":
            print(parse_md(terminal[chat["color"]] + message["content"] + terminal["reset"] + "\n"))


def remember_mode():
    for mode in modes:
        if mode["description"] == all_messages[0]["content"]:
            return mode["name"]

    return "custom"


def generate_description(all_messages):
    try:
        return client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "describe the chat using 10 words or less. For example: 'The culture of Malat', 'French words in War and peace', 'Frog facts', etc."},
                  {"role": "user", "content": f"human: {all_messages[1]['content']};\n ai: {all_messages[2]['content']}"}]).choices[0].message.content
    except:
        return "No description"


def help_me():
    print("Valid usage:\n dp -bs 'delete every file from my downloads folder' (it will work, do not try it).\n")
    print("Also valid usages:\n dp (this brings you to the the history tab\n dp 'what is the height of the Eiffel Tower'\n dp --gpt-4 -h 'Why did you lose to Chrollo?'\n")
    print("You can also add a new mode like this: dp --add-mode 'You are a DumbGPT. You get every question wrong.\n")

    available_modes = "Available modes: "
    for mode in modes:
        available_modes += f'{mode["shortcut"]} ({mode["name"]} mode), '

    available_modes = available_modes.strip(" ,") + "."
    print(available_modes)


def attach_images_anthropic_openai(all_messages):
    memo = {}
    messages_with_images = copy.deepcopy(all_messages, memo)
    for image in chat["images"]:
        if (curr_idx:=image["message_idx"]) < len(messages_with_images):
            image_data = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f'image/{image["extension"]}',
                    "data": image["content"]
                },
            } if chat["provider"] == "anthropic" else {
                "type": "image_url", "image_url": {
                    "url": f'data:image/{image["extension"]};base64,{image["content"]}'
                }
            }

            # this is for checking if the message already has an image attached
            if str(type(messages_with_images[curr_idx]["content"])) == "<class 'str'>":
                newValue = {"role": "user", "content": [
                    {"type": "text", "text": all_messages[curr_idx]["content"]},
                    image_data
                ]}
                messages_with_images[curr_idx] = newValue
            else:
                messages_with_images[curr_idx]["content"].append(newValue.append(newValue)) # type: ignore

    return messages_with_images


def attach_files(all_messages):
    global chat
    memo = {}
    all_messages_with_files = copy.deepcopy(all_messages, memo)
    for file in chat["files"]:
        added_text = f"'''\nuser attached {'webpage' if 'extension' == 'html' else 'file'}'" + file["name"] + "':\n" + file["content"] + "\n\n\n'''"
        all_messages_with_files[file["message_idx"]]["content"] = added_text + all_messages_with_files[file["message_idx"]]["content"]
    return all_messages_with_files


def get_openai_response(all_messages):
    all_messages = all_messages if not chat["vision_enabled"] else attach_images_anthropic_openai(all_messages)

    stream = client.with_options(
            base_url=chat["base_url"],
            api_key=os.getenv(chat["api_key_name"])
            ).chat.completions.create(
                max_tokens=2024,
                model=chat["model"],
                messages=all_messages,
                stream=True
                )

    return stream

def get_models(stdscr):
        stdscr.clear()
        menu = ["openai", "google", "anthropic", "openrouter", "hyperbolic", "together", "exit"]
        current_row = 0
        curses.start_color()
        curses.init_pair(1, curses.COLOR_CYAN, curses.COLOR_BLACK)
        provider_choice = ""
        model_choice = ""

        # Configure screen
        curses.curs_set(0)  # Hide cursor
        stdscr.keypad(1)    # Enable keypad

        # Window dimensions
        height, width = stdscr.getmaxyx()
        menu_window_height = height - 4  # Leave room for header and border

        def draw_menu(items, title, selected_idx, offset=0):
            stdscr.clear()
            # Draw title
            stdscr.attron(curses.color_pair(1))
            stdscr.addstr(0, 0, title, curses.A_BOLD)
            stdscr.attroff(curses.color_pair(1))

            # Draw items
            visible_items = min(menu_window_height, len(items))
            for idx in range(visible_items):
                list_idx = idx + offset
                if list_idx >= len(items):
                    break

                x = 0
                y = idx + 2

                if list_idx == selected_idx:
                    stdscr.attron(curses.A_REVERSE)
                    stdscr.addstr(y, x, str(items[list_idx])[:width-1])
                    stdscr.attroff(curses.A_REVERSE)
                else:
                    stdscr.addstr(y, x, str(items[list_idx])[:width-1])

            # Draw scroll indicators if necessary
            if offset > 0:
                stdscr.addstr(1, width-3, "↑")
            if offset + visible_items < len(items):
                stdscr.addstr(min(height-1, visible_items+2), width-3, "↓")

            stdscr.refresh()

        # Provider selection loop
        offset = 0
        while True:
            draw_menu(menu, "Select the provider:", current_row, offset)

            key = stdscr.getch()
            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
                if current_row < offset:
                    offset = current_row
            elif key == curses.KEY_DOWN and current_row < len(menu) - 1:
                current_row += 1
                if current_row >= offset + menu_window_height:
                    offset = current_row - menu_window_height + 1
            elif key == curses.KEY_ENTER or key in [10, 13]:
                if current_row == len(menu) - 1:  # Exit
                    return False
                else:
                    provider_choice = menu[current_row]
                    break

        # Reset for model selection
        current_row = 0
        offset = 0
        model_list = []

        if provider_choice == "google":
            try:
                model_list = [model.name for model in googleai.list_models()]
            except Exception as e:
                stdscr.addstr(0, 0, f"Error loading models: {str(e)}")
                stdscr.refresh()
                sleep(2)
                return False

        elif provider_choice == "anthropic":
            model_list = [
                'claude-3-5-sonnet-20241022',  # Fixed missing comma
                'claude-3-5-sonnet-20240620',
                'claude-3-opus-20240229',
                'claude-3-sonnet-20240229',
                'claude-3-haiku-20240307',
                'claude-2.1',
                'claude-2.0',
                'claude-instant-1.2'
            ]

        else:
            api_key_env = ""
            url = ""
            if provider_choice == "openai":
                api_key_env = "OPENAI_API_KEY"
                url = "https://api.openai.com/v1"
            if provider_choice == "openrouter":
                api_key_env = "OPENROUTER_API_KEY"
                url = "https://openrouter.ai/api/v1"
            if provider_choice == "hyperbolic":
                api_key_env = "HYPERBOLIC_API_KEY"
                url = "https://api.hyperbolic.xyz/v1"
            if provider_choice == "together":
                api_key_env = "TOGETHER_API_KEY"
                url = "https://api.together.xyz/v1"
            raw_list = client.with_options(
                    base_url=url,
                    api_key=os.getenv(api_key_env)
                    ).models.list()
            model_list = [str(model.id) for model in raw_list]

        model_list.append("exit")

        # Model selection loop
        while True:
            draw_menu(model_list, f"Select {provider_choice} model:", current_row, offset)

            key = stdscr.getch()
            if key == curses.KEY_UP and current_row > 0:
                current_row -= 1
                if current_row < offset:
                    offset = current_row
            elif key == curses.KEY_DOWN and current_row < len(model_list) - 1:
                current_row += 1
                if current_row >= offset + menu_window_height:
                    offset = current_row - menu_window_height + 1
            elif key == curses.KEY_ENTER or key in [10, 13]:
                if model_list[current_row] == "exit":
                    return False
                else:
                    model_choice = model_list[current_row]
                    chat["provider"] = provider_choice
                    chat["model"] = model_choice
                    return True

        curses.flushinp()
        return False

def get_anthropic_response(all_messages):
    all_messages = all if not chat["vision_enabled"] else attach_images_anthropic_openai(all_messages)

    stream = anthropic_client.messages.create(
        system=all_messages[0]["content"], # type: ignore
        max_tokens=2024,
        model=chat["model"],
        messages=all_messages[1:], # type: ignore
        stream=True)

    return stream

def get_google_response(all_messages):
    model = googleai.GenerativeModel(
        chat["model"],
        system_instruction=all_messages[0]["content"])
    all_messages = adapt_messages_to_google(all_messages)

    response = model.generate_content(
        all_messages,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        })
    return response

def get_ollama_response(all_messages):
    with httpx.stream(method="POST",
                      url="http://localhost:11434/api/chat",
                      json={
                          "model": chat["model"],
                          "messages": all_messages
                      },
                      timeout=None) as r:
        for chunk in r.iter_text():
            yield json.loads(chunk)["message"]["content"]




def adapt_messages_to_google(all_messages):
    new_all_messages = []
    for message in all_messages[1:]:
        new_message = {}

        new_message["role"] = message["role"]
        if new_message["role"] == "assistant": new_message["role"] = "model"

        new_message["parts"] = [glm.Part(text=message["content"])]
        new_all_messages.append(new_message)

    attach_glm_images(new_all_messages)

    return new_all_messages


def attach_glm_images(new_all_messages):
    for image in chat["images"]:
        # this -1 is here because we removed the system message previously
        if (curr_idx:=(image["message_idx"] - 1)) < len(new_all_messages):
            new_all_messages[curr_idx]["parts"].append(
                glm.Part(
                    inline_data=glm.Blob(
                        mime_type=f'image/{image["extension"]}',
                        data=base64.b64decode(image["content"])
                    )
                ),
            )

def attach_system_messages(all_messages):
    new_system_message = {
        "role": "system",
        "content": all_messages[0]["content"]
    }

    if chat["auto_turns"] > 0:
        new_system_message["content"] += ("\n" + auto_system_message + "Number of turns left: " + str(chat["auto_turns"]))
    if chat["bash"] is True:
        new_system_message["content"] += ("\n" + bash_system_message)
    if chat["dalle"] is True:
        new_system_message["content"] += ("\n" + dalle_system_message)


    if new_system_message["content"] == all_messages[0]["content"]:
        return all_messages
    else:
        new_all_messages = all_messages.copy()
        new_all_messages[0] = new_system_message
        return new_all_messages


def get_and_print_response():
    # I reversed this just to confuse you, dear reader (including myself, yes)
    all_messages = attach_files(chat["all_messages"]) if chat["files"] else chat["all_messages"]
    all_messages = attach_system_messages(all_messages)

    stop = threading.Event()
    bar_thread = threading.Thread(target=loading_bar, args=[chat, stop])
    bar_thread.start()

    errorMessage = ""

    try:
        match chat["provider"]:
            case "anthropic":
                stream = get_anthropic_response(all_messages)
            case "google":
                stream = get_google_response(all_messages)
            case "ollama":
                stream = get_ollama_response(all_messages)
            case _:
                stream = get_openai_response(all_messages)

        add_message_to_chat("assistant", "")

        print(terminal[chat["color"]], end="")

        try:
            for chunk in stream:
                if stop.is_set() == False:
                    stop.set()
                    bar_thread.join()
                text = ""
                if chat["provider"] == "anthropic":
                    if chunk.type == "content_block_delta": # type: ignore
                        text = chunk.delta.text # type: ignore
                        if not text: break
                    else:
                        continue
                elif chat["provider"] == "google":
                    text = chunk.text # type: ignore
                    if not text: break
                elif chat["provider"] == "ollama":
                    text = chunk
                    if not text: break
                else:
                    text = chunk.choices[0].delta.content # type: ignore
                    if not text:
                        continue

                print(text, end="", flush=True)
                chat["all_messages"][-1]["content"] += text # type: ignore

        except KeyboardInterrupt:
            print("\033[2D  ", end="")

    except (
        APIError,
        OpenAIError,
        ConflictError,
        NotFoundError,
        APIStatusError,
        RateLimitError,
        APITimeoutError,
        BadRequestError,
        APIConnectionError,
        AuthenticationError,
        InternalServerError,
        PermissionDeniedError,
        UnprocessableEntityError,
        APIResponseValidationError,
    ) as e:
        # bar.terminate()
        errorMessage += f"Error: {e}"
        alert(errorMessage)
        chat["all_messages"][-1]["content"] += errorMessage
        print(terminal["reset"] + "\n")
        return
    # except:
    #     bar.terminate()
    #     errorMessage += "Unknown error"
    #     alert(errorMessage)
    #     chat["all_messages"][-1]["content"] += errorMessage


    finally:
        print(terminal["reset"] + "\n")


def quick_input():
    global chat

    if len(argv) > 4:
        print("Too many arguments. For help with usage type 'dp help'.")
        return 1

    elif len(argv) == 2:
        if argv[1] == "--help" or argv[1] == "-h":
            help_me()
            exit()

        if argv[1] == "--load-last" or argv[1] == "-ll":
            chat['load_last'] = True
            return 0

        if argv[1] == "--models":
            editor = os.environ.get('EDITOR', 'nvim')
            try:
                run([editor, path + "/models.json"], check=True)
            except:
                alert("Unable to open editor. Check your EDITOR environment variable.")
            finally:
                return 1
        if argv[1] == "--modes":
            editor = os.environ.get('EDITOR', 'nvim')
            try:
                run([editor, path + "/modes.json"], check=True)
            except:
                alert("Unable to open editor. Check your EDITOR environment variable.")
            finally:
                return 1



        elif argv[1][0] == "-":
            for model in models:
                if argv[1] == "--" + model["name"] or argv[1] == "-" + model["shortcut"]:
                    change_model(model)
                    break

        else:
            prompt = argv[1]
            add_message_to_chat("system", defaults["mode"]["description"])
            add_message_to_chat("user", prompt)
            return 0

    elif len(argv) == 3:
        if argv[1] == "--new-mode":
            chat["mode"] = "custom"
            add_message_to_chat("system", argv[2])
            return 0
        else:
            model_selected = False
            mode_selected = False
            for model in models:
                if ("-" + model["shortcut"]) == argv[1] or ("--" + model["name"]) == argv[1]:
                    model_selected = True
                    change_model(model)
                    break

            if not model_selected:
                for mode in modes:
                    if ("-" + mode["shortcut"] == argv[1]) or ("--" + mode["name"] == argv[1]):
                        mode_selected = True
                        chat["mode"] = mode["name"]
                        add_message_to_chat("system", mode["description"])
                        break

            if not mode_selected:
                add_message_to_chat("system", defaults["mode"]["description"])

            add_message_to_chat("user", argv[2])
            return 0  # Success code

    elif len(argv) == 4:
        model_selected = False
        mode_selected = False

        for model in models:
            if ("-" + model["shortcut"]) == argv[1] or ("--" + model["name"]) == argv[1]:
                change_model(model)
                model_selected = True
                break

        for mode in modes:
            if ("-" + mode["shortcut"] == argv[2]) or ("--" + mode["name"] == argv[2]):
                chat["mode"] = mode["name"]
                add_message_to_chat("system", mode["description"])
                mode_selected = True
                break

        if not mode_selected:
            add_message_to_chat("system", defaults["mode"]["description"])

        add_message_to_chat("user", argv[3])
        return 0  # Success code



def delete_chat(con, cur):
    global chat
    if chat["is_loaded"]:
        cur.execute("DELETE FROM chat_messages WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM images WHERE chat_id=?", (chat["id"], ))
        cur.execute("DELETE FROM files WHERE chat_id=?", (chat["id"], ))
        con.commit()
        update_chat_ids(con, cur)
    exit()


def update_chat_ids(con, cur):
    old_chat_ids = cur.execute("SELECT DISTINCT chat_id FROM chat_messages;").fetchall()
    # this check if there are no chats left in the db
    if not old_chat_ids or not old_chat_ids[0]: return

    old_chat_ids_list = [id[0] for id in old_chat_ids]

    # ok so the basic idea here is that we just check if the chat_ids are in order, which should match perfectly with
    # idx + 1, given that the old_versions of the chat is deleted and the new one is inserted at the very end of the table. And this also words for keeping them succint!
    if old_chat_ids_list != sorted(old_chat_ids_list) or old_chat_ids_list[0] != 1 or not is_succinct(old_chat_ids_list):
        for (idx, chat_id) in enumerate(old_chat_ids_list):
            if idx+1 != chat_id:
                cur.execute("UPDATE images SET chat_id = ? WHERE chat_id = ?",
                    (idx+1, chat_id, ))
                cur.execute("UPDATE files SET chat_id = ? WHERE chat_id = ?",
                    (idx+1, chat_id, ))
                cur.execute("UPDATE chat_messages SET chat_id = ? WHERE chat_id = ?",
                    (idx+1, chat_id, ))
                con.commit()


def change_model(new_model):
    global chat

    chat["provider"] = new_model["provider"]
    chat["model"] = new_model["name"]
    chat["vision_enabled"] = new_model["vision_enabled"]

    match new_model["provider"]:
        case "openai":
            chat["api_key_name"] = "OPENAI_API_KEY"
            chat["base_url"] = "https://api.openai.com/v1"
        case "mistral":
            chat["api_key_name"] = "MISTRAL_API_KEY"
            chat["base_url"] = "https://api.mistral.ai/v1"
        case "together":
            chat["api_key_name"] = "TOGETHER_API_KEY"
            chat["base_url"] = "https://api.together.xyz"
        case "groq":
            chat["api_key_name"] = "GROQ_API_KEY"
            chat["base_url"] = "https://api.groq.com/openai/v1"
        case "anthropic":
            chat["api_key_name"] = "ANTHROPIC_API_KEY"
            chat["base_url"] = "https://api.anthropic.com/v1/messages"
        case "openrouter":
            chat["api_key_name"] = "OPENROUTER_API_KEY"
            chat["base_url"] = "https://openrouter.ai/api/v1"
        case "hyperbolic":
            chat["api_key_name"] = "HYPERBOLIC_API_KEY"
            chat["base_url"] = "https://api.hyperbolic.xyz/v1/"
        case "deepseek":
            chat["api_key_name"] = "DEEPSEEK_API_KEY"
            chat["base_url"] = "https://api.deepseek.com"


def choose_mode():
    global chat
    mode_input = input("What mode would you like? ").lower().strip()
    print()

    current_mode = defaults["mode"]
    for option in modes:
        if mode_input == option["name"] or mode_input == option["shortcut"]:
            current_mode = option
            break

    add_message_to_chat("system", current_mode["description"])
    chat["mode"] = current_mode["name"]


def delete_messages(number = 2):
    for _ in range(number):
        chat["all_messages"].pop()
        for idx, image in enumerate(chat["images"]):
            if image["message_idx"] == len(chat["all_messages"]):
                chat["images"].pop(idx)

        for idx, file in enumerate(chat["files"]):
            if file["message_idx"] == len(chat["all_messages"]):
                chat["files"].pop(idx)

    alert(f"Deleted {number} messages")
    print_chat()

def edit_message(id):
    global chat
    new_message = use_text_editor(chat["all_messages"][-id]["content"])
    chat["all_messages"][-id]["content"] = new_message

def nuclear(con, cur):
    cur.execute("DELETE FROM chat_messages")
    con.commit()
    exit()

if __name__ == "__main__":
    main()
