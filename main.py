import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import argparse
from tkinter import ttk
import subprocess
import os
import multiprocessing

import full_screen_view
import item_grid
import project_list
import shell_script_window
import spell_check
import media_interface
import constants

#TODO: Add preference for gpx files in gnss track code

class CmdLineError(Exception):
    pass


class CountCallbackSet:
    def __init__(self):
        self.set = set()
        self.callback = None

    def add(self, item):
        self.set.add(item)
        self.call_callbacks()

    def remove(self, item):
        self.set.remove(item)
        self.call_callbacks()

    def __len__(self):
        return len(self.set)

    def __iter__(self):
        return iter(self.set)

    def call_callbacks(self):
        if self.callback != None:
            self.callback()

    def register_callback(self, callback):
        self.callback = callback


class MediaSelectorApp:
    def __init__(self, root, unsanitised_input_data, processing_thread_count, thumb_size=(180, 180), item_border_size=6, item_padding=10, profile_item_loading_filename=None):
        self.input_data = {}

        if not os.path.isfile(unsanitised_input_data["interface"]):
            raise CmdLineError("Following provided interface file doesn't exist or isn't a file: '"+unsanitised_input_data["interface"]+"'")
        if not os.access(unsanitised_input_data["interface"], os.X_OK):
            raise CmdLineError("Following provided interface file isn't executable: '"+unsanitised_input_data["interface"]+"'")
        self.input_data["interface"]=os.path.normpath(unsanitised_input_data["interface"])

        if unsanitised_input_data["map_database"] != None:
            self.input_data["map_database"] = os.path.normpath(unsanitised_input_data["map_database"])
        else:
            self.input_data["map_database"] = None
        self.input_data["force_offline"] = unsanitised_input_data["force_offline"]

        self.input_data["sources"]=[]
        for source in unsanitised_input_data["sources"]:
            if not os.path.isdir(source):
                raise CmdLineError("Following provided source directory doesn't exist: '"+source+"'")
            self.input_data["sources"].append((os.path.normpath(source), constants.source_properties.normal))
        if "read_only_source" in unsanitised_input_data:
            for source in unsanitised_input_data["read_only_source"]:
                if not os.path.isdir(source):
                    raise CmdLineError("Following provided source directory doesn't exist: '"+source+"'")
                self.input_data["sources"].append((os.path.normpath(source), constants.source_properties.read_only))

        self.input_data["destinations"]=[]
        for destination in unsanitised_input_data["destinations"]:
            if not os.path.isdir(destination):
                raise CmdLineError("Following provided destination directory doesn't exist: '"+destination+"'")
            self.input_data["destinations"].append(os.path.normpath(destination))

        self.input_data["destinations_append"]=unsanitised_input_data["destinations_append"]

        self.selected_items = CountCallbackSet()  # set of selected file paths

        root.title("MEDIA organiser")

        self.upper_and_shell_pane = ttk.PanedWindow(root, orient=tk.VERTICAL)

        self.list_grid_pane = ttk.PanedWindow(self.upper_and_shell_pane, orient=tk.HORIZONTAL)

        self.grid_and_toolbar = tk.Frame(self.list_grid_pane)

        self.ItemGrid = item_grid.ItemGrid(self.grid_and_toolbar, thumb_size, item_border_size, item_padding, self.selected_items, self.input_data, self.enter_full_screen, self.select_all_callback, self.update_progress_bar, media_interface.load_interface_data, root, profile_item_loading_filename, processing_thread_count)
        self.item_count = len(self.ItemGrid.item_list)

        self.toolbar = tk.Frame(self.grid_and_toolbar, bd=3)
        self.toolbar.config(relief="groove")

        self.danger_style = ttk.Style()
        self.danger_style.configure("Danger.TButton", background="#d18282")
        self.danger_style.map("Danger.TButton", background=[('hover', '#cf3838')])
        self.danger_style.configure("Normal.TButton", background="#82b5d1")
        self.danger_style.map("Normal.TButton", background=[('hover', '#3899cf')])
        self.danger_style.configure("Clear.TButton", background="#424242", foreground='#DDDDDD')
        self.danger_style.map("Clear.TButton", background=[('hover', '#000000')])

        self.execute_button = ttk.Button(self.toolbar, text="Execute", command=self.execute_shell, style="Danger.TButton")
        self.execute_button.pack(side=tk.LEFT, padx=(4, 2), pady=2)

        self.add_to_script_button = ttk.Button(self.toolbar, text="Add to script", command=self.add_to_script, style="Normal.TButton")
        self.add_to_script_button.pack(side=tk.LEFT, padx=2, pady=2)

        self.clear_script_button = ttk.Button(self.toolbar, text="Clear script", command=self.clear_shell_script, style="Clear.TButton")
        self.clear_script_button.pack(side=tk.LEFT, padx=2, pady=2)

        self.clear_script_button = ttk.Button(self.toolbar, text="Export script", command=self.export_shell_script)
        self.clear_script_button.pack(side=tk.LEFT, padx=(2, 4), pady=2)

        ttk.Separator(self.toolbar, orient='vertical').pack(side=tk.LEFT, padx=(5, 5), fill=tk.Y)

        self.select_all_button = tk.Button(self.toolbar, text="Select All", command=self.select_all)
        self.select_all_button.pack(side=tk.LEFT, padx=2)

        self.select_none_button = tk.Button(self.toolbar, text="Select None", command=self.select_none)
        self.select_none_button.pack(side=tk.LEFT, padx=2)

        self.select_invert_button = tk.Button(self.toolbar, text="Invert selections", command=self.select_invert)
        self.select_invert_button.pack(side=tk.LEFT, padx=2)

        self.item_count_label = tk.Label(self.toolbar, text="")
        self.item_count_label.pack(side=tk.RIGHT, padx=2)

        ttk.Separator(self.toolbar, orient='vertical').pack(side=tk.RIGHT, padx=(5, 5), fill=tk.Y)

        self.progress_bar = ttk.Progressbar(self.grid_and_toolbar)

        self.ItemGrid.grid(row=0, column=0, sticky='nswe')
        self.progress_bar.grid(row=1, column=0, sticky='we')
        self.grid_and_toolbar.grid_rowconfigure(0, weight=1)
        self.grid_and_toolbar.grid_columnconfigure(0, weight=1)

        self.bash_side_channel_read_fd = None
        self.bash_side_channel_write_fd = None
        self.ShellScriptWindow = shell_script_window.ShellScriptWindow(self.upper_and_shell_pane, self.input_data)
        self.ShellScriptWindow.grid(row=0, column=0, sticky='nswe')
        self.ShellScriptWindow.grid_rowconfigure(0, weight=1)
        self.ShellScriptWindow.grid_columnconfigure(0, weight=1)

        self.ProjectList = project_list.ProjectList(self.list_grid_pane, self.input_data["destinations"], self.ShellScriptWindow.new_project_callback)

        self.ShellScriptWindow.query_project_queued_in_script = self.ProjectList.query_project_queued_in_script
        self.clear_shell_script()

        self.list_grid_pane.add(self.grid_and_toolbar, weight=1)
        self.list_grid_pane.add(self.ProjectList, weight=1)

        self.upper_and_shell_pane.add(self.list_grid_pane, weight=1)
        self.upper_and_shell_pane.add(self.ShellScriptWindow, weight=0)

        self.upper_and_shell_pane.grid (row=0, column=0, sticky='nswe')
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.selected_items.register_callback(self.update_counters)
        self.selected_items.call_callbacks() # Write initial text on the counter label

        self.shell_script_error_line = None

    def update_progress_bar(self, items):
        if items != self.item_count:
            self.progress_bar["value"] = (items*100)/self.item_count
        else:
            self.progress_bar.grid_forget()
            self.toolbar.grid(row=1, column=0, sticky='we')
            self.update_counters()

    def enter_full_screen(self, path):
        try:
            self.FullScreenItem = full_screen_view.FullScreenItem(self.grid_and_toolbar, self.input_data, path, self.exit_full_screen)
            self.ItemGrid.grid_forget()
            self.FullScreenItem.grid(row=0, column=0, sticky='nswe')
        except subprocess.CalledProcessError:
            pass

    def exit_full_screen(self):
        self.FullScreenItem.grid_forget()
        self.FullScreenItem.destroy()
        self.ItemGrid.grid(row=0, column=0, sticky='nswe')

    def recycle_bash_side_channel_pipe(self):
        if self.bash_side_channel_read_fd != None:
            os.close(self.bash_side_channel_read_fd)
        if self.bash_side_channel_write_fd != None:
            os.close(self.bash_side_channel_write_fd)
        self.bash_side_channel_read_fd, self.bash_side_channel_write_fd = os.pipe()

    def clear_shell_script(self):
        self.recycle_bash_side_channel_pipe()
        self.ShellScriptWindow.clear(self.bash_side_channel_write_fd)
        self.shell_script_error = None
        self.ProjectList.clear_projects_queued_in_script()
        self.ProjectList.full_update_list()

    def execute_shell(self):
        if len(self.selected_items) != 0:
            messagebox.showinfo("Error", "Error: Cannot have selected items when executing. Did you forget to add them to the script?")
            return

        if self.shell_script_error != None:
            self.ShellScriptWindow.unmark_error_line(self.shell_script_error)

        shell_script_string = self.ShellScriptWindow.get_script()

        bash_process = subprocess.Popen(["bash", "-c", shell_script_string], pass_fds=(self.bash_side_channel_write_fd, ))

        os.close(self.bash_side_channel_write_fd)
        self.bash_side_channel_write_fd = None

        with os.fdopen(self.bash_side_channel_read_fd, 'r') as f:
            error_line = f.read().strip()
        self.bash_side_channel_read_fd = None

        bash_process.wait()

        self.recycle_bash_side_channel_pipe()
        if bash_process.returncode != 0:
            self.shell_script_error = error_line
            self.ShellScriptWindow.mark_error_line(error_line)
            messagebox.showinfo("Error", "ERROR: Shell exit with an error code\nThe line that caused the error has been highlighted red")
            self.ShellScriptWindow.update_bash_side_channel_write_fd(self.bash_side_channel_write_fd)
        else:
            self.shell_script_error = None
            self.ItemGrid.checkmark_items(self.ShellScriptWindow.get_items_in_script())
            self.update_counters()
            self.ShellScriptWindow.clear(self.bash_side_channel_write_fd)
            self.ProjectList.clear_projects_queued_in_script()
            self.ProjectList.full_update_list()

    def update_counters(self):
        total=len(self.ItemGrid.items)
        selected=len(self.selected_items)
        linked=self.ItemGrid.linked_count
        self.item_count_label.config(text=f"Total: {total} Linked: {linked} Selected: {selected}")

    def select_all_callback(self, event=None):
        self.select_all()

    def select_all(self):
        for i in self.ItemGrid.items:
            i.select()

    def select_none(self):
        for i in self.ItemGrid.items:
            if i.get_file_path() in self.selected_items:
                i.deselect()

    def select_invert(self):
        for i in self.ItemGrid.items:
            if i.get_file_path() in self.selected_items:
                i.deselect()
            else:
                i.select()

    def export_shell_script(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".sh", filetypes=[("Shell Script", "*.sh")])
        if not save_path:
            return
        with open(save_path, "w") as f:
            f.write(self.ShellScriptWindow.get_script())

    def add_to_script(self):
        selected_tab, selected_project = self.ProjectList.get_selected_dir()
        if not selected_project:
            messagebox.showinfo("Selection", "No project selection")
            return

        if not self.selected_items:
            messagebox.showinfo("Selection", "No items selected.")
            return

        linked_already=[]
        destination_dir=self.ShellScriptWindow.get_destination_dir(selected_tab,selected_project);
        if not self.ProjectList.query_project_queued_in_script(selected_tab, selected_project) :
            for dirpath, dirnames, filenames in os.walk(destination_dir, followlinks=False):
                for filename in filenames:
                    full_path = os.path.join(dirpath, filename)
                    if os.path.islink(full_path):
                        link_destination = os.path.realpath(full_path)
                        linked_already.append((link_destination,filename,dirpath))
        try:
            for file_id in self.selected_items:
                for file_to_link in media_interface.load_interface_data(self.input_data, 0, 'get-related', arg=file_id)["file_list"]:
                    for i in linked_already:
                        if i[0] == file_to_link["file_path"]:
                            messagebox.showinfo("Error", f"ERROR: file \"{file_to_link["file_path"]}\" is already linked as \"{i[1]}\" in \"{i[2]}\"")
                            return
                    self.ShellScriptWindow.add_file(file_to_link["file_path"], selected_tab, selected_project)
        except FileNotFoundError as error_message:
            messagebox.showinfo("ERROR", error_message)
        except ValueError as error_message:
            messagebox.showinfo("ERROR", error_message)

        self.select_none()


