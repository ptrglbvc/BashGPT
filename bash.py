import subprocess 

def execute_command(command):

    try :
        output = subprocess.check_output(command, shell=True, universal_newlines=True)
    except:
        output = "Whoops, that didn't work."
    finally:
        return output
