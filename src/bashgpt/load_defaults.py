import json
from pathlib import Path

defaults_path = str(Path(__file__).parent.resolve()) + "/defaults.json"

def load_defaults():
    with open(defaults_path, "r") as defaults:
        if defaults:=defaults.read().strip():
            return json.loads(defaults)
    