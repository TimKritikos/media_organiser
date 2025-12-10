import subprocess
import json
import os
from tkinter import messagebox

def load_interface_data(input_data , source_number, query, arg=None):
    match query:
        case 'list-thumbnails':
            command = [input_data["interface"], '-l', os.path.normpath(input_data["sources"][source_number][0])]
        case 'get-related':
            if arg == None:
                messagebox.showinfo("Error", "Internal error: called load_interface_data without passing arg")
                raise ValueError
            command = [input_data["interface"], '-g', arg]
        case _:
            raise CalledProcessRtt

    try:
        data = json.loads(subprocess.check_output(command))
    except subprocess.CalledProcessError as error:
        error = json.loads(error.stdout)["error_string"]
        messagebox.showinfo("Error", "Error with media interface: " + error )
        raise error

    if data["version"].split('.')[0] != "1":
        messagebox.showinfo("Error", "ERROR invalid api version on source media interface")
        raise error

    return data
