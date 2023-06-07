import subprocess

# Start the shell process
shell = subprocess.Popen(['bash'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, universal_newlines=True)

# Send commands to the shell
shell.stdin.write('cd /path/to/directory\n')
shell.stdin.write('ls\n')
subprocess.call('clear', shell=True)
shell.stdin.write('echo "Hello, World!"\n')

# Close the shell process to indicate the end of input
shell.stdin.close()


print(shell.stdout)


