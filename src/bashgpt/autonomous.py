import re

auto_system_message = """
You have been granted autonomous mode by the user.
You can type his messages for him, thereby continuing the chat indefinitely. 
The messages you type between <user> and </user> tags will show up in his chat.
You can use this for uploading images with this command <user> /i "path_to_image.png" "A message for yourself" </user>.
If you do not type a message for the user, a message "You are in control."
"""


def parse_auto_message(message):
    pattern = re.compile(r"<user>(.*?)</user>", re.DOTALL)
    matches = pattern.findall(message)
    return "\n".join(matches)

        
        