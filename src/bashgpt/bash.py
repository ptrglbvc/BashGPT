import subprocess
import threading
from time import sleep
import re
from queue import Queue, Empty
from bashgpt.chat import add_message_to_chat

bash_system_message = """
You are granted permissions to the user's access to the user's computer via the bash shell.
Whatever you write between <bash> and </bash> tags will get executed by the user, and you will get the Shell output in the messages
For example, if the user says: 'Please unzip the mom.zip file on my desktop and delete it.'
You should write: <bash>unzip ~/Desktop/mom.zip -d ~/Desktop/ && rm ~/Desktop/mom.zip</bash> in your message.
You can use cat and echo for writing and reading text files
"""

process = subprocess.Popen(
    ["/bin/sh"],  # Replace with your desired shell
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1  # Line-buffered
)

def execute_command(command):
    output = subprocess.getoutput(command)
    return output
#     global process
#     q = Queue()
#     # Capture both stdout and stderr
#     stdout_thread = threading.Thread(target=enqueue_output, args=(process.stdout, q, "stdout"))
#     stderr_thread = threading.Thread(target=enqueue_output, args=(process.stderr, q, "stderr"))
    
#     stdout_thread.daemon = True
#     stderr_thread.daemon = True
    
#     stdout_thread.start()
#     stderr_thread.start()

#     process.stdin.write(command + "\n")
#     process.stdin.flush()

#     # Wait and read all available lines from stdout and stderr
#     output_lines = []
#     while True:
#         try:
#             stream, line = q.get(timeout=1)
#         except Empty:
#             break
#         else:
#             output_lines.append((stream, line.strip()))

#     stdout = ""
#     stderr = ""
#     for stream, line in output_lines:
#         if stream == "stdout":
#             stdout += line + "\n"
#             print(line)
#         elif stream == "stderr":
#             stderr += line + "\n"

#     return stdout + stderr


# def enqueue_output(out, queue, stream_name):
#     for line in iter(out.readline, ''):
#         queue.put((stream_name, line))
#     out.close()


def bash(message):
    commands = parse_bash_message(message)

    for command in commands:
        try:
            output = execute_command(command)
            if output.strip():
                print("Shell response:\n" +  output)
                if len(output)<1000:
                    add_message_to_chat("user", "Shell response: " + output)
                else:
                    add_message_to_chat("user", "Shell response: " + output[:1000] + f"... {len(output) - 1000} more characters")
                    
        except Exception:
            pass


def parse_bash_message(message):
    pattern = re.compile(r"<bash>(.*?)</bash>", re.DOTALL)
    matches = pattern.findall(message)
    return matches
