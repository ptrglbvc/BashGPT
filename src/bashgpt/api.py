from bashgpt.chat import chat, add_message_to_chat
from bashgpt.autonomous import auto_system_message
from bashgpt.bash import bash_system_message
from bashgpt.dalle import dalle_system_message
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
# anthropic_client = Anthropic(api_key=getenv("ANTHROPIC_API_KEY"))
googleai.configure(api_key=getenv("GOOGLEAI_API_KEY"))

def debug_print_payload(messages, provider):
    """Helper to debug cache control issues by printing the payload."""
    try:
        # Check if debug mode is generally desired, or just print if caching is detected
        # For now, we print if caching is detected to confirm it works
        has_cache = False
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if "cache_control" in block:
                        has_cache = True
                        break
        
        if not has_cache: 
            return

        print(f"\n{terminal['yellow']}--- DEBUG: Outgoing {provider} Payload (Caching Active) ---{terminal['reset']}")
        
        # Only print the messages that actually have cache control for brevity
        for i, msg in enumerate(messages):
            is_cached = False
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if "cache_control" in block:
                        is_cached = True
            
            if is_cached:
                print(f"Message {i} ({msg['role']}): CACHE CONTROL PRESENT")
                # Print specific content block with cache
                print(json.dumps(msg['content'], indent=2))
        
        print(f"{terminal['yellow']}-----------------------------------------------------------{terminal['reset']}\n")
    except Exception as e:
        print(f"Debug print failed: {e}")

def attach_images_anthropic_openai(all_messages):
    memo = {}
    messages_with_images = copy.deepcopy(all_messages, memo)
    for image in chat["images"]:
        if (curr_idx := image["message_idx"]) < len(messages_with_images):
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
                    {"type": "text",
                        "text": all_messages[curr_idx]["content"]},
                    image_data
                ]}
                messages_with_images[curr_idx] = newValue
            else:
                messages_with_images[curr_idx]["content"].append(
                    image_data)  # type: ignore

    return messages_with_images


def apply_caching(all_messages):
    """
    Applies Anthropic-style prompt caching to messages if enabled for the model.
    CRITICAL: Always returns a copy of messages with the internal 'cache_control' 
    key stripped out, ensuring clean payloads for APIs that strictly validate keys.
    """
    memo = {}
    # Always deepcopy to avoid modifying chat state and to safely strip internal keys
    messages_processed = copy.deepcopy(all_messages, memo)
    
    # Check if the current model actually supports caching
    is_caching_enabled = chat.get("anthropic_cache_control", False)
    
    for msg in messages_processed:
        # Check internal flag
        wants_cache = msg.get("cache_control", False)
        
        # 1. Clean up the internal key so it's never sent to the API provider
        if "cache_control" in msg:
            del msg["cache_control"]

        # 2. Only apply the API-specific structure if the model supports it
        #    AND the specific message requested it.
        if is_caching_enabled and wants_cache:
            cache_payload = {
                "type": "ephemeral",
                "ttl": "1h"
            }
            
            # If content is a simple string, convert to list of blocks
            if isinstance(msg["content"], str):
                msg["content"] = [{
                    "type": "text",
                    "text": msg["content"],
                    "cache_control": cache_payload
                }]
            
            # If content is already a list (e.g. has images)
            elif isinstance(msg["content"], list):
                # Attach to the last block of content
                if len(msg["content"]) > 0:
                    msg["content"][-1]["cache_control"] = cache_payload

    return messages_processed


def attach_files(all_messages):
    global chat
    memo = {}
    all_messages_with_files = copy.deepcopy(all_messages, memo)
    for file in chat["files"]:
        added_text = f"'''\nuser attached {'webpage' if 'extension' == 'html' else 'file'}'" + \
            file["name"] + "':\n" + file["content"] + "\n\n\n'''"
        all_messages_with_files[file["message_idx"]]["content"] = added_text + \
            all_messages_with_files[file["message_idx"]]["content"]
    return all_messages_with_files


def get_openai_response(all_messages):
    all_messages = all_messages if not chat["vision_enabled"] else attach_images_anthropic_openai(
        all_messages)
    
    all_messages = apply_caching(all_messages)
    debug_print_payload(all_messages, "OpenAI/OpenRouter")

    # Detect if caching transformation occurred
    has_cache_in_payload = False
    for msg in all_messages:
        if isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if "cache_control" in block:
                    has_cache_in_payload = True
                    break
        if has_cache_in_payload:
            break

    # Prepare parameters
    params = {
        "model": chat["model"],
        "max_tokens": chat["max_tokens"],
        "temperature": chat["temperature"],
        "frequency_penalty": chat["frequency_penalty"],
        "stream": True
    }

    # Handle extra_body
    final_extra_body = chat["extra_body"].copy() if chat["extra_body"] else {}

    # If caching is present, OpenAI Python SDK might strip 'cache_control' from content blocks.
    # We bypass this by passing messages via extra_body.
    if has_cache_in_payload:
        final_extra_body["messages"] = all_messages
        # We must still pass a required 'messages' arg to the SDK, but it will be ignored 
        # in favor of extra_body by the API (standard overwrite behavior for extra_body).
        messages_arg = [{"role": "user", "content": "dummy_for_sdk_validation"}] 
    else:
        messages_arg = all_messages

    stream = client.with_options(
        base_url=chat["base_url"],
        api_key=getenv(chat["api_key_name"])
    ).chat.completions.create(
        messages=messages_arg,
        extra_body=final_extra_body if final_extra_body else None,
        **params
    )

    return stream


