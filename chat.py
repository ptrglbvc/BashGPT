# disables the debug and info logging that is enabled by default by the cs50 and openai libraries.
# It turns out we have to do it at the very start, at least before we call the OpenAI() constructor and it starts doing it's logging thing. 
import logging
logging.disable(logging.DEBUG)
logging.disable(logging.INFO)

import threading
import os
import requests
import subprocess
import tempfile
import base64
import shlex
import json
from re import findall, sub
from sys import argv, platform
from pathlib import Path
from time import sleep
from multiprocessing import Process
import pprint

from modes_and_models import modes, models, short_mode
from db_and_key import setup_db
from whisper import record, whisper
from load_defaults import load_defaults

from openai import OpenAI
from anthropic import Anthropic
import vlc
import httpx

chat = {
        "all_messages": [],
        "images": [],
        "is_loaded": False,
        "id": None,
        "mode": "short", 
        "model": "gpt-3.5-turbo", 
        "vision_enabled": False,
        "api_key_name": "OPENAI_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "provider" : "openai",
        "color": "purple",
        "description": ""}
db = ""
defaults = load_defaults()

all_messages = chat["all_messages"]

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

terminal = {"purple": "\033[35m", 
            "red": "\033[31m",
            "blue": "\033[34m",
            "yellow": "\033[33m",
            "orange": "\033[38;5;214m",
            "bold": "\033[1m", 
            "reset": "\033[0m\033[?25h"
            }

#this has honestly been the hardest part of this project. Without the library, I had to resort to really big workarounds
path = str(Path(__file__).parent.resolve()) + "/"
another_one_location = path + "another_one.wav"
audio_location = path + "audio.wav"



def main():
    global db
    apply_defaults()

    if len(argv)>1:
        quick_input()

    # we don't need to load the history if we enter the app from the quick input mode. We only need to once we save
    if not all_messages:
        db = setup_db(path)
        history_exists = db.execute(("SELECT MAX(message_id) "
                                    "AS max FROM chat_messages"))[0]["max"] is not None 
        if history_exists:
            history_input = input(
                ("\nWould you like to resume a previous conversation? "
                "(y/n) ")).lower().strip()
            if history_input and history_input[0] == "y":
                choose_chat(db)
                chat["mode"] = remember_mode()
            else:
                choose_mode()

        else:
            choose_mode()
    

    while True:
        message = ""

        if not len(all_messages) == 2 or str(type(all_messages[-1]["content"])) == "<class 'list'>":
            message = input("You: ").strip()
        
        print()

        if message and message[0] == "/" and len(message) > 1:
            command = shlex.split(message[1:])
            # command = parse_command(message[1:])

            match command[0]:
                case "q":
                    if len(command) == 1:
                        if not chat["is_loaded"]:
                            db = setup_db(path)
                        save_chat(db)
                        exit()
                    elif len(command) == 2:
                        chat["description"] = command[1]
                        save_chat(db)
                        exit()
                    else:
                        alert("Too many arguments")
                        continue

                case "q!":
                    print("\033[1A", end="")
                    exit()

                case "rm!":
                    if chat["id"]:
                        delete_chat(db)
                    else:
                        print("\033[1A", end="")
                        exit()

                case "nuclear!!!":
                    nuclear(db)

                case "l": 
                    message = use_editor("")
                    print(message, end="\n\n")

                case "v":
                    try:
                        message = voice_input()
                    except:
                        alert("Recording doesn't work on you device.")
                        message = use_editor()
                        print(message, end="\n\n")

                case "dl":
                    if len(command) == 1:
                        delete_messages()

                    elif (command[1] and command[1].isnumeric()):
                        no_of_messages = int(command[1])
                        delete_messages(no_of_messages)
                    
                    else:
                        alert("Invalid argument for message deletion")
                    continue

                case "model":
                    if (len(command) == 2):
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
                    continue

                case "image":
                    if len(command) == 2:
                        get_image(command[1])
                    else:
                        alert("Invalid arguments")
                    continue

                case "color":
                    if len(command) == 2 and command[1] in terminal:
                        chat["color"] = command[1]
                        print_chat()
                        alert(f"Changed color to {command[1]}")
                    else:
                        alert("Invalid color")
                    continue

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
                    
                    continue

                case "rg":
                    delete_messages(1)
                    message = ""
                    alert("Regenerating message")
                    print_chat()
                
                case "speak":
                    if len(command) == 2 and (command[1] == "shimmer" or command[1] == "2"):
                        alert("Speech with begin shortly")
                        threading.Thread(target=speak, args=[all_messages[-1]["content"], "shimmer"]).start()
                        continue 
                    elif len(command) == 1:
                        alert("Speech with begin shortly")
                        threading.Thread(target=speak, args=[all_messages[-1]["content"]]).start()
                        continue
                    alert("Invalid voice")
                
                case "cd" | "change-default":
                    if len(command) == 3:
                        change_defaults(command[1], command[2])
                    else:
                        alert("Invalid number of args")
                    continue

                case _:
                    alert("Invalid command")
                    continue


        if (message):
            add_message_to_chat("user", message)

        get_and_print_response()

        if chat["mode"] == "bash":
            last_message = chat["all_messages"][-1]["content"]
            bash_mode(last_message)

        if chat["mode"] == "dalle":
            threading.Thread(target=dalle_mode, args=[]).start()


