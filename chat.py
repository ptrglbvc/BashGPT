#!/opt/homebrew/bin/python3
import openai
import simpleaudio as sa
from cs50 import SQL
import logging
from modes import modes, short_mode
from sys import argv
from pathlib import Path
from whisper import record, whisper
logging.disable(logging.CRITICAL)


with open('key.txt', 'r') as file:
    pass
    openai.api_key = open("key.txt", "r").read().strip()
db = SQL("sqlite:///history.db")
history_exists = db.execute(("SELECT MAX(message_id) "
                            "as max FROM chat_messages"))[0]["max"] is not None
# checks if the chat is resumed, for the number,
# also stores the number of the loaded chatg
is_loaded = [False]
is_argv = False if len(argv) == 1 else True
all_messages = []


def main():
    global all_messages
    if is_argv:
        prompt = argv[-1]
        all_messages.append({"role": "system", "content": short_mode})
        all_messages.append({"role": "user", "content": prompt})
        print()
        if len(argv) == 3:
            for mod in modes:
                if ("-"+mod["shortcut"]) == argv[1]:
                    all_messages[0] = {"role": "user",
                                       "content": mod["description"]}

    elif history_exists:
        history_input = input(
            ("Would you like to resume a previous conversation? "
             "(y/n) ")).lower().strip()
        if history_input == "y":
            all_messages = resume_chat()

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
        if not is_argv or len(all_messages) > 2:
            chat = input("You: ")
            print()

            if chat == "q":
                save_chat(all_messages)
                break
            elif chat == "l":  # l stands for long input
                chat = long_input()
            elif chat == "v":
                chat = voice_input()

            all_messages.append({"role": "user", "content": chat})

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0301",
            messages=all_messages)
        answer = response.choices[0].message.content
        stylized_answer = "\033[1m\033[35m" + answer + "\033[0m"
        total_tokens = response.usage.total_tokens

        print(stylized_answer, "\n")
        playsound("./another_one.wav")  # to-do: play this in another thread
        all_messages.append({"role": "assistant", "content": answer})

        if total_tokens > 3200:
            print("\033[1m\033[31mToken limit almost reached.\033[0m\n")


def long_input():
    print(("\033[1m\033[31mInput your long text. "
           "To end the input, type END in a new line.\033[0m\n"))
    chat = ""
    while True:
        line = input()
        if line.rstrip() == "END":
            chat.rstrip("\n")
            print()
            break
        chat += line + "\n"
    return chat

def voice_input():
    record()
    transcription = whisper("audio.wav")
    print(transcription + "\n")
    return transcription

def save_chat(chat):
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


def resume_chat():
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

# todo: make this multithreaded


def get_description(all_messages):
    chat_description = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "describe the chat using 12 words or less. focus mainly on the human."},
                  {"role": "user", "content": f"human: {all_messages[1]['content']};\n ai: {all_messages[2]['content']}"}]).choices[0].message.content
    return chat_description


main()
