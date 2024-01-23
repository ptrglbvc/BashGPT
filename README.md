# BashGPT

[!](https://user-images.githubusercontent.com/108212912/253288399-a2b2a520-84ea-458e-8d05-8c4771fd23e6.mov)

## Introduction
**Why have all that pretty weak-ass html nonsense when you can just use God's given tool - the t e r m i n a l.**

On a serious note, I usually prefer using the terminal for most things related to programming, so why not just have a good ChatGPT experience in the terminal, with some added features, like Bash mode, Dalle mode and voice input.


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

Add the OPENAI_API_KEY to your environment variables.

Bash:
```bash
echo 'export OPENAI_API_KEY = "(your key)"' >> ~/.bashrc
```

Zsh:
```bash
echo 'export OPENAI_API_KEY = "(your key)"' >> ~/.zshrc
```

PowerShell:
```powershell
$env:OPENAI_API_KEY = '(your key)' 
```

## Dependencies
There is not much dependencies to install, pretty much just Python 3.0+, [PortAudio v19](https://github.com/PortAudio/portaudio) for voice recording and sqlite for database manipulation (pretty much already on every non-Windows device). All the necessary Python libraries will automatically be installed with _pip install_, but you can manually install them yourself. All the libraries can be seen in the **setup.py** file.    


## Usage

The very basic usage:
```
dp -u "What is your name? What is your quest? What is your favorite colour?"
```

The code above starts a chat with the first message being the one between the quotes. The -u flag is one of the mode flags, and stands for "uwu", which... well, just see for yourself in the answer:
```
Haii, my name is Uwumi. My quest is to spread kawaii vibes to everyone I meet. My favowite colour is pinku~ *giggles and twirls cutely* OwO
```

Yeah... so the modes allow the chat agent to really be customized. This is all a part of the functionality of the OpenAI API. Also, I DIDN'T GIVE HER THAT NAME OK?!?!

The available modes can be seen by doing a simple _dp help_ and saying no to continuing a previous chat, which bring the user to the next screen. 
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

GPT-4 is also fully supported, as well as other available OpenAI models, if your OpenAI account has access (more like ClosedAI amirite). The available models are located in the **models.json** file. To use GPT-4, type the following:
```
dp -4 "How far away are Belgrade and Budapest"
```
```
378.2 km
```
Also valid:
```
dp -4 -b "Does kissing a man while drunk mean I'm gay?"
```


## Some other cool stuff
### Commands in chat and exiting

While in a chat, you can do some commands. For example, typing '*v*' brings you to voice input. 

You exit BashGPT the same way as you exit vim, by turning off your computer. Шутка. Just use '*q*'. 

'*q!*' is for exiting the chat without saving.

'*l*' brings you to long input mode, which allows you to input multiple paragraphs of text (impossible with Python's input function).

'*rm!*' is for deleting the chat entirely (if it's already saved).


### Another one

If you keep hearing this from time to time, do not worry, you are not insane, or even better, you are not listening to DJ Khaled. The sound just gets played about every 10 or so messages. You cannot turn this off.
