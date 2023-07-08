import pyaudio
import wave
import openai

import sys
import os
from pathlib import Path

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
            pass
        print("\n")

        stream.close()
        p.terminate()

def whisper(file):
    openai.api_key = open(key_location, "r").read().strip()
    with open(file, "rb") as audio_file:
        try:
            transcript = openai.Audio.transcribe("whisper-1", audio_file).text
        except:
            transcript = "Voice recording didn't work."

    os.remove(file)
    return transcript

if (__name__)=="__main__":
    main()

