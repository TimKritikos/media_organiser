import subprocess
import json
import os

def load_interface_data(input_data , source_number, query, arg=None):
    match query:
        case 'list-thumbnails':
            data = json.loads(subprocess.check_output([input_data["interface"], '-l', os.path.normpath(input_data["sources"][source_number])]))
        case 'get-related':
            if arg == None:
                print("Internal error: called load_interface_data without passing arg")
                return None
            data = json.loads(subprocess.check_output([input_data["interface"], '-g', arg]))
        case _:
            raise KeyError

    #TODO: Enable before release
    #if data["version"] != "v0.1.0":
    #    print("ERROR invalid api version on source media interface")
    #    return None

    return data
