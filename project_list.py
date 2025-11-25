import re
import tkinter as tk
from tkinter import ttk
import os

import new_project

class  ProjectList(tk.Frame):
    def __init__(self, root, destinations, ShellScriptNewProjectCallback):
        super().__init__(root, bd=2, relief="sunken")

        self.dirs_in_script = []
        self.destinations = destinations
        self.ShellScriptNewProjectCallback = ShellScriptNewProjectCallback

        self.toolbox = tk.Frame(self)
        self.case_insensitive_button = ttk.Button(self.toolbox, text="Case insensitive", command=self.case_insensitive_insert)
        self.case_insensitive_button.pack(side=tk.LEFT, padx=(4, 2), pady=2)
        self.case_insensitive_button = ttk.Button(self.toolbox, text="New project", command=self.new_project)
        self.case_insensitive_button.pack(side=tk.LEFT, padx=(2, 4), pady=2)
        self.toolbox.pack(fill=tk.X)

        self.searchbox = tk.Entry(self)
        self.searchbox.bind('<KeyRelease>', self.update_list)
        self.searchbox_description = "Enter a search regex"
        self.searchbox.bind("<FocusIn>", self.searchbox_focused)
        self.searchbox.bind("<FocusOut>", self.searchbox_unfocused)
        self.searchbox.bind('<Control-KeyRelease-a>', self.select_all)
        self.searchbox.bind('<Control-KeyRelease-A>', self.select_all)
        self.searchbox.pack(fill=tk.X)
        self.searchbox_unfocused()

        self.notebook=ttk.Notebook(self)

        self.dir_listboxes = []
        for index, destination in enumerate(destinations):
            dir_listbox = tk.Listbox(self.notebook, width=60)
            self.notebook.add(dir_listbox, text=f'Tab {index}', sticky='nswe')
            self.dir_listboxes.append(dir_listbox)
            self.dirs_in_script.append([])
        self.notebook.pack(fill="both", expand=True)

        self.full_update_list()

    def query_project_queued_in_script(self, dest_id, name):
        try:
            self.dirs_in_script[dest_id].index(name)
        except ValueError:
            return False
        else:
            return True

    def clear_projects_queued_in_script(self):
        self.dirs_in_script = []
        for i in self.destinations:
            self.dirs_in_script.append([])

    def full_update_list(self):
        self.dirs = []
        for index,dir in enumerate(self.destinations):
            self.dirs.append([new_item for new_item in os.listdir(self.destinations[index]) if os.path.isdir(os.path.join(self.destinations[index], new_item))])
        self.update_list()

    def update_list(self, event=None):
        self.listbox_items = []

        for i in self.destinations:
            self.listbox_items.append([])

        for index, dirs in enumerate(self.dirs_in_script):
            for d in dirs:
                self.listbox_items[index].append(d)
        try:
            for dest_index, dest_dirs in enumerate(self.dirs):
                for project in dest_dirs:
                    if self.searchbox_status == 'unfocused' or any(True for _ in re.finditer(self.searchbox.get(), project)):
                        self.listbox_items[dest_index].append(project)
        except re.error:
            self.searchbox.config(bg='red')
        else:
            self.searchbox.config(bg='white')

        for i in self.listbox_items:
            i.sort()

        for listbox_index, dir_listbox in enumerate(self.dir_listboxes):
            dir_listbox.delete(0,'end')
            for project in self.listbox_items[listbox_index]:
                dir_listbox.insert(tk.END, project)
                if project in self.dirs_in_script[listbox_index]:
                    dir_listbox.itemconfig(tk.END, {'bg': 'yellow'})

    def new_project(self, event=None):
        self.NewProject = new_project.NewProject(self, self.ShellScriptNewProjectCallback, self.new_project_callback)

    def get_visible_tab(self):
        return self.notebook.index(self.notebook.select())

    def new_project_callback(self, name):
        current_tab=self.get_visible_tab()
        self.dirs_in_script[current_tab].append(name)
        self.update_list()
        self.dir_listboxes[current_tab].see(self.listbox_items[current_tab].index(name))
        return self.get_visible_tab()

    def case_insensitive_insert(self, event=None):
        if self.searchbox_status == 'unfocused':
            self.searchbox_focused()
        self.searchbox.insert("end", "(?i)")
        self.searchbox.focus_set()
        self.searchbox.icursor('end')
        self.update_list()

    def select_all(self, event=None):
        self.searchbox.select_range(0, 'end')
        self.searchbox.icursor('end')

    def get_selected_dir(self):
        current_tab = self.get_visible_tab()
        selection = self.dir_listboxes[current_tab].curselection()
        if not selection:
            return None
        else:
            return current_tab, self.dir_listboxes[current_tab].get(selection[0])

    def searchbox_focused(self, event=None):
        if self.searchbox.get() == self.searchbox_description:
            self.searchbox.delete(0, tk.END)
            self.searchbox.config(fg='black')
            self.searchbox_status = 'focused'

    def searchbox_unfocused(self, event=None):
        if self.searchbox.get() == '':
            self.searchbox.insert(0, self.searchbox_description)
            self.searchbox.config(fg='grey')
            self.searchbox_status = 'unfocused'
