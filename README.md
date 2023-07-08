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
pip install --editable .
```

## Dependencies
There is not much dependencies to install, pretty much just Python 3.0+, [PortAudio v19](https://github.com/PortAudio/portaudio) for voice recording and sqlite for database manipulation (pretty much already on every non-Windows device). All the necessary Python libraries will automatically be installed with _pip install_, but you can manually install them yourself. All the libraries can be seen in the **setup.py** file.    

## Use
Basically, a quicker way to interact with the gpt models than booting up a site or an application, and is primarely intended for getting small code inserts or some nuggets of information. 

Basic usage:
```
dp -u "What is your name? What is your quest? What is your favorite colour?"
```
The code above starts a chat with the first message being the one between the quotes. The -u flag is one of the mode flags, and stands for "uwu", which... well, just see for yourself in the answer:
```
Haii, my name is Uwumi. My quest is to spread kawaii vibes to everyone I meet. My favowite colour is pinku~ *giggles and twirls cutely* OwO
```
Yeah... so the modes allow the chat agent to really be customized. This is all a part of the functionality of the OpenAI API. The available modes can be seen by doing a simple _dp help_ and saying no to continuing a previous chat, which bring the user to the next screen.
```
Available modes: h (hisoka mode), bs (bash mode), u (uwu mode), t (trump mode), b (based mode), c (chance mode), d (dalle mode), p (pleonasm mode).
```
A shorthand is enough to choose, or the full name of mode (case-insensitive either way).

if you want to add a new mode for your chat, you can do that with the following:
```
dp --new-mode "You are the most Monty Python assistant there is. 
Every answer you give sounds like a Monty Python quote or refernece."
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

### setup.py
This file is for installation with pip. I recommend installing it with the --editable flag, because it doesn't work on my system without it.

### file_locations.py
Stores the absolute file locations for **key.txt**, **history.db**, **audio.wav** and **another_one.wav**., which are needed for running it for outside of the program directory.

### modes.py
Stores the prebuilt modes in a list of dictionaries, like god intended. By storing them all here, including some really long descriptions, the chat.py file looks much cleaner and more readable.

### history.db
Stores the chats. The table is created with the following command:
```
CREATE TABLE chat_messages (
    chat_id INTEGER,
    message_id INTEGER PRIMARY KEY,
    user_name TEXT,
    message TEXT, 
    description TEXT);
```

### another_one.wav
The most important file in the project. You will find out what it is used for yourself, trust me.
