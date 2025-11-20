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

        self.dir_listbox = tk.Listbox(self, width=60)
        self.dir_listbox.delete(0, tk.END)
        self.dir_listbox.pack(fill="both", expand=True)

        self.full_update_list()

    def query_project_queued_in_script(self, name):
        try:
            self.dirs_in_script.index(name)
        except ValueError:
            return False
        else:
            return True

    def clear_projects_queued_in_script(self):
        self.dirs_in_script = []

    def full_update_list(self):
        self.dirs = [new_item for new_item in os.listdir(self.destinations[0]) if os.path.isdir(os.path.join(self.destinations[0], new_item))]
        self.update_list()

    def update_list(self, event=None):
        self.listbox_items = []

        for d in self.dirs_in_script:
            self.listbox_items.append(d)
        try:
            for d in self.dirs:
                if self.searchbox_status == 'unfocused' or any(True for _ in re.finditer(self.searchbox.get(), d)):
                    self.listbox_items.append(d)
        except re.error:
            self.searchbox.config(bg='red')
        else:
            self.searchbox.config(bg='white')

        self.listbox_items.sort()

        self.dir_listbox.delete(0,'end')
        for d in self.listbox_items:
            self.dir_listbox.insert(tk.END, d)
            if d in self.dirs_in_script:
                self.dir_listbox.itemconfig(tk.END, {'bg': 'yellow'})

    def new_project(self, event=None):
        self.NewProject = new_project.NewProject(self, self.ShellScriptNewProjectCallback, self.new_project_callback)

    def new_project_callback(self, name):
        self.dirs_in_script.append(name)
        self.update_list()
        self.dir_listbox.see(self.listbox_items.index(name))

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
        selection = self.dir_listbox.curselection()
        if not selection:
            return None
        else:
            return self.dir_listbox.get(selection[0])

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
