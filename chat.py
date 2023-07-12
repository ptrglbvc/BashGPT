import openai
import simpleaudio as sa

import logging
import threading
import os
import requests
import subprocess
from sys import argv, platform
from pathlib import Path
from time import sleep
from multiprocessing import Process

from modes_and_models import modes, models, short_mode
from db_and_key import setup_db, setup_key
from whisper import record, whisper


# hides the logging that is enabled by default by the cs50 library.
logging.disable(logging.CRITICAL)

all_messages = []


#this has honestly been the hardest part of this project. Without the library, I had to resort to really big workarounds
path = str(Path(__file__).parent.resolve()) + "/"
another_one_location = path + "another_one.wav"
audio_location = path + "audio.wav"


def main():

    openai.api_key = setup_key()
    # also stores the number of the loaded chat from the database in the 1st index
    # please ignore my stupid naming conventions
    chat_is_loaded = [False]
    global all_messages
    db = ""

    if len(argv)>1:
        (current_mode, current_model) = quick_input()
    else:
        current_model = "gpt-3.5-turbo"

    # we don't need to load the history if we enter the app from the quick input mode. We only need to once we save
    if not all_messages:
        db = setup_db(path)
        history_exists = db.execute(("SELECT MAX(message_id) "
                                    "AS max FROM chat_messages"))[0]["max"] is not None 
        if history_exists:
            while 1:
                history_input = input(
                    ("\nWould you like to resume a previous conversation? "
                    "(y/n) ")).lower().strip()[0]
                if history_input == "y":
                    all_messages = resume_chat(db, chat_is_loaded)
                    current_mode = remember_mode()
                    break
                if history_input == "n":
                    break

            # ask user for the mode if he doesn't load history.
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
    

    while True:
        # If there is only 2 messages, then we know that it is a user sending a message via command line argiments.
        if not len(all_messages) == 2:
            chat = input("You: ").strip()
            print()

            if chat == "q":
                if not db:
                    db = setup_db(path)
                save_chat(db, chat_is_loaded)
                break
            elif chat == "q!":
                exit()
            elif chat == "rm!":
                if chat_is_loaded[0]:
                    delete_chat(db, chat_is_loaded)
                else:
                    exit()
            elif chat == "l": 
                chat = long_input()
            elif chat == "v":
                try:
                    chat = voice_input()
                except:
                    print("Recording doesn't work on you device. \nLong input mode activated.")
                    chat = long_input()

            all_messages.append({"role": "user", "content": chat})
            
        # just making sure it look more nice when entered through quick mode.
        else:
            print()

        thred = Process(target=loading_bar, args=["bold_purple"])
        thred.start()

        (stylized_answer, total_tokens) = get_and_parse_response(current_model)
        thred.terminate()
        return_cursor_and_overwrite_bar()

        print(stylized_answer, "\n")

        if total_tokens > 3200:
            print("\033[1m\033[31mToken limit almost reached.\033[0m\n")

        if current_mode == "bash":
            bash_mode(stylized_answer)

        if current_mode == "dalle":
            threading.Thread(target=dalle_mode, args=[stylized_answer]).start()

        #play the "another one" sound effect thread from time to time (in another thread). just cause.
        if len(all_messages)%10==0:
            threading.Thread(target=playsound, args=[another_one_location]).start()





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
    print(2*"\033[1A" + "        \r", end="")
    audio_location = record()
    print("You: ", end=" ")
    thred = Process(target=loading_bar)
    thred.start()

    transcription = whisper(audio_location)

    thred.terminate()
    return_cursor_and_overwrite_bar()

    print(transcription + "\n")
    return transcription

