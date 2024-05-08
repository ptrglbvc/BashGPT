from pathlib import Path
import json

path = str(Path(__file__).parent.resolve()) + "/"
modes_path = path + "modes.json"
models_path = path + "models.json"

with open(modes_path, 'r') as jason:
    modes = json.load(jason)

with open(models_path, "r") as jason:
    models = json.load(jason)
