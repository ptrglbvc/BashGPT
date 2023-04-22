# BashGPT

## Installation
Clone the repo.
```
    git clone https://github.com/ptrglbvc/BashGPT.git
```
Go to the cloned directory.
```
    cd BashGPT
```
Install it with pip install.
```
    pip install --editable
```
Don't forget to put your OpenAI API key in the key.txt file.

## Use
I noticed that there is not a good command-line interface for interacting with the GPT api-s, so I made basically a ChatGPT for the command line.

Basic usage:
```
    dp -u "What is your name? What is your quest? What is your favorite colour?"
```
The code above starts a chat with the first message being between the one between the quotees. The -u flag is one of the mode flags, and stands for "uwu", which... well, just see for yourself in the answer:
```
    Haii, my name is Uwumi. My quest is to spread kawaii vibes to everyone I meet. My favowite colour is pinku~ *giggles and twirls cutely* OwO
```
Yeah... so the modes allow the chat agent to really be customized. This is all a part of the functionality of the openai API. The available modes can be seen by doing a simple **dp** and saying no to continuing a previous chat, which bring the user to the next screen.
```
    Modes to choose from: hisoka, uwu, trump, based, pleonasm. The default is short mode.
    Which mode would you like?
```
A shorthand is enough to choose, or the full name of mode (case-insensitive).

if you want to add a new mode for your chat, you can do that with the following:
```
    dp --new-mode "You are the most Monty Python assistant there is. Every answer you give sounds like a Monty Python quote or refernece."
```
This example produces the following result:

```
    You: What is your name?
```
```
    My name is Sir Lancelot the Brave.
```
While in chat, you can go in the long input mode with **v**, which allows you to input multiple paragraphs of text.

## The files
### chat.py
This file is the core of the program. It contains most of the logic of the program, really, the whisper.py is the only other file that contains logic. Main function, along with the other functions, the function of which is described in the file itself. The most important components are the **openai** library and the SQL module of the **cs50** library. It handles the interaction with the gpt-3.5-turbo API by sending a list of dictionaries (__all_messages__) trough the **openai** library.  

### whisper.py
This module provides the interaction with the whisper API for the voice recognition. The **openai** again handles most of the logic for the whisper() function. The other important part is the record function, which is provides the voice recording functionality through the **PyAudio** and **wave** libraries.

### key.txt
This file is used to store the OpenAI API key. I used a simple text file simply for ease of use. If the key.txt file is not present, the __check_db_and_key()__ function inside of chat.py ensures that the user is asked for his key and makes the file.