def add_message_to_chat(role, content):
    global chat
    chat["all_messages"].append({"role": role, "content": content})


def get_image(image_url):
    global chat
    clean_image_url = image_url.strip("'")
    image_name = clean_image_url.split("/")[-1]

    #images from links can oftentimes have those variables like ?v=somethingblabla&
    #this will be a problem when trying to parse the image extensio
    try:
        question_idx = image_name.index("?")
        dot_idx = image_name.index(".")
        image_name = image_name[:question_idx] if dot_idx < question_idx else image_name
    except:
        pass

    image_extension = image_name.split(".")[-1]
    if image_extension == "jpg": image_extension = "jpeg"


    if clean_image_url[0:4] == "http":
        image = base64.b64encode(httpx.get(clean_image_url).content).decode("utf-8")
        chat["images"].append({
            "url" : image, 
            "name": image_name, 
            "extension": image_extension,
            "message_idx": len(chat["all_messages"])
            })

    elif os.path.isfile(clean_image_url):
        with open(clean_image_url, "rb") as image_file:
            image = base64.b64encode(image_file.read()).decode('utf-8')
            chat["images"].append({
                "url" : image, 
                "name": image_name, 
                "extension": image_extension,
                "message_idx" : len(chat["all_messages"]),
                })

    else:
        alert("Invalid url")


def apply_defaults():
    global chat
    if defaults["color"]:
        chat["color"] = defaults["color"]
    if defaults["model"]:
        change_model(defaults["model"])



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
                    break
            if not valid_model:
                alert("Invalid model")
        case _:
            alert("Invalid default property")
    
    with open(path + "defaults.json", "w") as def_file:
        def_file.write(json.dumps(defaults, indent=4))

                


def voice_input():
    print("\033[2A" + "        \r", end="")
    audio_location = record()
    print("You: ", end=" ")
    thred = Process(target=loading_bar, args=[chat])
    thred.start()

    transcription = whisper(audio_location)

    thred.terminate()
    return_cursor_and_overwrite_bar()

    print(transcription + "\n")
    return transcription

def save_chat(db):
    global chat
    if not db:
        db = setup_db(path)
    # if the message is too short, or more precisely, it's just the role message and the
    # first user message, there was most likely some error and there's no need to save it.
    if len(all_messages) > 2:
        print("Saving chat. Hold on a minute...")
        if chat["is_loaded"]:

            # deletes the chat, but the now message is saved under a newer number.
            db.execute("DELETE FROM chat_messages WHERE chat_id=?", chat["id"])
            db.execute("DELETE FROM images WHERE chat_id=?", chat["id"])
            max_chat_id = chat["id"] - 1

        else:
            max_chat_id = db.execute(
                "SELECT MAX(chat_id) AS max FROM chat_messages")[0]["max"]
            if not max_chat_id:
                max_chat_id = 0

        if not chat["description"]:
            chat["description"] = generate_description(all_messages)

        for message in all_messages:
            db.execute("INSERT INTO chat_messages (chat_id, user_name, message, description) VALUES (?, ?, ?, ?)",
                max_chat_id+1, message["role"], message["content"], chat["description"])
        
        for image in chat["images"]:
            db.execute("INSERT INTO images (url, name, extension, chat_id, message_idx) VALUES (?, ?, ?, ?, ?)",
                image["url"], image["name"], image["extension"], max_chat_id+1, image["message_idx"])

        update_chat_ids(db)

def choose_chat(db):
    global chat
    options = db.execute(
        "SELECT DISTINCT chat_id, description FROM chat_messages")
    print()
    option_ids = []
    for option in options:
        option_ids.append(option["chat_id"])
        print(f"{option['chat_id']}: {option['description']}")

    while 1:
        option_input = input("\nWhich message do you want to continue? ")
        if option_input.isnumeric() and (choice := int(option_input)) in option_ids:
            load_chat(db, choice)
            load_images(db, choice)
            print_chat()
            break
    

