from pathlib import Path
import json

def data_loader(base_path=None, file_names=None):
    base_path = base_path or str(Path(__file__).parent.resolve()) + "/"
    file_names = file_names or {
        "modes": "modes.json",
        "models": "models.json",
        "providers": "providers.json"
    }

    data = {}
    for key, file_name in file_names.items():
        file_path = base_path + file_name
        with open(file_path, 'r') as jason:
            data[key] = json.load(jason)

    return data["modes"], data["models"], data["providers"]