def main():
    version = "v0.0-dev"

    root = tk.Tk()
    root.geometry("1000x600")

    parser = argparse.ArgumentParser(description='Select and symlink media from one directory to another')
    parser.add_argument('-i', '--interface',            type=str,                                         required=True,  help='Path to source direcotry interface executable')
    parser.add_argument('-s', '--source',               type=str,  action='append',                       required=True,  help='Path to the source directory of media to get linked. This can be entered multiple times')
    parser.add_argument('-r', '--read-only-source',     type=str,  action='append',                                       help='Like the -s flag but the items will only be visiable, not selectable for linking. Usualy used for context for the items to be selected')
    parser.add_argument('-d', '--destination',          type=str,  action='append',                       required=True,  help='Path to the distention directory for the links to stored in. This can be entered multiple times')
    parser.add_argument('-a', '--destination-append',   type=str,                                                         help='Path to be appended to the project directory selected in the destination directory. For example if media needs to be linked in a sub-folder')
    parser.add_argument('-v', '--version',                         action="version",                                      help='print the version of this program and exit successfully',  version=version)
    parser.add_argument('-p', '--profile-item-loading', type=str,                                         required=False, help='Run a profiler on the code that loads the items, save the data under the provided filename and exit')
    parser.add_argument('-j', '--jobs',                 type=int,                                         required=False, help='The number of jobs to run simultaneously. Currently this is used for reading and processing the input data when starting up. By default the number of availiable threads is used.')
    parser.add_argument('-m', '--map-database',         type=str,                                         required=False, help='Path to a database of tile images to look through before loading from the network')
    parser.add_argument('-O', '--force-offline',        type=bool, action=argparse.BooleanOptionalAction, required=False, help='Disable fetching resources from the network')

    args = parser.parse_args()

    if args.jobs == None:
        jobs=multiprocessing.cpu_count()
    else:
        jobs=args.jobs

    input_data = {
        "interface": args.interface,
        "sources": args.source,
        "destinations": args.destination,
        "destinations_append": (args.destination_append if args.destination_append is not None else ""),
        "force_offline": args.force_offline,
        "map_database": args.map_database
    }

    if input_data["force_offline"] == None:
        input_data["force_offline"]=False

    if args.read_only_source != None:
        input_data["read_only_source"]= args.read_only_source

    try:
        app = MediaSelectorApp(root, input_data, jobs, profile_item_loading_filename=args.profile_item_loading)
    except CmdLineError as error_message:
        print(f"ERROR: {error_message}", file=sys.stderr)
        sys.exit(1)

    app.ItemGrid.start_loading()

    root.mainloop()


if __name__ == "__main__":
    main()
