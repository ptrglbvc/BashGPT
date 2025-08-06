from bashgpt.terminal_codes import terminal
from time import sleep
from re import sub
import tempfile
import subprocess
import os

def alert(text):
    print(terminal["red"] + text + terminal["reset"] + "\n")

def return_cursor_and_overwrite_bar():
    print("\033[?25h\033[0m", end="\b")

# I know this technically isn't a bar, but semantics never stopped anyone from doing anything really
def loading_bar(chat, stop_event):
    phases = ['⠟', '⠯', '⠷', '⠾', '⠽', '⠻']
    i = 0

    # Makes the spinner disappear.
    print("\033[?25l" + terminal[chat["color"]], end="", flush=True)
    try:
        while not stop_event.is_set():
            print("\b" + phases[i], end="", flush=True)
            sleep(0.14)
            i = (i + 1) % len(phases)
    finally:
        print("\b \b", end="", flush=True)
        print("\033[?25h", end="", flush=True)

def parse_md(text):
    bold_text = sub(r'\*\*(.*?)\*\*|__(.*?)__', r'\033[1m\1\2\033[22m', text)
    italic_text = sub(r'\*(.*?)\*|_(.*?)_', r'\033[3m\1\2\033[23m', bold_text)

    return italic_text

def is_succinct(list):
    for i in range(1, len(list)):
        if list[i] != list[i-1]+1:
            return False

    return True

def use_temp_file(initial_text):
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