def get_anthropic_response(all_messages):
    all_messages = all_messages if not chat["vision_enabled"] else attach_images_anthropic_openai(
        all_messages)
    
    all_messages = apply_caching(all_messages)
    debug_print_payload(all_messages, "Anthropic")

    # Anthropic SDK handles specific structure for System vs Messages
    # If the first message is system, we extract it.
    system_input = []
    messages_payload = []
    
    # Check first message for system role
    if all_messages and all_messages[0]["role"] == "system":
        system_content = all_messages[0]["content"]
        
        # Anthropic 'system' param can be string or list of blocks
        # apply_caching might have turned it into a list with cache_control
        system_input = system_content
        messages_payload = all_messages[1:]
    else:
        messages_payload = all_messages

    stream = anthropic_client.messages.create(
        system=system_input,  # type: ignore
        model=chat["model"],
        messages=messages_payload,  # type: ignore
        stream=True,
        max_tokens=chat["max_tokens"],
        temperature=chat["temperature"],
        # frequency_penalty is not supported natively by Anthropic SDK
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
        if new_message["role"] == "assistant":
            new_message["role"] = "model"

        new_message["parts"] = [glm.Part(text=message["content"])]
        new_all_messages.append(new_message)

    attach_glm_images(new_all_messages)

    return new_all_messages


def attach_glm_images(new_all_messages):
    for image in chat["images"]:
        # this -1 is here because we removed the system message previously
        if (curr_idx := (image["message_idx"] - 1)) < len(new_all_messages):
            new_all_messages[curr_idx]["parts"].append(
                glm.Part(
                    inline_data=glm.Blob(
                        mime_type=f'image/{image["extension"]}',
                        data=base64.b64decode(image["content"])
                    )
                ),
            )


def attach_system_messages(all_messages):
    # We must preserve the cache_control flag if it exists on the system message
    new_system_message = {
        "role": "system",
        "content": all_messages[0]["content"],
        "cache_control": all_messages[0].get("cache_control", False)
    }

    if chat["auto_turns"] > 0:
        new_system_message["content"] += ("\n" + auto_system_message +
                                          "Number of turns left: " + str(chat["auto_turns"]))
    if chat["bash"] is True:
        new_system_message["content"] += ("\n" + bash_system_message)
    if chat["dalle"] is True:
        new_system_message["content"] += ("\n" + dalle_system_message)

    # If nothing changed content-wise and no cache control, return original
    if new_system_message["content"] == all_messages[0]["content"] and not new_system_message["cache_control"]:
        return all_messages
    else:
        new_all_messages = all_messages.copy()
        new_all_messages[0] = new_system_message
        return new_all_messages


def get_response(messages=None):
    if messages is None:
        messages = chat["all_messages"]

    # Filter out trailing empty assistant message (placeholder).
    # Some providers (Anthropic, Bedrock, Vercel) strictly reject empty content.
    # The server adds an empty assistant message to capture the stream, but it 
    # shouldn't be sent in the prompt unless it's a specific prefill (non-empty).
    if messages and messages[-1]['role'] == 'assistant' and not messages[-1]['content']:
        messages = messages[:-1]

    # I reversed this just to confuse you, dear reader (including myself, yes)
    messages = attach_files(messages) if chat["files"] else messages
    messages = attach_system_messages(messages)

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
            if num_of_updates in [1, 2, 3, 4]:

                # Update avg_delay using a simple moving average formula.
                avg_delay = (avg_delay + delay_since_last) / 2
            num_of_updates += 1

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
                    # maximum time to spend printing a chunk (in seconds)
                    max_chunk_time = 0.5
                    char_delay = avg_delay / \
                        len(text) if len(text) > 0 else min_delay
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
        # Propagate provider errors to callers (server/CLI) to handle appropriately
        raise

    finally:
        print(terminal["reset"] + "\n")


def get_and_print_response():
    try:
        text = get_response()
    except Exception as e:
        # CLI fallback: show error as a notification and append to last assistant message
        errorMessage = f"Error: {e}"
        alert(errorMessage)
        if chat["all_messages"] and chat["all_messages"][-1]["role"] == "assistant":
            chat["all_messages"][-1]["content"] += errorMessage
        else:
            add_message_to_chat("assistant", errorMessage)
        print(terminal["reset"] + "\n")
        return

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
            chat["all_messages"][-1]["content"] += char  # type: ignore
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
