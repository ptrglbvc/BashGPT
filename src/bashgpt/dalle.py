import re
import subprocess
import os
import requests
import imghdr
from io import BytesIO
from json import loads
from base64 import b64decode
from pathlib import Path
from sys import platform


from bashgpt.chat import chat

dalle_system_message = """
You can use the dalle tool to generate images.
To use it, place a json between <dalle> and </dalle> tags.
The only key in the json that is necessary is prompt, which is a string.
For example, if the user asks for a cat, you can write <dalle>{"prompt": "Cat, photoshoot, Canon f/1.5"}</dalle>.
Optional keys are "size" - the size of the image. The available sizes are "1024x1024" (square), "1536x1024" (portrait) and "1024x1536" (landscape).
The "quality" key is for the quality of the image. It can be "low", "medium" and "high".
Do not change quality and size unless asked.
The "included_images" is for the images to include in the request, used mostly for editing and using features of those images in the result. Both urls and local paths are supported.
Putting it all together for a more complex request:
<dalle>{"prompt": "Generate a man with this cat on his head", "included_images"=["absolute/path/to/cat.png"], "quality"="medium", "size"="1536x1024"}</dalle>.
The image will get generated in the background shortly after you give the prompt, so also inform the user that they will get the image in a couple of seconds.
The images are saved in the user's downloads folder.
"""

def generate_openai_image(client):
    last_message = chat["all_messages"][-1]["content"]
    last_message_id = len(chat["all_messages"]) - 1
    try:
        commands = parse_dalle_message(last_message)

        for command in commands:
            command = loads(command)
            prompt = command["prompt"]

            if "included_images" in command:
                included_images = command["included_images"]
            else:
                included_images = []

            if "quality" in command:
                quality = command["quality"]
            else:
                quality = "low"

            if "size" in command:
                size = command["size"]
            else:
                size = "1024x1024"

            if included_images:
                response = client.images.edit(
                    prompt=prompt,
                    model="gpt-image-1",
                    image=load_images(included_images),
                    n=1,
                    quality=quality,
                    size=size,
                )

            else:
                response = client.images.generate(
                    prompt=prompt,
                    model="gpt-image-1",
                    n=1,
                    quality=quality,
                    size=size,
                    moderation="low"
                )

            image_content = b64decode(response.data[0].b64_json)
            prompt_words = prompt.split()

            if len(prompt_words)>10:
                name_words = prompt_words[:10]

            name_words = [word.strip(",.!/'") for word in prompt.split() if '/' not in word]
            image_name = " ".join(name_words) + ".png"
            image_path = str(Path.home() / 'Downloads' / image_name)

            with open(image_path, "wb") as image:

                image.write(image_content)

            if platform == "win32":
                os.startfile(image_path)
            elif platform == "darwin":
                subprocess.Popen(["open", image_path])
            else:
                subprocess.Popen(["xdg-open", image_path])
    except Exception as exception:
        chat["all_messages"][last_message_id]["content"] += ("\n\nThere was an exception in generating the image: " + str(exception))
        pass

def load_images(included_images):
    files = []
    for src in included_images:
        if os.path.isfile(src):
            files.append(open(src, 'rb'))
        else:
            r = requests.get(src, timeout=10)
            r.raise_for_status()
            data = r.content

            ext = imghdr.what(None, data)
            if ext not in ("jpeg", "png", "webp"):
                raise ValueError(f"Unsupported image type: {ext!r}")
            ext = "jpg" if ext == "jpeg" else ext

            bio = BytesIO(data)
            # give it a “filename” so openai client picks up mime‐type
            bio.name = f"image.{ext}"
            bio.seek(0)
            files.append(bio)
    return files

def download_image(url, timeout=10):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content

def is_url_valid(url, timeout=5):
    try:
        r = requests.head(url, allow_redirects=True, timeout=timeout)
        return r.status_code < 400
    except requests.RequestException:
        return False


def parse_dalle_message(message):
    pattern = re.compile(r"<dalle>(.*?)</dalle>", re.DOTALL)
    matches = pattern.findall(message)
    return matches
