import pyaudio
import wave
from openai import OpenAI

import sys
import os
from pathlib import Path

from bashgpt.db_and_key import setup_key

client = OpenAI()

chunk = 1024
format = pyaudio.paInt16
channels = 1 if sys.platform == 'darwin' else 2
rate = 44100
record_seconds = 5

path = str(Path(__file__).parent.resolve()) + "/"
audio_location = path + "audio.wav"
key_location = path + "key.txt"


def main():
    if len(sys.argv)==3 and sys.argv[1]=="-f":
        whisper(sys.argv[2].strip())

    else:
        record()
        print(whisper(audio_location))
        os.remove(audio_location)
        

def record():
    with wave.open(audio_location, 'wb') as wf:
        p = pyaudio.PyAudio()
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)

        stream = p.open(format=format, channels=channels, rate=rate, input=True)

        print("\033[1m\033[31mRecording 🎶 (press C-c to stop)\033[0m")
        try:
            while True: 
                wf.writeframes(stream.read(chunk))
        except KeyboardInterrupt:
            print("\r   ")


        stream.close()
        p.terminate()
    return audio_location

def whisper(file):
    client.api_key = setup_key()
    with open(file, "rb") as audio_file:
        try:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            ).text
        except:
            transcript = "Voice recording didn't work."

    return transcript

if (__name__)=="__main__":
    main()