def save_chat(db, chat_is_loaded):
    if not db:
        db = setup_db(path)
    # if the chat is too short, that is, it's the role message and the
    # first user message, there's no need to save it.
    if len(all_messages) > 2:
        print("Saving chat. Hold on a minute...")
        if chat_is_loaded[0]:
            global chat_id
            chat_description = db.execute(
                "SELECT description FROM chat_messages WHERE chat_id = ?", chat_is_loaded[1])[0]["description"]

            # deletes the chat, but the now chat is saved under a newer number.
            db.execute("DELETE FROM chat_messages WHERE chat_id=?", chat_is_loaded[1])
            max_chat_id = chat_is_loaded[1]-1

        else:
            max_chat_id = db.execute(
                "SELECT MAX(chat_id) AS max FROM chat_messages")[0]["max"]
            if not max_chat_id:
                max_chat_id = 0

            chat_description = get_description(all_messages)

        for message in all_messages:
            db.execute("INSERT INTO chat_messages (chat_id, user_name, message, description) VALUES (?, ?, ?, ?)",
                       max_chat_id+1, message["role"], message["content"], chat_description)
        
        update_chat_ids(db)


def playsound(file):
    wave_object = sa.WaveObject.from_wave_file(file)
    wave_object.play().wait_done()


def resume_chat(db, chat_is_loaded):
    options = db.execute(
        "SELECT DISTINCT chat_id, description FROM chat_messages")
    print()
    option_ids = []
    for option in options:
        option_ids.append(option["chat_id"])
        print(f"{option['chat_id']}: {option['description']}")

    while 1:
        option_input = input("\nWhich chat do you want to continue? ")
        if option_input.isnumeric() and int(option_input) in option_ids:
            chat_id = option_input
            break


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


def remember_mode():
    for mod in modes:
        if mod["description"][:15] == all_messages[0]["content"][:15]:
            return mod["name"]
            

def get_description(all_messages):
    return openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "system", "content": "describe the chat using 12 words or less. For example: 'The culture of Malat', 'French words in War and peace', 'Frog facts', etc."},
                  {"role": "user", "content": f"human: {all_messages[1]['content']};\n ai: {all_messages[2]['content']}"}]).choices[0].message.content
        

def help_me():
    print("Valid usage:\n dp -bs 'delete every file from my downloads folder' (it will work, do not try it).\n")
    print("Also valid usages:\n dp (this brings you to the the history tab\n dp 'what is the height of the Eiffel Tower'\n dp --gpt-4 -h 'Why did you lose to Chrollo?'\n")
    print("You can also add a new mode like this: dp --add-mode 'You are a DumbGPT. You get every question wrong.\n")

    available_modes = "Available modes: "
    for mode in modes:
        available_modes += f'{mode["shortcut"]} ({mode["name"]} mode), '
    
    available_modes = available_modes.strip(" ,") + "."
    print(available_modes)


def get_and_parse_response(current_model):
    for _ in range(5):
        try:
            response = openai.ChatCompletion.create(
                model=current_model,
                messages=all_messages,
                temperature=0.8)

            answer = response.choices[0].message.content
            stylized_answer = "\033[1m\033[35m" + answer + "\033[0m"
            total_tokens = response.usage.total_tokens

            all_messages.append({"role": "assistant", "content": answer})
            return (stylized_answer, total_tokens)
        except:
            print("\rRetrying request...")
    
    save_chat()
    exit()


def bash_mode(answer):
    try:
        command = answer.split("```")[1]
        output = execute_command(command)
        if output.strip():
            nicely_formated_output = "\033[1m\033[31mShell: "+output+"\033[0m"
            print(nicely_formated_output)
            if len(output)<1000:
                all_messages.append({"role": "user", "content": "Shell: "+ output})
            
    except Exception as e:
        print(f"Exception: {e}")


