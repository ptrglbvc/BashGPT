import pyaudio
import wave
import openai
import sys
from pynput import keyboard

CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1 if sys.platform == 'darwin' else 2
RATE = 44100
RECORD_SECONDS = 5


def main():
    if len(sys.argv)==3 and sys.argv[1]=="-f":
        whisper(sys.argv[2].strip())

    else:
        record()
        print(whisper("audio.wav"))
        

def record():
    with wave.open('audio.wav', 'wb') as wf:
        p = pyaudio.PyAudio()
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(p.get_sample_size(FORMAT))
        wf.setframerate(RATE)

        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True)

        print("\033[1m\033Recording 🎶 (press C-c to stop)\033[0m")
        try:
            while True: 
                wf.writeframes(stream.read(CHUNK))
        except KeyboardInterrupt:
            pass
        print("\n")

        stream.close()
        p.terminate()

def whisper(file):
    openai.api_key = open("key.txt", "r").read().strip()
    audio_file= open(file, "rb")
    transcript = openai.Audio.transcribe("whisper-1", audio_file).text
    return transcript

if (__name__)=="__main__":
    main()
