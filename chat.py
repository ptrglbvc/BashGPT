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

logging.disable(logging.CRITICAL)

# checks if the chat is resumed,
# also stores the number of the loaded chatg
is_loaded = [False]
is_argv = False if len(argv) == 1 else True
is_new_mode = True if is_argv and argv[1] in ("--new-mode", "--add-mode") else False
all_messages = []

#this has honestly been the hardest part of the project. Without the library, I had to resort to really big workarounds
path = str(Path(__file__).parent.resolve()) + "/"
key_location = path + "key.txt"
db_location = path + "history.db"
another_one_location = path + "another_one.wav"
audio_location = path + "audio.wav"


def main():
    global is_new_mode
    global all_messages
    global key_location, db_location, another_one_location
    db = setup_db_and_key()
    history_exists = db.execute(("SELECT MAX(message_id) "
                                "as max FROM chat_messages"))[0]["max"] is not None

    if is_argv:

        # check for too many args
        if len(argv)>3:
            print("Too many arguments")
            return 0

        prompt = argv[-1]
        all_messages.append({"role": "system", "content": short_mode})
        all_messages.append({"role": "user", "content": prompt})
        print()

        if len(argv) == 3:
            if argv[1] == "--new-mode":
                all_messages[0] = {"role": "system",
                                   "content": argv[2]}

            else:
                for mod in modes:
                    if ("-"+mod["shortcut"]) == argv[1]:
                        all_messages[0] = {"role": "system",
                                           "content": mod["description"]}

    elif history_exists:
        history_input = input(
            ("Would you like to resume a previous conversation? "
             "(y/n) ")).lower().strip()
        if history_input == "y":
            all_messages = resume_chat(db)

        else:
            modes_text = "Modes to choose from: "
            for option in modes:
                modes_text += option["name"]+", "
                if option["shortcut"] is modes[-1]["shortcut"]:
                    modes_text = modes_text.rstrip(", ")+"."
            print("\n" + modes_text, end=" ")

            mode_input = input(
                "The default is short mode.\n"
                "What mode would you like? ").lower().strip()
            print()
            mode = short_mode
            for option in modes:
                if mode_input == option["name"] or mode_input == option["shortcut"]:
                    mode = option["description"]
                    break
            all_messages.append({"role": "system", "content": mode})

    while 1:
        if not is_argv or len(all_messages) > 2 or is_new_mode:
            chat = input("You: ")
            print()

            if chat == "q":
                save_chat(all_messages, db)
                break
                exit()
            elif chat == "l":  # l stands for long input
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

        #play the "another one" sound effect thread from time to time (in another thread)
        if len(all_messages)%10==0:
            threading.Thread(target=playsound, args=[another_one_location]).start()
        all_messages.append({"role": "assistant", "content": answer})

        if total_tokens > 3200:
            print("\033[1m\033[31mToken limit almost reached.\033[0m\n")


def setup_db_and_key():
    if not os.path.isfile(key_location):
        key = input("What is your OpenAI API key? ")
        with open(key_location, "w") as key_file:
            key_file.write(key)
    
    with open(key_location, 'r') as key:
        pass
        openai.api_key = key.read().strip()

    #checks if the user already has a db file in the directory, if not, creates it.
    #replace the file path with yours here
    if not os.path.isfile(db_location):
        try:
            conn = sqlite3.connect(db_location)
        except sqlite3.Error as e:
            print(e)
        finally:
            if conn:
                conn.close()
        #replace the file path with your file path here
        db = SQL("sqlite:///" + db_location)
        db.execute(("CREATE TABLE chat_messages ("
        "chat_id INTEGER,"
        "message_id INTEGER PRIMARY KEY,"
        "user_name TEXT,"
        "message TEXT,"
        "description TEXT);"))
    else:
        db = SQL("sqlite:///" + db_location)
    return db


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

def save_chat(chat, db):
    # if the chat is too short, that is, just the role message and the
    # first user message, there's no need to save it.
    if len(chat) > 2:
        print("Saving chat. Hold on a minute...")
        chat_description = get_description(chat)
        max_chat_id = db.execute(
            "SELECT MAX(chat_id) AS max FROM chat_messages")[0]["max"]
        if max_chat_id is None:
            max_chat_id = 0

        elif is_loaded[0]:
            global chat_id

            # deletes the chat, but the now chat is saved under a newer number.
            db.execute(
                "DELETE FROM chat_messages WHERE chat_id=?", is_loaded[1])
            max_chat_id = is_loaded[1]-1

        for message in chat:
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
    global is_loaded
    is_loaded.append(chat_id)
    is_loaded[0] = True

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


if __name__ == "__main__":
    main()