def speak(message, voice="nova"):
    speech_file_path = Path(__file__).parent / "speech.mp3"
    with client.audio.speech.create(
        model="tts-1-hd",
        voice=voice,
        input=message
    ) as response:
        response.stream_to_file(speech_file_path)
        player = vlc.MediaPlayer(speech_file_path)
        player.play()


def load_chat(db, choice):
    global chat
    data = db.execute("SELECT * FROM chat_messages WHERE chat_id=?", choice)

    chat["id"] = choice 
    chat["is_loaded"] = True
    chat["description"] = data[0]["description"]
    for row in data:
        add_message_to_chat(row["user_name"], row["message"])


def load_images(db, id):
    data = db.execute("SELECT * FROM images WHERE chat_id=?", id)
    for row in data:
        chat["images"].append({
            "url": row["url"],
            "name": row["name"],
            "extension": row["extension"],
            "message_idx": row["message_idx"]
        })


def print_chat():
    global chat
    global terminal

    print("\x1b\x5b\x48\x1b\x5b\x32\x4a")

    for message in chat["all_messages"]:
        if message["role"] == "user":
            if str(type(message["content"])) == "<class 'str'>":
                print("You: " + message["content"] + "\n")
            else:
                for item in message["content"]:
                    if item["type"] == "text":
                        print("You: " + item["text"] + "\n")
                for item in message["content"]:
                    if item["type"] == "image_url":
                        image_name = item["image_url"]["url"].split("/")[-1]
                        alert(f"Attached image: {image_name}")
        if message["role"] == "assistant":
            print(parse_md(terminal[chat["color"]] + message["content"] + terminal["reset"] + "\n"))

def parse_md(text):
    bold_text = sub(r'\*\*(.*?)\*\*|__(.*?)__', r'\033[1m\1\2\033[22m', text)
    italic_text = sub(r'\*(.*?)\*|_(.*?)_', r'\033[3m\1\2\033[23m', bold_text)

    return italic_text
        

def alert(text):
    print(terminal["red"] + terminal["bold"] + text + terminal["reset"] + "\n")


def remember_mode():
    for mode in modes:
        if mode["description"] == all_messages[0]["content"]:
            return mode["name"]
    
    if short_mode == all_messages[0]["content"]:
        return "short"
    
    return "custom"


def generate_description(all_messages):
    try:
        return client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "describe the message using 12 words or less. For example: 'The culture of Malat', 'French words in War and peace', 'Frog facts', etc."},
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


