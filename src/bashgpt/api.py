from bashgpt.chat import chat, add_message_to_chat
from bashgpt.autonomous import auto_system_message
from bashgpt.bash import bash_system_message
from bashgpt.dalle import  dalle_system_message
from bashgpt.util_functions import alert, loading_bar
from bashgpt.terminal_codes import terminal

import google.ai.generativelanguage as glm
import google.generativeai as googleai
from google.generativeai.types import HarmBlockThreshold, HarmCategory
from anthropic import Anthropic
from openai import (APIConnectionError, APIError, APIResponseValidationError,
                    APIStatusError, APITimeoutError, AuthenticationError,
                    BadRequestError, ConflictError, InternalServerError,
                    NotFoundError, OpenAI, OpenAIError, PermissionDeniedError,
                    RateLimitError, UnprocessableEntityError)

import threading
import copy
import base64
import json
import httpx
from os import getenv

client = OpenAI(api_key=getenv("OPENAI_API_KEY"))
anthropic_client = Anthropic(api_key=getenv("ANTHROPIC_API_KEY"))
googleai.configure(api_key=getenv("GOOGLEAI_API_KEY"))


def attach_images_anthropic_openai(all_messages):
    memo = {}
    messages_with_images = copy.deepcopy(all_messages, memo)
    for image in chat["images"]:
        if (curr_idx:=image["message_idx"]) < len(messages_with_images):
            image_data = {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": f'image/{image["extension"]}',
                    "data": image["content"]
                },
            } if chat["provider"] == "anthropic" else {
                "type": "image_url", "image_url": {
                    "url": f'data:image/{image["extension"]};base64,{image["content"]}'
                }
            }

            # this is for checking if the message already has an image attached
            if str(type(messages_with_images[curr_idx]["content"])) == "<class 'str'>":
                newValue = {"role": "user", "content": [
                    {"type": "text", "text": all_messages[curr_idx]["content"]},
                    image_data
                ]}
                messages_with_images[curr_idx] = newValue
            else:
                messages_with_images[curr_idx]["content"].append(image_data) # type: ignore

    return messages_with_images


def get_openai_response(all_messages):
    all_messages = all_messages if not chat["vision_enabled"] else attach_images_anthropic_openai(all_messages)

    stream = client.with_options(
            base_url=chat["base_url"],
            api_key=getenv(chat["api_key_name"])
            ).chat.completions.create(
                model=chat["model"],
                messages=all_messages,
                stream=True,
                max_tokens=chat["max_tokens"],
                temperature=chat["temperature"],
                frequency_penalty=chat["frequency_penalty"],
                extra_body=chat["extra_body"]
                )

    return stream


def attach_files(all_messages):
    global chat
    memo = {}
    all_messages_with_files = copy.deepcopy(all_messages, memo)
    for file in chat["files"]:
        added_text = f"'''\nuser attached {'webpage' if 'extension' == 'html' else 'file'}'" + file["name"] + "':\n" + file["content"] + "\n\n\n'''"
        all_messages_with_files[file["message_idx"]]["content"] = added_text + all_messages_with_files[file["message_idx"]]["content"]
    return all_messages_with_files


def get_anthropic_response(all_messages):
    all_messages = all_messages if not chat["vision_enabled"] else attach_images_anthropic_openai(all_messages)

    stream = anthropic_client.messages.create(
        system=all_messages[0]["content"], # type: ignore
        model=chat["model"],
        messages=all_messages[1:], # type: ignore
        stream=True,
        max_tokens=chat["max_tokens"],
        temperature=chat["temperature"],
        frequency_penalty=chat["frequency_penalty"]
        )

    return stream


def get_google_response(all_messages, stream=True, model=""):
    model = googleai.GenerativeModel(
        model if model else chat["model"],
        system_instruction=all_messages[0]["content"])
    all_messages = adapt_messages_to_google(all_messages)

    response = model.generate_content(
        all_messages,
        safety_settings={
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        },
        generation_config={
            "max_output_tokens": chat["max_tokens"],
            "temperature": chat["temperature"]
        },
        stream=True
    )
    return response


def adapt_messages_to_google(all_messages):
    new_all_messages = []
    for message in all_messages[1:]:
        new_message = {}

        new_message["role"] = message["role"]
        if new_message["role"] == "assistant": new_message["role"] = "model"

        new_message["parts"] = [glm.Part(text=message["content"])]
        new_all_messages.append(new_message)

    attach_glm_images(new_all_messages)

    return new_all_messages



def attach_glm_images(new_all_messages):
    for image in chat["images"]:
        # this -1 is here because we removed the system message previously
        if (curr_idx:=(image["message_idx"] - 1)) < len(new_all_messages):
            new_all_messages[curr_idx]["parts"].append(
                glm.Part(
                    inline_data=glm.Blob(
                        mime_type=f'image/{image["extension"]}',
                        data=base64.b64decode(image["content"])
                    )
                ),
            )

