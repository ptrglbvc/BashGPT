import openai
import simpleaudio as sa
import logging
import os
import sqlite3
import threading
from cs50 import SQL
from modes import modes, short_mode
from sys import argv
from whisper import record, whisper
from pathlib import Path
from bash import execute_command
from setup_db_and_key import setup_db, setup_key

logging.disable(logging.CRITICAL)

# checks if the chat is resumed,
# also stores the number of the loaded chat from the database
# ignore my retarded naming conventions

chat_is_loaded = [False]
#is_argv = False if len(argv) == 1 else True
#is_new_mode = True if argv and argv[1] in ("--new-mode", "--add-mode") else False
all_messages = []
current_mode = "short"


#this has honestly been the hardest part of the project. Without the library, I had to resort to really big workarounds
path = str(Path(__file__).parent.resolve()) + "/"
another_one_location = path + "another_one.wav"
audio_location = path + "audio.wav"

db = setup_db(path) if argv==1 else ""
setup_key(path)


def main():
    global all_messages
    current_mode = "short"

    # check for too many args
    if len(argv)>3:
        print("Too many arguments. For help with usage type 'dp help'.")
        return 0

    elif len(argv)==2:
        if argv[1]=="help":
            help_me()
            exit()

        prompt = argv[1]
        all_messages.append({"role": "system", "content": short_mode})
        all_messages.append({"role": "user", "content": prompt})
        print()

    elif len(argv) == 3:
        if argv[1] == "--new-mode":
            all_messages.append({"role": "system",
                                "content": argv[2]})

        else:
            for mod in modes:
                if ("-"+mod["shortcut"]) == argv[1]:
                    all_messages.append({"role": "system", "content": mod["description"]})
                    current_mode = mod["name"]

            if not all_messages:
                print("Invalid mode. For available modes type 'dp help'.")
                exit()
            
            all_messages.append({"role": "user", "content": argv[2]})

    # we don't need to load the history if we enter the app from the quick mode. We only need to once we save

    else:
        db = setup_db(path)
        history_exists = db.execute(("SELECT MAX(message_id) "
                                    "AS max FROM chat_messages"))[0]["max"] is not None 
        if history_exists:
            history_input = input(
                ("\nWould you like to resume a previous conversation? "
                "(y/n) ")).lower().strip()
            if history_input == "y":
                all_messages = resume_chat(db)

            # we need to ask the user for the mod if he doesn't load history.
            else:
                mode_input = input("What mode would you like? ").lower().strip()
                print()

                mode_description = short_mode
                for option in modes:
                    if mode_input == option["name"] or mode_input == option["shortcut"]:
                        mode_description = option["description"]
                        current_mode = option["name"]
                        break
                all_messages.append({"role": "system", "content": mode_description})
    

    while 1:
        # If there is only 2 messages, then we know that it is a user sending a message via command line argiments.
        if not len(all_messages) == 2:
            chat = input("You: ")
            print()

            if chat == "q":
                save_chat()
                break
            elif chat == "l": 
                chat = long_input()
            elif chat == "v":
                chat = voice_input()

            all_messages.append({"role": "user", "content": chat})

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=all_messages,
            temperature=0.9)
        answer = response.choices[0].message.content
        stylized_answer = "\033[1m\033[35m" + answer + "\033[0m"
        total_tokens = response.usage.total_tokens

        print(stylized_answer, "\n")
        all_messages.append({"role": "assistant", "content": answer})

        #bashgpt mode starts here baby
        if current_mode == "bash":
            try:
                command = answer.split("```")[1]
                output = execute_command(command)
                if output.strip():
                    nicely_formated_output = "\033[1m\033[31mShell: "+output+"\033[0m"
                    print(nicely_formated_output)
                    if len(output)<1000:
                        all_messages.append({"role": "user", "content": "Shell: "+ output})
                    
            except Exception:
                pass

        #play the "another one" sound effect thread from time to time (in another thread). just cause.
        if len(all_messages)%10==0:
            threading.Thread(target=playsound, args=[another_one_location]).start()

        if total_tokens > 3200:
            print("\033[1m\033[31mToken limit almost reached.\033[0m\n")




def long_input():
    print(("\033[1m\033[31mInput your long text. "
           "To end the input, type 'q' in a new line.\033[0m\n"))
    chat = ""
    while True:
        line = input()
        if line.rstrip() == "q":
            chat.rstrip("\n")
            print()
            break
        chat += line + "\n"
    return chat

def voice_input():
    record()
    transcription = whisper(audio_location)
    print("You: " + transcription + "\n")
    return transcription

def save_chat():
    global db
    if not db:
        db = setup_db(path)
    # if the chat is too short, that is, it's the role message and the
    # first user message, there's no need to save it.
    if len(all_messages) > 2:
        print("Saving chat. Hold on a minute...")
        chat_description = get_description(all_messages)
        max_chat_id = db.execute(
            "SELECT MAX(chat_id) AS max FROM chat_messages")[0]["max"]
        if not max_chat_id:
            max_chat_id = 0

        elif chat_is_loaded[0]:
            global chat_id

            # deletes the chat, but the now chat is saved under a newer number.
            db.execute("DELETE FROM chat_messages WHERE chat_id=?", chat_is_loaded[1])
            max_chat_id = chat_is_loaded[1]-1

        for message in all_messages:
            db.execute("INSERT INTO chat_messages (chat_id, user_name, message, description) VALUES (?, ?, ?, ?)",
                       max_chat_id+1, message["role"], message["content"], chat_description)


def playsound(file):
    wave_object = sa.WaveObject.from_wave_file(file)
    wave_object.play().wait_done()


def resume_chat(db):
    options = db.execute(
        "SELECT DISTINCT chat_id, description FROM chat_messages")
    print()
    for option in options:
        print(f"{option['chat_id']}: {option['description']}")
    # todo: error handing
    chat_id = int(input("\nWhich chat do you want to continue? "))
    global chat_is_loaded
    chat_is_loaded.append(chat_id)
    chat_is_loaded[0] = True

    rows = db.execute("select * from chat_messages where chat_id=?", chat_id)
    global all_messages
    for row in rows:
        all_messages.append(
            {"role": row["user_name"], "content": row["message"]})
        stylized_message = "You: "+row["message"]+"\n"
        if row["user_name"] == "assistant":
            stylized_message = "\033[1m\033[35m" + row["message"] + "\033[0m\n"
        elif row["user_name"] == "system":
            stylized_message = ""
        print(stylized_message)

    return all_messages


def get_description(all_messages):
    chat_description = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "describe the chat using 12 words or less. focus mainly on the human."},
                  {"role": "user", "content": f"human: {all_messages[1]['content']};\n ai: {all_messages[2]['content']}"}]).choices[0].message.content
    return chat_description

def help_me():
    print("Valid usages: dp -bs 'delete every file from my downloads folder' (do not try this at home).\n")
    print("Also valid usages: dp; dp 'what is the height of the Eiffel Tower'\n")
    print("You can also add a new mode: dp --add-mode 'You are a DumbGPT. You get every question wrong.")

    print("Available modes: ", end="")
    for mode in modes:
        print(f'{mode["shortcut"]} ({mode["name"]} mode),', end=" ")


if __name__ == "__main__":
    main()
