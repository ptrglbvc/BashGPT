# BashGPT

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
