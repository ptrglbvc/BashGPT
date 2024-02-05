from pathlib import Path
import json

path = str(Path(__file__).parent.resolve()) + "/"
modes_path = path + "modes.json"
models_path = path + "models.json"

# short mode is the default mode, it has to exist, even if the json is deleted 
short_mode = ("Answer every question you get as shortly and as matter of factly "
              "as possible. Just focus on the answer to the question and nothing else. "
              "No fat. For example:'user: Who won the premier league? assistant: Manchester City.'"
              "Don't even use complete sentences if not needed.")

with open(modes_path, 'r') as jason:
    modes = json.load(jason)

with open(models_path, "r") as jason:
    models = json.load(jason)
