import re
import subprocess
import os
from pathlib import Path
from sys import platform

import requests
from bashgpt.chat import chat

dalle_system_message = """
You can use the dalle tool to generate beautiful images using the dalle image generator api. 
To use it, simply put the prompt between <dalle> and </dalle> tags.
For example, if the user asks for a cat, you can write <dalle>Cat, photoshoot, Canon f/1.5</dalle>.
The image will get generated shortly after you give the prompt, so also inform the user that they will get the image in a couple of seconds.
If the user asks for stuff like naked girls or gore, reject him and tell him that he'll just waste his OpenAI credits, because OpenAI the endpoint will reject him anyway.
"""

def dalle_mode(client):
    last_message = chat["all_messages"][-1]["content"]
    try:
        prompts = parse_dalle_message(last_message)
        for prompt in prompts:
            response = client.images.generate(
                prompt=prompt,
                model="dall-e-3",
                n=1,
                size="1024x1024",
            )

            image_url = response.data[0].url
            prompt_words = prompt.split()

            if len(prompt_words)>10:
                name_words = prompt_words[:10]

            name_words = [word.strip(",.!/'") for word in prompt.split() if '/' not in word]
            image_name = " ".join(name_words) + ".png"
            image_path = str(Path.home() / 'Downloads' / image_name)

            response = requests.get(image_url)
            with open(image_path, "wb") as image:
                image.write(response.content)
                
            if platform == "win32":
                os.startfile(image_path)
            elif platform == "darwin":
                subprocess.Popen(["open", image_path])
            else:
                subprocess.Popen(["xdg-open", image_path])
    except:
        pass


def parse_dalle_message(message):
    pattern = re.compile(r"<dalle>(.*?)</dalle>", re.DOTALL)
    matches = pattern.findall(message)
    return matches