def attach_system_messages(all_messages):
    new_system_message = {
        "role": "system",
        "content": all_messages[0]["content"]
    }

    if chat["auto_turns"] > 0:
        new_system_message["content"] += ("\n" + auto_system_message + "Number of turns left: " + str(chat["auto_turns"]))
    if chat["bash"] is True:
        new_system_message["content"] += ("\n" + bash_system_message)
    if chat["dalle"] is True:
        new_system_message["content"] += ("\n" + dalle_system_message)


    if new_system_message["content"] == all_messages[0]["content"]:
        return all_messages
    else:
        new_all_messages = all_messages.copy()
        new_all_messages[0] = new_system_message
        return new_all_messages

def get_response(messages=None):
    if messages is None:
        messages = chat["all_messages"]
    # I reversed this just to confuse you, dear reader (including myself, yes)
    messages = attach_files(messages) if chat["files"] else messages
    messages = attach_system_messages(messages)


    errorMessage = ""

    try:
        match chat["provider"]:
            case "anthropic":
                stream = get_anthropic_response(messages)
            case "google":
                stream = get_google_response(messages)
            case _:
                stream = get_openai_response(messages)




        print(terminal[chat["color"]], end="")

        import time

        # Initialize the previous chunk's timestamp and a default average delay.
        prev_time = time.time()
        avg_delay = 0.1
        num_of_updates = 0

        for chunk in stream:
            current_time = time.time()
            delay_since_last = current_time - prev_time
            prev_time = current_time

            # unless we use an async function, since the delay is counted as part of the tiem between chunks, the average will enter into a feedback loop, especially when the chunks are smaller. so best to just use the average between the first 3 chunks
            # also, the time to the first chunk shouldn't count, since its more due to time to first token than tps
            if num_of_updates in [1,2,3,4]:

                # Update avg_delay using a simple moving average formula.
                avg_delay = (avg_delay + delay_since_last) / 2
            num_of_updates+=1


            text = ""
            if chat["provider"] == "anthropic":
                if chunk.type == "content_block_delta":  # type: ignore
                    text = chunk.delta.text  # type: ignore
                    if not text:
                        break
                else:
                    continue
            elif chat["provider"] == "google":
                text = chunk.text  # type: ignore
                if not text:
                    break
            else:
                text = chunk.choices[0].delta.content  # type: ignore
                if not text:
                    continue

            # Calculate a delay per character so that the whole chunk prints over about avg_delay seconds.
            if text:
                if chat.get("smooth_streaming", True):
                    min_delay = 0.001  # minimum delay per character (1ms)
                    max_delay = 0.03   # maximum delay per character (30ms)
                    max_chunk_time = 0.5  # maximum time to spend printing a chunk (in seconds)
                    char_delay = avg_delay / len(text) if len(text) > 0 else min_delay
                    char_delay = max(min(char_delay, max_delay), min_delay)
                    total_time = char_delay * len(text)
                    if total_time > max_chunk_time:
                        char_delay = max_chunk_time / len(text)
                    for char in text:
                        yield char
                        time.sleep(char_delay)
                else:
                    yield text


    except (
        APIError,
        OpenAIError,
        ConflictError,
        NotFoundError,
        APIStatusError,
        RateLimitError,
        APITimeoutError,
        BadRequestError,
        APIConnectionError,
        AuthenticationError,
        InternalServerError,
        PermissionDeniedError,
        UnprocessableEntityError,
        APIResponseValidationError,
    ) as e:
        print(terminal["reset"] + "\n")

        errorMessage += f"Error: {e}"
        alert(errorMessage)
        if chat["all_messages"][-1]["role"] == "assistant":
            chat["all_messages"][-1]["content"] += errorMessage
        else:
            add_message_to_chat("assistant", errorMessage)
        return

    finally:
        print(terminal["reset"] + "\n")

def get_and_print_response():
    text = get_response()

    stop = threading.Event()
    bar_thread = threading.Thread(target=loading_bar, args=[chat, stop])
    bar_thread.start()

    if chat["all_messages"][-1]["role"] != "assistant":
        add_message_to_chat("assistant", "")

    try:
        for char in text:
            if not stop.is_set():
                stop.set()
                bar_thread.join()
            print(char, end="", flush=True)
            chat["all_messages"][-1]["content"] += char # type: ignore
    except KeyboardInterrupt:
        if stop.is_set() == False:
            stop.set()
            bar_thread.join()
        print("\033[2D" + terminal["reset"], end="")

def generate_description():
    global chat
    try:
        resp = get_google_response(
            all_messages=[{"role": "system", "content": "describe the chat using 5 words or less. For example: 'The culture of Malat', 'French words in War and peace', 'Frog facts', etc."},
                {"role": "user", "content": f"human: {chat['all_messages'][1]['content']};\n ai: {chat['all_messages'][2]['content']}"}],
            model="gemini-2.0-flash-lite",
            stream=False)
        description = resp.text
        return description
    except:
        return "No description"
