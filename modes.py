from pathlib import Path
import json

path = str(Path(__file__).parent.resolve()) + "/"
jason_path = path + "modes.json"

# short mode is the default mode, it has to exist, even if the json is deleted 
short_mode = ("Answer every question you get as shortly and as matter of factly "
              "as possible. Just focus on the answer to the question and nothing else. "
              "No fat. For example: Who won the premier league? - Manchester City. "
              "Don't even use complete sentences if not needed.")

with open(jason_path, 'r') as jason:
    modes = json.load(jason)