def quick_input():
    global all_messages
    current_mode = "short"
    current_model = "gpt-3.5-turbo"

    # check for too many args
    if len(argv)>4:
        print("Too many arguments. For help with usage type 'dp help'.")
        return 0

    elif len(argv)==2:
        if argv[1]=="help":
            help_me()
            exit()
        
        elif argv[1]=="--gpt-4" or argv[1]=="-4":
            current_model = "gpt-4"

        else:
            prompt = argv[1]
            all_messages.append({"role": "system", "content": short_mode})
            all_messages.append({"role": "user", "content": prompt})

    elif len(argv) == 3:
        if argv[1] == "--new-mode":
            current_mode = argv[2]

        else:
            for mode in modes:
                if ("-"+mode["shortcut"]) == argv[1]:
                    current_mode = mode["name"]
                    all_messages.append({"role": "system", "content": mode["description"]})
                    break
            
            if current_mode == "short":
                for model in models:
                    if ("-" + model["shortcut"]) == argv[1] or ("--" + model["name"]) == argv[1]:
                        current_model = model["name"]
                        all_messages.append({"role": "system", "content": short_mode})
                        break

            all_messages.append({"role": "user", "content": argv[2]})


    elif len(argv) == 4:
        for model in models:
            if ("-" + model["shortcut"]) == argv[1] or ("--" + model["name"]) == argv[1]:
                current_model = model["name"]
                break

        for mode in modes:
            if ("-" + mode["shortcut"]) == argv[2] or ("--" + mode["name"]) == argv[2]:
                current_mode = mode["name"]
                all_messages.append({"role": "system", "content": mode["description"]})
            
        if not all_messages:
            all_messages.append({"role": "system", "content": short_mode})
        
        all_messages.append({"role": "user", "content": argv[3]})
            
    return (current_mode, current_model) 


def dalle_mode(text):
    try:
        prompt = text.split("```")[1].strip()
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="1024x1024"
        )
        image_url = response['data'][0]['url']
        prompt_words = prompt.split()
        if len(prompt_words)>10:
            prompt_words = prompt_words[:10]

        prompt_words = [word.strip(",.!/'") for word in prompt.split() if '/' not in word]

        image_name = "_".join(prompt_words) + ".png"
        response = requests.get(image_url)
        with open(image_name, "wb") as image:
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

def delete_chat(db, chat_is_loaded):
    if chat_is_loaded[0]:
        db.execute("DELETE FROM chat_messages WHERE chat_id=?", chat_is_loaded[1])
        update_chat_ids(db)
    exit()
    
def update_chat_ids(db):
    old_chat_ids = db.execute("SELECT DISTINCT chat_id FROM chat_messages;")
    old_chat_ids_list = [id["chat_id"] for id in old_chat_ids]

    if old_chat_ids_list != sorted(old_chat_ids_list) or old_chat_ids[0] != 1 or not is_succinct(old_chat_ids_list):
        messages_in_new_order = []
        for id in old_chat_ids:
            messages_in_new_order.append(db.execute("SELECT message_id FROM chat_messages WHERE chat_id = ?", id["chat_id"]))

        for chat_id in range(0, len(messages_in_new_order)):
            for message in messages_in_new_order[chat_id]:
                db.execute("UPDATE chat_messages SET chat_id = ? WHERE message_id = ?", chat_id+1, message["message_id"])

def is_succinct(list):
    for i in range(1, len(list)):
        if list[i] != list[i-1]+1:
            return False
        
    return True 

# I know this technically isn't a bar, but semantics never stopped anyone from doing anything really
def loading_bar(color = "regular"):
    phases = ['⠟', '⠯', '⠷', '⠾', '⠽', '⠻']
    i = 0;
    colors = {"purple": "\033[35m", "bold_purple": "\033[35m\033[1m", "red": "\033[31m", "regular": ""}

    # makes the cursor disappear.
    print("\033[?25l" + colors[color], end="")
    while True:
        print("\b" + phases[i], end="")
        sleep(140/1000)
        if i==5:
            i=0 
        else:
            i+=1


def return_cursor_and_overwrite_bar():
    print("\033[?25h", end="\b")


if __name__ == "__main__":
    main()