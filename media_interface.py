import subprocess
import json
import os
from tkinter import messagebox

def load_interface_data(input_data , source_number, query, arg=None):
    match query:
        case 'list-thumbnails':
            command=[input_data["interface"], '-l', os.path.normpath(input_data["sources"][source_number][0])]
        case 'get-related':
            if arg == None:
                print("Internal error: called load_interface_data without passing arg")
                return None
            command=[input_data["interface"], '-g', arg]
        case _:
            raise CalledProcessRtt

    try:
        data = json.loads(subprocess.check_output(command))
    except subprocess.CalledProcessError as error:
        error=json.loads(error.stdout)["error_string"]
        messagebox.showinfo("Error", "Error with media interface: "+error)
        raise error


    #TODO: Enable before release
    #if data["version"] != "v0.1.0":
    #    print("ERROR invalid api version on source media interface")
    #    return None

    return data