def attach_images(all_messages):
    global chat
    messages_with_images = all_messages.copy()
    for image in chat["images"]:
        if (curr_idx:=image["message_idx"]) < len(messages_with_images):
            image_data = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f'image/{image["extension"]}',
                    "data": image["url"]
                },
            } if chat["provider"] == "anthropic" else {
                "type": "image_url", "image_url": {
                    "url": f'data:image/{image["extension"]};base64,{image["url"]}'
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
                messages_with_images[curr_idx]["content"].append(newValue.append(newValue))
    
    return messages_with_images



def get_and_print_response():
    global chat
    global terminal 
    system_message = chat["all_messages"][0]["content"]
    all_messages = chat["all_messages"] if not chat["vision_enabled"] else attach_images(chat["all_messages"])

    bar = Process(target=loading_bar, args=[chat])
    bar.start()

    stream = client.with_options(
        base_url=chat["base_url"], 
        api_key=os.getenv(chat["api_key_name"])
        ).chat.completions.create(
            max_tokens=2024, 
            model=chat["model"], 
            messages=all_messages, 
            stream=True
            ) if chat["provider"] != "anthropic" else anthropic_client.messages.create(
                system=system_message,
                max_tokens=2024, 
                model=chat["model"], 
                messages=all_messages[1:], 
                stream=True)

    add_message_to_chat("assistant", "")
    bar.terminate()

    print("\b" + terminal[chat["color"]], end="")

    try:
        formatting = {"is_bold": False, "is_itallic": False, "is_code": False}
        for chunk in stream:
            text = ""
            if chat["provider"] == "anthropic":
                if chunk.type == "content_block_delta":
                    text = chunk.delta.text
                else: 
                    continue
            else:
                text = chunk.choices[0].delta.content
                if not text:
                    continue

            formatted_text = parse_md_while_streaming(text, formatting)

            print(formatted_text, end="")
            chat["all_messages"][-1]["content"] += text

    except KeyboardInterrupt:
        print("\033[2D  ", end="")
        

    print(terminal["reset"] + "\n")

def parse_md_while_streaming(text, formatting):
    ft = text
    if text == '``':
        ft = text
    if "```" in text or "`" in text:
        formatting["is_code"] = not formatting["is_code"]
        ft = text
    
    if not formatting["is_code"]:
        if "***" in text:
            ft = text.replace(
                "***", "\033[22m\033[23m") if (formatting["is_bold"] and formatting["is_itallic"]
                    ) else text.replace("***", "\033[1m\033[3m")
            formatting["is_bold"] = not formatting["is_bold"]
            formatting["is_itallic"] = not formatting["is_itallic"]
        if "___" in text:
            ft = text.replace(
                "___", "\033[22m\033[23m") if (formatting["is_bold"] and formatting["is_itallic"]
                    ) else text.replace("___", "\033[1m\033[3m")
            formatting["is_bold"] = not formatting["is_bold"]
            formatting["is_itallic"] = not formatting["is_itallic"]
        elif "**" in text:
            ft = text.replace("**", "\033[22m") if formatting["is_bold"] else text.replace("**", "\033[1m")
            formatting["is_bold"] = not formatting["is_bold"]
        elif "__" in text:
            ft = text.replace("__", "\033[22m") if formatting["is_bold"] else text.replace("__", "\033[1m")
            formatting["is_bold"] = not formatting["is_bold"]
        # The * and _ are a problem because we cannot know without the further context whether it's is for lists or italic
        # So the best solution is to just leave it as is, and parse it only if the user reprints the message for one reason or another

    return ft


def bash_mode(message):
    all_parts = message.split("```")
    if len(all_parts) > 1:
        commands = all_parts[1::2]
        for command in commands:

            if command.strip().startswith("bash"):
                command = command.strip()[4:]
            if command.strip().startswith("zsh"):
                command = command.strip()[3:]

            try:
                output = execute_command(command)
                if output.strip():
                    nicely_formated_output = "\033[1m\033[31mShell: "+output+"\033[0m"
                    print(nicely_formated_output)
                    if len(output)<1000:
                        add_message_to_chat("user", "Shell: " + output)
                    
            except Exception:
                pass


def quick_input():
    global chat

    # check for too many args
    if len(argv)>4:
        print("Too many arguments. For help with usage type 'dp help'.")
        return 0

    elif len(argv)==2:
        if argv[1] == "--help" or argv[1] == "-h":
            help_me()
            exit()
        
        if argv[1] == "--load-last" or argv[1] == "-ll":
            global db
            db = setup_db(path)
            last_id = db.execute("SELECT MAX(chat_id) FROM chat_messages")[0]["MAX(chat_id)"]
            load_chat(db, last_id)
            load_images(db, last_id)
            print_chat()
            
            
        
        elif argv[1][0]=="-":
            for model in models:
                if argv[1] == "--" + model["name"] or argv[1] == "-" + model["shortcut"]:
                    change_model(model)

        else:
            prompt = argv[1]
            add_message_to_chat("system", short_mode)
            add_message_to_chat("user", prompt)

    elif len(argv) == 3:
        if argv[1] == "--new-mode":
            chat["mode"] = "custom"
            add_message_to_chat("system", argv[2])

        else:
            for mode in modes:
                if ("-" + mode["shortcut"] == argv[1]) or ("--" + mode["name"] == argv[1]):
                    chat["mode"] = mode["name"]
                    add_message_to_chat("system", mode["description"])
                    break
            
            if chat["mode"] == "short":
                for model in models:
                    if ("-" + model["shortcut"]) == argv[1] or ("--" + model["name"]) == argv[1]:
                        change_model(model)
                        add_message_to_chat("system", short_mode)
                        break
            
            add_message_to_chat("user", argv[2])


    elif len(argv) == 4:
        for model in models:
            if ("-" + model["shortcut"]) == argv[1] or ("--" + model["name"]) == argv[1]:
                change_model(model)
                break

        for mode in modes:
            if ("-" + mode["shortcut"]) == argv[2] or ("--" + mode["name"]) == argv[2]:
                chat["mode"] = mode["name"]
                add_message_to_chat("system", mode["description"])
            
        if not chat["all_messages"]:
            add_message_to_chat("system", short_mode)
        
        add_message_to_chat("user", argv[3])
            

def dalle_mode():
    global chat
    last_message = chat["all_messages"][-1]["content"]
    try:
        prompt = last_message.split("```")[1].strip()
        response = client.images.generate(
            prompt=prompt,
            model="dall-e-3",
            n=1,
            size="1024x1024",
        )

        image_url = response.data[0].url
        prompt_words = prompt.split()

        if len(prompt_words)>10:
            name_words = prompt_words[:10]

        name_words = [word.strip(",.!/'") for word in prompt.split() if '/' not in word]
        image_name = " ".join(prompt_words) + ".png"
        image_path = path + image_name

        response = requests.get(image_url)
        with open(image_path, "wb") as image:
            image.write(response.content)
            
        if platform == "win32":
            os.startfile(image_name)
        elif platform == "darwin":
            subprocess.Popen(["open", image_name])
        else:
            subprocess.Popen(["xdg-open", image_name])
    except:
        pass


def execute_command(command):
    output = subprocess.check_output(command, shell=True, universal_newlines=True)
    return output


def delete_chat(db):
    global chat
    if chat["is_loaded"]:
        db.execute("DELETE FROM chat_messages WHERE chat_id=?", chat["id"])
        db.execute("DELETE FROM images WHERE chat_id=?", chat["id"])
        update_chat_ids(db)
    exit()
    

def update_chat_ids(db):
    old_chat_ids = db.execute("SELECT DISTINCT chat_id FROM chat_messages;")
    old_chat_ids_list = [id["chat_id"] for id in old_chat_ids]

    if old_chat_ids_list != sorted(old_chat_ids_list) or old_chat_ids_list[0] != 1 or not is_succinct(old_chat_ids_list):
        messages_in_new_order = []
        for id in old_chat_ids_list:
            messages_in_new_order.append(
                db.execute("SELECT message_id FROM chat_messages WHERE chat_id = ?", id))

        for chat_id in range(0, len(messages_in_new_order)):
            for message in messages_in_new_order[chat_id]:
                db.execute("UPDATE chat_messages SET chat_id = ? WHERE message_id = ?", chat_id+1, message["message_id"])
        
        for (idx, chat_id) in enumerate(old_chat_ids_list):
            if idx+1 != chat_id:
                db.execute("UPDATE images SET chat_id = ? WHERE chat_id = ?", 
                    idx+1, chat_id)


def is_succinct(list):
    for i in range(1, len(list)):
        if list[i] != list[i-1]+1:
            return False
        
    return True 


# I know this technically isn't a bar, but semantics never stopped anyone from doing anything really
def loading_bar(chat):
    global terminal
    phases = ['⠟', '⠯', '⠷', '⠾', '⠽', '⠻']
    i = 0;

    # makes the cursor disappear.
    print("\033[?25l" + terminal[chat["color"]], end="")
    while True:
        print("\b" + phases[i], end="")
        sleep(140/1000)
        if i==5:
            i=0 
        else:
            i+=1


def return_cursor_and_overwrite_bar():
    print("\033[?25h", end="\b")


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
        

def choose_mode():
    global chat
    mode_input = input("What mode would you like? ").lower().strip()
    print()

    mode_description = short_mode
    for option in modes:
        if mode_input == option["name"] or mode_input == option["shortcut"]:
            mode_description = option["description"]
            chat["mode"] = option["name"]
            break
    add_message_to_chat("system", mode_description)


def delete_messages(number = 2):
    for _ in range(number):
        chat["all_messages"].pop(-1)
    print(chat["all_messages"])
    alert(f"Deleted {number} messages")
    print_chat()

def edit_message(id):
    global chat
    new_message = use_editor(chat["all_messages"][-id]["content"])
    chat["all_messages"][-id]["content"] = new_message

def use_editor(initial_text):
    editor = os.environ.get('EDITOR', 'nvim')
    tmpfile_contents = ""

    with tempfile.NamedTemporaryFile(suffix=".tmp", mode='w+', delete=False) as tmpfile:
        tmpfile_path = tmpfile.name
        tmpfile.write(initial_text)
        tmpfile.flush()

    try:
        subprocess.run([editor, tmpfile_path], check=True)
        with open(tmpfile_path, 'r') as tmpfile:
            # chat["all_messages"][-id]["content"] = tmpfile.read().strip()
            tmpfile_contents = tmpfile.read().strip()
    finally:
        os.remove(tmpfile_path)
        return tmpfile_contents


def nuclear(db):
    db.execute("DELETE FROM chat_messages")
    exit()

if __name__ == "__main__":
    main()
