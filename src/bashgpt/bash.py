import subprocess
import threading
from queue import Queue, Empty
from bashgpt.chat import add_message_to_chat


process = subprocess.Popen(
    ["/bin/sh"],  # Replace with your desired shell
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1  # Line-buffered
)

def execute_command(command):
    global process
    q = Queue()
    # Capture both stdout and stderr
    stdout_thread = threading.Thread(target=enqueue_output, args=(process.stdout, q, "stdout"))
    stderr_thread = threading.Thread(target=enqueue_output, args=(process.stderr, q, "stderr"))
    
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    
    stdout_thread.start()
    stderr_thread.start()

    process.stdin.write(command + "\n")
    process.stdin.flush()

    # Wait and read all available lines from stdout and stderr
    output_lines = []
    while True:
        try:
            stream, line = q.get(timeout=1)
        except Empty:
            break
        else:
            output_lines.append((stream, line.strip()))

    stdout = ""
    stderr = ""
    for stream, line in output_lines:
        if stream == "stdout":
            stdout += line + "\n"
        elif stream == "stderr":
            stderr += line + "\n"

    return stdout + stderr


def enqueue_output(out, queue, stream_name):
    for line in iter(out.readline, ''):
        queue.put((stream_name, line))
    out.close()


def parse_bash_message(message):
    all_parts = message.split("```")
    if len(all_parts) > 1:
        commands = all_parts[1::2]
        for command in commands:

            if command.strip().startswith("bash"):
                command = command.strip()[4:]
            if command.strip().startswith("zsh"):
                command = command.strip()[3:]

            try:
                output = execute_command(command)
                if output.strip():
                    print("Shell response:\n" +  output)
                    if len(output)<1000:
                        add_message_to_chat("user", "Shell response: " + output)
                    else:
                        add_message_to_chat("user", "Shell response: " + output)
                    
            except Exception:
                pass
