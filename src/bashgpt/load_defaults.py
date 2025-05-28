import json
from os.path import exists

def load_defaults(path):
    defaults_path = path + "/defaults.json"
    if not exists(defaults_path):
        open(defaults_path, 'a').close()


    with open(defaults_path, "r") as defaults:
        if defaults:=defaults.read().strip():
            return json.loads(defaults)
        else:
            return {
            "color": "blue",
            "model": {
                "name": "claude-3-5-sonnet-20240620",
                "shortcut": "sonnet",
                "provider": "anthropic",
                "vision_enabled": True
            },
            "mode": {
                "description": (
                    "Answer every question you get as shortly and as matter of factly as possible. "
                    "Just focus on the answer to the question and nothing else. No fat. For example: "
                    "'user: Who won the premier league? assistant: Manchester City.' "
                    "Don't even use complete sentences if not needed."
                ),
                "name": "short",
                "shortcut": "s"
            }
        }
