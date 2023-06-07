import subprocess 

def execute_command(command):
    output = subprocess.check_output(command, shell=True, universal_newlines=True)
    return output
