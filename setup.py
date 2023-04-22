from setuptools import setup, find_packages
from setuptools.command.install import install
import os

class PreInstallCommand(install):
    def run(self):
        key = os.path.abspath("key.txt")
        db = os.path.abspath("history.db")
        audio = os.path.abspath("audio.wav")
        another_one = os.path.abspath("another_one.wav")

        with open("file_locations.py", "w") as file:
            file.write('key_location = ' + '"' + key + '"' + '\ndb_location = ' + '"' + db + '"' + '\n')
        with open("file_locations.py", "a") as file:
            file.write('audio_location = ' + '"' + audio + '"' + '\nanother_one_location = ' + '"' + another_one + '"' + '\n')

        key = input("What is your OpenAI API key? ")
        with open("key.txt", "w") as key_file:
            key_file.write(key)
        install.run(self)

setup(
    name="bashgpt",
    version="0.1",
    packages=find_packages(),
    install_requires=["cs50", "openai", "simpleaudio"],
    entry_points="""
    [console_scripts]
    dp=chat:main
    """,
    cmdclass={
        'install': PreInstallCommand,
    }
)
