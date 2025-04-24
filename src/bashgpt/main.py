#!/Users/petar/Projects/Python/BashGPT/env/bin/python
import base64
import os
import shlex
import curses
import threading
from io import BytesIO
from time import sleep
from sys import argv
from typing import cast, Literal
from subprocess import run

import httpx
from PIL import ImageGrab, Image
import vlc

from bashgpt.autonomous import auto_system_message, parse_auto_message
from bashgpt.bash import bash, bash_system_message
from bashgpt.chat import add_message_to_chat, chat, load_chat, load_images, load_files, change_model, save_chat, delete_chat, apply_defaults, change_defaults, defaults
from bashgpt.dalle import dalle_mode, dalle_system_message
from bashgpt.db_and_key import setup_db
from bashgpt.get_file import get_file
from bashgpt.load_defaults import load_defaults
from bashgpt.data_loader import data_loader
from bashgpt.terminal_codes import terminal
from bashgpt.util_functions import (alert, is_succinct, loading_bar, parse_md, use_temp_file)
from bashgpt.whisper import record, whisper
from bashgpt.api import client, googleai, get_and_print_response
from bashgpt.path import get_path


all_messages = chat["all_messages"]
(modes, models, providers) = data_loader()

#this has honestly been one of the hardest part of this project. Without the library, I had to resort to really big workarounds
path = get_path()
audio_location = path + "audio.wav"

def main():
    apply_defaults()

    con = cur = None

    if len(argv) > 1:
        status = input_with_args()
        if status != 0:
            exit()  # Exit if there was an error

    if chat.get('load_last'):
        (con, cur) = setup_db(path)
        last_id = cur.execute("SELECT MAX(chat_id) FROM chat_messages").fetchone()[0]
        if last_id:
            load_chat(cur, last_id)
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

        if chat["autosave"]:
            if not chat["is_loaded"]:
                (con, cur) = setup_db(path)
            save_chat(con, cur)

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
                print("Saving chat. Hold on a minute...")
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
            message = use_temp_file("")
            print(message, end="\n\n")
            return message

        case "v":
            try:
                message = voice_input()
            except:
                alert("Recording doesn't work on you device.")
                message = use_temp_file("")
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
                        change_model(model, providers)
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

        case "continue" | "con":
            print_chat(newline_in_the_end=False)
            print(" ", end="")
            get_and_print_response()
            return 1




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

        case "rp" | "reprint":
            print_chat()
            return 1

        case "max_tokens" | "mt":
            if len(command) == 2:
                try:
                    num = int(command[1])
                    if num >= 1:
                        chat["max_tokens"] = num
                        alert(f"Max generated tokens set to {num}")
                except ValueError:
                    alert("Imput a valid integer larger than 0")
            return 1

        case "temp" | "temperature":
            if len(command) == 2:
                try:
                    num = float(command[1])
                    if num >= 0 and num <= 2:
                        chat["temperature"] = num
                        alert(f"Temperature set to {num}")
                except ValueError:
                    alert("Imput a valid float from 0 to 2")
            return 1

        case "fp" | "frequency_penalty":
            if len(command) == 2:
                try:
                    num = float(command[1])
                    if num >= 0 and num <= 2:
                        chat["frequency_penalty"] = num
                        alert(f"Frequency penalty set to {num}")
                except ValueError:
                    alert("Imput a valid float from 0 to 2")
            return 1
        case "autosave":
            chat["autosave"] = not chat["autosave"]
            alert("Autosave is " + "on" if chat["autosave"] else "off")
            return 1

        case "info":
            alert(f"max_tokens: {chat["max_tokens"]}\ntemperature: {chat["temperature"]}\nfrequency_penalty: {chat["frequency_penalty"]}\nautosave: {chat["autosave"]}\nmodel: {chat["model"]} ({chat["provider"]})")
            return 1

        case _:
            alert("Invalid command")
            return 1


def image_to_base64_and_info(img: Image.Image, default_name="pasted image") -> dict:
    fmt = img.format or "PNG"  # default to PNG if unknown
    ext = fmt.lower()

    buffer = BytesIO()
    img.save(buffer, format=fmt)
    img_bytes = buffer.getvalue()

    b64_bytes = base64.b64encode(img_bytes)
    b64_str = b64_bytes.decode("utf-8")

    filename = f"{default_name}.{ext}"

    return {
        "base64": b64_str,
        "extension": ext,
        "name": filename,
    }


def get_image(image_url):
    global chat

    if image_url == "paste":
        image = ImageGrab.grabclipboard()

        if isinstance(image, Image.Image):
            image_data = image_to_base64_and_info(image)

            chat["images"].append({
                "content" : image_data["base64"],
                "name": image_data["name"],
                "extension": image_data["extension"],
                "message_idx": len(chat["all_messages"])
                })
            alert(f"Image attached: \033[3m{image_data['name']}\033[0m")
            return

        else:
            alert("Could not get image from clipboard")
            return


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



def choose_chat(cur):
    options = cur.execute(
        "SELECT chat_id, description FROM chats").fetchall()
    print()
    option_ids = []
    for option in options:
        option_ids.append(option[0])
        print(f"{option[0]}: {option[1]}")

    while 1:
        option_input = input("\nWhich chat do you want to continue? ")
        if option_input.isnumeric() and (choice := int(option_input)) in option_ids:
            load_chat(cur, choice)
            print_chat()
            break

VoicesLiteral = Literal['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']

def is_valid_voice(value: str) -> bool:
    allowed_values = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']
    return value in allowed_values

