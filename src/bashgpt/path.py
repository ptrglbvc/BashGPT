from os import path
from pathlib import Path

def get_path():
    return str(Path(path.realpath(__file__)).parent) + "/"