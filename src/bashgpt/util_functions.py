from bashgpt.terminal_codes import terminal
from time import sleep
from re import sub

def alert(text):
    print(terminal["red"] + text + terminal["reset"] + "\n")

def return_cursor_and_overwrite_bar():
    print("\033[?25h\033[0m", end="\b")

# I know this technically isn't a bar, but semantics never stopped anyone from doing anything really
def loading_bar(chat):
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

def parse_md(text):
    bold_text = sub(r'\*\*(.*?)\*\*|__(.*?)__', r'\033[1m\1\2\033[22m', text)
    italic_text = sub(r'\*(.*?)\*|_(.*?)_', r'\033[3m\1\2\033[23m', bold_text)

    return italic_text

def is_succinct(list):
    for i in range(1, len(list)):
        if list[i] != list[i-1]+1:
            return False
        
    return True 