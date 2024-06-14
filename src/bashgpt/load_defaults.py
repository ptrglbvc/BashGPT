import json
from pathlib import Path
from os.path import exists

defaults_path = str(Path(__file__).parent.resolve()) + "/defaults.json"

def load_defaults():
    if not exists(defaults_path):
        open(defaults_path, 'a').close()
        
    
    with open(defaults_path, "r") as defaults:
        if defaults:=defaults.read().strip():
            return json.loads(defaults)
    