def speak(message, voice="nova"):
    try:
        speech_file_path = path + "speech.mp3"
        if not is_valid_voice(voice):
            voice="nova"
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice=voice, # type: ignore
            input=message,
        ) as response:
            response.stream_to_file(speech_file_path)
            player = vlc.MediaPlayer(speech_file_path)
            player.play() # type: ignore
    except Exception as e:
        alert(f"Error: {e}")



def print_chat(newline_in_the_end = True):
    global chat
    global terminal

    print("\x1b\x5b\x48\x1b\x5b\x32\x4a")

    for idx, message in enumerate(chat["all_messages"]):
        if newline_in_the_end == False and idx == len(chat["all_messages"]) - 1 and message["role"] == "assistant":
            print(parse_md(terminal[chat["color"]] + message["content"] + terminal["reset"]), end="")
            return
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
        if mode["description"] == chat["all_messages"][0]["content"]:
            return mode["name"]

    return "custom"


def help_me():
    print("Valid usage:\n dp -bs 'delete every file from my downloads folder' (it will work, do not try it).\n")
    print("Also valid usages:\n dp (this brings you to the the history tab\n dp 'what is the height of the Eiffel Tower'\n dp --gpt-4 -h 'Why did you lose to Chrollo?'\n")
    print("You can also add a new mode like this: dp --add-mode 'You are a DumbGPT. You get every question wrong.\n")

    available_modes = "Available modes: "
    for mode in modes:
        available_modes += f'{mode["shortcut"]} ({mode["name"]} mode), '

    available_modes = available_modes.strip(" ,") + "."
    print(available_modes)


def get_models(stdscr):
        stdscr.clear()
        menu = [key for key in providers.keys()]
        menu.append("google")
        menu.append("anthropic")
        menu.append("exit")
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
            api_key_name = providers[provider_choice]["api_key_name"]
            base_url = providers[provider_choice]["base_url"]
            raw_list = client.with_options(
                    base_url=base_url,
                    api_key=os.getenv(api_key_name)
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
                    if chat["provider"] not in ["google", "anthropic"]:
                        chat.update(providers[provider_choice])
                    return True

        curses.flushinp()
        return False


def edit_file(file_path):
    editor = os.environ.get('EDITOR', 'nvim')
    try:
        run([editor, path + file_path], check=True)
    except:
        alert("Unable to open editor. Check your EDITOR environment variable.")
    finally:
        return 1


def input_with_args():
    global chat

    if len(argv) > 4:
        print("Too many arguments. For help with usage type 'dp help'.")
        return 1

    elif len(argv) == 2:
        if argv[1] in ("--help","-h"):
            help_me()
            return 1

        elif argv[1] in ("--load-last", "-ll"):
            chat['load_last'] = True
            return 0

        elif argv[1] == "--server":
            from bashgpt.server import server
            import webbrowser
            import threading

            # Start server in a thread
            threading.Thread(target=server, daemon=True).start()

            # Open browser after a short delay to allow server to start
            def open_browser():
                sleep(1)  # Give the server a moment to start
                webbrowser.open("http://127.0.0.1:5000")

            threading.Thread(target=open_browser).start()

            # Keep the main thread running
            try:
                while True:
                    sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down server...")

            return 1

        if argv[1] == "--models":
            edit_file("/models.json")
        if argv[1] == "--modes":
            edit_file("/modes.json")
        if argv[1] == "--defaults":
            edit_file("/defaults.json")


        elif argv[1].startswith("-"):
            for model in models:
                if argv[1] == "--" + model["name"] or argv[1] == "-" + model["shortcut"]:
                    change_model(model, providers)
                    return 0

        else:
            prompt = argv[1]
            add_message_to_chat("system", defaults["mode"]["description"])
            add_message_to_chat("user", prompt)
            return 0

    elif len(argv) == 3:
        if argv[1] == "--server" and argv[2] in ("--load-last", "-ll"):
            from bashgpt.server import server
            import webbrowser
            import threading
            import sqlite3
            import time

            # Get the last chat ID
            con = sqlite3.connect(path + "history.db")
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            last_id = cur.execute("SELECT MAX(chat_id) FROM chat_messages").fetchone()[0]
            cur.close()
            con.close()

            if not last_id:
                print("No previous chats found. Opening homepage instead.")
                last_id = ""

            # Start server in a thread
            threading.Thread(target=server, daemon=True).start()

            # Open browser with last chat after a short delay
            def open_browser():
                time.sleep(1)  # Give the server a moment to start
                url = f"http://127.0.0.1:5000/chat/{last_id}" if last_id else "http://127.0.0.1:5000"
                webbrowser.open(url)

            threading.Thread(target=open_browser).start()

            # Keep the main thread running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down server...")

            return 1

        if argv[1] == "--new-mode":
            chat["mode"] = "custom"
            add_message_to_chat("system", argv[2])
            alert("\nCustom mode added")
            return 0
        else:
            model_selected = False
            mode_selected = False
            for model in models:
                if ("-" + model["shortcut"]) == argv[1] or ("--" + model["name"]) == argv[1]:
                    model_selected = True
                    change_model(model, providers)
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
                change_model(model, providers)
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
    new_message = use_temp_file(chat["all_messages"][-id]["content"])
    chat["all_messages"][-id]["content"] = new_message

def nuclear(con, cur):
    cur.execute("DELETE FROM chat_messages")
    con.commit()
    exit()

if __name__ == "__main__":
    main()
