import tkinter as tk
from tkinter import ttk

import spell_check

class NewProject(tk.Toplevel):
    def __init__(self, root, ShellScriptWindowCallback, ProjectListCallback ):
        super().__init__(root)
        self.title("Create project")
        self.geometry("400x70")
        self.attributes('-type', 'dialog')

        self.ProjectListCallback = ProjectListCallback
        self.ShellScriptWindowCallback = ShellScriptWindowCallback

        self.entry_frame = tk.Frame(self)
        self.entry_label = tk.Label(self.entry_frame, text="Name:")
        self.entry_label.grid(row=0, column=0, padx=(5, 0), pady=10)
        self.text = tk.Text(self.entry_frame)
        self.text.grid(row=0, column=1, sticky='we', padx=(5, 9))
        self.text.config(height=1)
        self.text.config(wrap='none')
        self.text.bind("<Return>", self.return_handle)
        self.text.bind('<Control-KeyRelease-a>', self.select_all)
        self.text.bind('<Control-KeyRelease-A>', self.select_all)

        self.danger_style = ttk.Style()
        self.danger_style.configure("Bad.TButton", background="#FF5E5E")
        self.danger_style.map("Bad.TButton", background=[('hover', '#FF0000')])
        self.danger_style.configure("Good.TButton", background="#82FF82")
        self.danger_style.map("Good.TButton", background=[('hover', '#00FF00')])

        self.button_grid = tk.Frame(self)
        self.spell_check_button = ttk.Button(self.button_grid, text="Spell check", command=self.spell_check_exec)
        self.spell_check_button.grid(row=0, column=0, padx=3, pady=3, sticky='we')
        self.space_to_underscore = ttk.Button(self.button_grid, text="Space to underscore", command=self.space_to_underscore_exec)
        self.space_to_underscore.grid(row=0, column=1, padx=3, pady=3, sticky='we')
        self.write_to_script = ttk.Button(self.button_grid, text="Write to script", command=self.write_to_script_exec)
        self.write_to_script.grid(row=0, column=2, padx=3, pady=3, sticky='we')

        self.entry_frame.grid(row=0, column=0, sticky='nwe')
        self.button_grid.grid(row=1, column=0, sticky='we')
        self.entry_frame.grid_rowconfigure(1, weight=1)
        self.entry_frame.grid_columnconfigure(1, weight=1)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.text.focus_set()

    def return_handle(self, event):
        if event.keysym == "Return":  # prevent newline
            return "break"
        if event.keysym == "Tab":  # move focus instead of inserting tab
            event.widget.tk_focusNext().focus()
            return "break"

    def spell_check_exec(self):
        if spell_check.spell_check(self) == 0:
            self.spell_check_button.configure(style="Good.TButton")
        else:
            self.spell_check_button.configure(style="Bad.TButton")

    def space_to_underscore_exec(self):
        text = self.text.get("1.0", "1.end")
        self.text.delete('1.0', tk.END)
        self.text.insert(tk.END, text.replace(' ', '_'))
        self.space_to_underscore.configure(style="Good.TButton")

    def write_to_script_exec(self):
        text = self.text.get("1.0", "1.end")
        active_tab=self.ProjectListCallback(text)
        self.ShellScriptWindowCallback(active_tab, text)
        self.destroy()

    def select_all(self, event=None):
        self.text.tag_add(tk.SEL, "1.0", tk.END)
