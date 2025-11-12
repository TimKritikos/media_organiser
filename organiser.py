import json
import os
from datetime import datetime
from datetime import timezone
import sys
from exif import Image as exifImage
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import subprocess
import argparse
from tkinter import ttk
import re
import nltk
from nltk.corpus import words
from nltk.corpus import wordnet

#TODO: Check if a file is already linked in the destination directory
#TODO: add a file view mode
#TODO: add multiple source and destinations support
#TODO: Sort items by create date in the grid
#TODO: Add second thread for loading images to bring up the UI faster
#TODO: Add metadata specialised metadata for Optical Image stabilisation and other professional camera metadata that could possibly be useful in selection of images

TK_SHIFT_MASK    = 0x0001
TK_CONTROL_MASK  = 0x0004

class CmdLineError(Exception):
    pass
class DoubleSlash(Exception):
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
            self.callback(len(self.set))

    def register_callback(self, callback):
        self.callback = callback


class Item(tk.Frame):

    last_selected = None
    mouse_action = 1

    def __init__(self, root, item_data, selected_items, input_data, input_data_source_index, thumb_size, bg_color, select_color, enter_callback, leave_callback, full_screen_callback, shift_select_callback, select_all_callback, **kwargs):
        super().__init__(root, **kwargs)

        self.selected_items = selected_items
        self.dragged_over = set()
        self.bg_color = bg_color
        self.select_color = select_color
        self.filename_path = os.path.join(input_data["sources"][input_data_source_index], item_data["filename"])
        self.full_screen_callback = full_screen_callback
        self.shift_select_callback = shift_select_callback
        self.select_all_callback = select_all_callback

        if not self.filename_path or not os.path.exists(self.filename_path):
            print("ERROR: file in json from source media interface executable couldn't be found")
            return -1

        #Create thumbnail image
        if item_data["file_type"] in ["image-preview", "image"]:
            try:
                img = Image.open(self.filename_path).convert("RGB")
                img.thumbnail(thumb_size)
                self.photo_obj = ImageTk.PhotoImage(img)
            except Exception:
                img = Image.new("RGB", thumb_size, (100, 100, 100))
                self.photo_obj = ImageTk.PhotoImage(img)
        else:
            img = Image.new("RGB", thumb_size, (60, 60, 60))
            self.photo_obj = ImageTk.PhotoImage(img)

        self.image = tk.Label(self, image=self.photo_obj, borderwidth=0)
        self.image.pack()
        self.caption = tk.Label(self, text=os.path.basename(self.filename_path), wraplength=thumb_size[0], borderwidth=0)
        self.caption.pack()

        for i in (self.image, self.caption, self):
            i.bind("<Button-1>", self.on_click)
            i.bind("<B1-Motion>", self.on_drag)
            i.bind("<Enter>", enter_callback)
            i.bind("<Leave>", leave_callback)
            i.bind("<Key>", self.key_callback)

    def key_callback(self, event):
        if event.char == '\r' :
            self.full_screen_callback(self.filename_path)
        if event.state & TK_CONTROL_MASK and event.keysym == 'a':
            self.select_all_callback()

    def deselect(self):
        for i in (self.image, self.caption, self):
            i.config(bg=self.bg_color)
        if self.filename_path in self.selected_items:
            self.selected_items.remove(self.filename_path)

    def select(self):
        for i in (self.image, self.caption, self):
            i.config(bg=self.select_color)
        self.selected_items.add(self.filename_path)

    def on_click(self, event):
        self.dragged_over.clear()
        if self.filename_path in self.selected_items:
            self.deselect()
            Item.mouse_action = 0
        else:
            self.select()
            Item.mouse_action = 1
        self.dragged_over.add(self)
        if event.state & TK_SHIFT_MASK and Item.last_selected != None:
            self.shift_select_callback(Item.last_selected,self,Item.mouse_action)
        Item.last_selected=self

    def get_filename_path(self):
        return self.filename_path

    def on_drag(self, event):
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return
        while widget and not isinstance(widget, Item):
            widget = widget.master
        if isinstance(widget, Item) and widget not in self.dragged_over:
            if Item.mouse_action == 1:
                widget.select()
            else:
                widget.deselect()
            self.dragged_over.add(widget)


class FullScreenItem(tk.Frame):
    def __init__(self, root, input_data, filename, exit_callback, **kwargs):
        super().__init__(root, **kwargs)

        self.best_file = None
        self.exit_callback = exit_callback
        self.image = None
        self.old_image_size = (0, 0)

        data = load_interface_data(input_data, 0, 'get-related', arg=filename)

        for file in data["file_list"]:
            if file["item_type"] == file["file_type"]:
                self.best_file = file

        if self.best_file == None:
            raise ValueError

        self.best_file_path = os.path.join(input_data["sources"][0], self.best_file["filename"])

        self.image_frame = tk.Frame(self)
        self.metadata_frame = tk.Frame(self)

        with open(self.best_file_path, 'rb') as image_file:
            my_image = exifImage(self.best_file_path)

        self.metadata_labels = []
        if not my_image.has_exif:
            self.no_exif = tk.Label(self.metadata_frame, text="File doesn't have exif metadata")
            self.no_exif.grid(row=0, column=0)
            self.attach_binds(self.no_exif)
        else:
            #Process create date
            try:
                create_date_notz = datetime.strptime(my_image.datetime, '%Y:%m:%d %H:%M:%S')
                create_date = create_date_notz.replace(tzinfo=timezone.utc)
                create_date_str = create_date.strftime("%Y-%m-%d")
                create_time_str = create_date.strftime("%H:%M:%S")
            except AttributeError:
                create_date_str = ""
                create_time_str = ""

            #Process shutter speed
            try:
                if my_image.exposure_time < 1:
                    shutter_str = "1/"+str(1/my_image.exposure_time)+" s"
                else:
                    shutter_str = str(my_image.exposure_time)+" s"
            except AttributeError:
                shutter_str = ""

            self.metadata_canvas = tk.Canvas(self.metadata_frame, highlightthickness=0, width=220)
            self.metadata_canvas.grid(row=0, column=0, sticky='nswe')
            self.metadata_canvas.grid_rowconfigure(0, weight=1)
            self.metadata_canvas.grid_columnconfigure(0, weight=1)

            metadata_key_x_end = 120
            metadata_value_x_start = 125
            metadata_y_start = 20
            metadata_y_step = 15

            metadata = []
            for key in ("f_number", "photographic_sensitivity", "focal_length_in_35mm_film", "make", "model", "lens_make", "lens_model", "flash"):
                value = getattr(my_image, key, None)
                metadata.append(value if value is not None else "")


            for i, (key, value) in enumerate((
                ("Create date:", create_date_str),
                ("Create time:", create_time_str),
                ( "Aperture:", "f"+str(metadata[0])),
                ( "Shutter speed:", shutter_str),
                ( "ISO:", str(metadata[1])),
                ( "Focal Length (35mm):", str(metadata[2])+"mm"),
                ( "Camera make:", metadata[3]),
                ( "Camera name:", metadata[4]),
                ( "Lens make:", metadata[5]),
                ( "Lens model:", metadata[6]),
                ( "Flash:", metadata[7])
                )):
                y = metadata_y_start + i * metadata_y_step

                key_id = self.metadata_canvas.create_text(metadata_key_x_end, y, text=key, anchor="e", fill="#333")
                val_id = self.metadata_canvas.create_text(metadata_value_x_start, y, text=value, anchor="w", fill="#000")

            self.attach_binds(self.metadata_canvas)

        self.image_frame.grid(row=0, column=0, sticky='nswe')
        self.attach_binds(self.image_frame)

        self.metadata_frame.grid(row=0, column=1, sticky='nse')
        self.attach_binds(self.metadata_frame)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.attach_binds(self)

        self.img = Image.open(self.best_file_path).convert("RGB")

    def attach_binds(self, widget):
        widget.bind("<Configure>", lambda x: self.after_idle(self.update_size))
        widget.bind("<Key>", self.key_callback)
        widget.bind("<Enter>", lambda x: x.widget.focus_set() )

    def enter(self, event):
        event.widget.focus_set()

    def key_callback(self, event):
        if event.char == '\r':
            self.exit_callback()

    def update_size(self):
        frame_width = self.image_frame.winfo_width()
        frame_height = self.image_frame.winfo_height()
        image_size = (frame_width, frame_height)
        if image_size != self.old_image_size:
            self.old_image_size = image_size
            if self.image:
                self.image.destroy()
            if self.best_file["item_type"] in ["image-preview", "image"]:
                image_resized=self.img.copy()
                image_resized.thumbnail(image_size)
            else:
                image_resized = Image.new("RGB", image_size, (60, 60, 60))

            self.photo_obj = ImageTk.PhotoImage(image_resized)
            self.image = tk.Label(self.image_frame, image=self.photo_obj, borderwidth=0)
            self.image.grid(row=0, column=0, sticky='nw')


class ItemGrid(tk.Frame):
    def __init__(self, root, thumb_size, item_border_size, item_padding, selected_items, input_data, full_screen_callback, select_all_callback):
        super().__init__(root)

        self.thumb_size = thumb_size
        self.item_border_size = item_border_size
        self.item_padding = item_padding
        self.last_items_per_row = 0
        self.dragged_over = set()
        self.items = []

        self.item_list = load_interface_data(input_data, 0, 'list-thumbnails')

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.item_grid = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.item_grid, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        for item in self.item_list["file_list"]:
            self.items.append(Item(self.item_grid, item, selected_items, input_data, 0, self.thumb_size, root.cget('bg'), "#5293fa", self.bind_grid_scroll, self.unbind_grid_scroll, full_screen_callback, self.shift_select, select_all_callback, bd=self.item_border_size))

        self.item_grid.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda x: self.canvas.after_idle(self.update_item_layout))
        for i in (self.canvas, self.item_grid):
            i.bind("<Enter>", self.bind_grid_scroll)
            i.bind("<Leave>", self.unbind_grid_scroll)
            i.bind("<Control-a>", select_all_callback)
            i.bind("<Control-A>", select_all_callback)

    def bind_grid_scroll(self, event):
        self.canvas.bind_all("<Button-4>", self.scroll_steps)
        self.canvas.bind_all("<Button-5>", self.scroll_steps)
        event.widget.focus_set()

    def unbind_grid_scroll(self, event):
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def scroll_steps(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")

    def update_item_layout(self, event=None):
        canvas_width = self.canvas.winfo_width()

        items_per_row = max(1, canvas_width // (self.thumb_size[0] + self.item_border_size*2 + self.item_padding*2))

        if self.last_items_per_row != items_per_row:
            for item in self.items:
                item.grid_forget()

            for idx, item in enumerate(self.items):
                row = idx // items_per_row
                col = idx % items_per_row
                item.grid(row=row, column=col, padx=self.item_padding, pady=self.item_padding, sticky="nsew")
            self.last_items_per_row = items_per_row

    def shift_select(self, start, end, action):
        select = 0
        for i in self.items:
            if i == start or i == end:
                if select == 0:
                    select = 1
                else:
                    break
            if select == 1:
                if action:
                    i.select()
                else:
                    i.deselect()


# Note: clear needs to be called to initialise the contents of the window
class ShellScriptWindow(tk.Frame):
    def __init__(self, root, input_data):
        super().__init__(root)
        self.text_widget = tk.Text(self, bg='black', fg='white', height=8)
        self.text_widget.grid(row=0, column=0, sticky='nswe')
        self.script_written_lines = set()
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.text_widget.yview)
        self.text_widget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar.grid(row=0, column=1, sticky='ns')
        self.input_data = input_data
        self.query_project_queued_in_script = None

        self.text_widget.tag_configure("parameters", foreground="#FC8DF5")
        self.text_widget.tag_configure("keywords_builtins", foreground="#B5732D")
        self.text_widget.tag_configure("posix_commands", foreground="#B5732D")
        self.text_widget.tag_configure("strings", foreground="#EB2626")
        self.text_widget.tag_configure("comments", foreground="#26A2EB")
        self.text_widget.tag_configure("quote_chars", foreground="#B5732D")

        self.syntax_highlighting_patterns = {
                "keywords_builtins": r"\b(set|trap)\b",
                "posix_commands": r"\b(ln|mkdir)\b",
                "strings": r"(['\"]).*?\1",
                "comments": r"#.*",
                "parameters": r"-[a-zA-Z0-9_]+"
                }

        self.text_widget.tag_configure("error", background="red")

    def treat_strings_for_posix_shell(self, string):
        return "'"+string.replace('\'','\'"\'"\'')+"'"

    def add_file(self, file, project_name):
        if self.query_project_queued_in_script == None:
            raise TypeError # This should never happen

        destination_project_dir = self.get_destination_dir(project_name,not self.query_project_queued_in_script(project_name))

        line = "ln -s " + self.treat_strings_for_posix_shell(os.path.relpath(os.path.join(self.input_data["sources"][0], file), destination_project_dir)) + " " + self.treat_strings_for_posix_shell(destination_project_dir) + "\n"
        if line not in self.script_written_lines:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, line)
            self.text_widget.config(state=tk.DISABLED)
            self.syntax_highlight_lines((4+len(self.script_written_lines), ))
            self.script_written_lines.add(line)
            self.text_widget.see("end")

    def get_script(self):
        return self.text_widget.get("1.0", tk.END)

    def get_destination_dir(self, project_name, expected_to_exist):
        destination_project_dir = os.path.join(self.input_data["destinations"][0], project_name, self.input_data["destinations_append"], '.')

        if expected_to_exist and not os.path.isdir(destination_project_dir):
            raise FileNotFoundError("Selected project directory with the set destination append path doesn't exist")
            return

        # This is a last line of defense. This shouldn't ever be true
        if destination_project_dir.find('//') != -1 or destination_project_dir.find('/./') != -1 or destination_project_dir.find('/../') != -1:
            raise ValueError("Created a path that's not fully efficient")

        return destination_project_dir


    def clear(self, bash_side_channel_write_fd):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(tk.END, "#!/bin/sh\nset -eu\n\n")
        self.text_widget.config(state=tk.DISABLED)
        self.syntax_highlight_lines((1, 2))
        self.update_bash_side_channel_write_fd(bash_side_channel_write_fd)
        self.script_written_lines.clear()

    def mark_error_line(self,line):
        for tag in self.syntax_highlighting_patterns:
            self.text_widget.tag_remove(tag, f"{line}.0", f"{line}.end")
        self.text_widget.tag_add("error", f"{line}.0", f"{line}.end")
        self.text_widget.see(f"{line}.0")

    def unmark_error_line(self,line):
        self.text_widget.tag_remove("error", f"{line}.0", f"{line}.end")
        self.syntax_highlight_lines((line, ))

    def update_bash_side_channel_write_fd(self, fd):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete('3.0', '4.0')
        self.text_widget.insert('3.0', f"trap 'echo \"$LINENO\" >&{fd}' ERR # For debug\n")
        self.text_widget.config(state=tk.DISABLED)
        self.syntax_highlight_lines((3, ))

    def syntax_highlight_lines(self, lines):
        for line in lines:
            code = self.text_widget.get(f"{line}.0", f"{line}.end")

            for tag in self.syntax_highlighting_patterns:
                self.text_widget.tag_remove(tag, f"{line}.0", f"{line}.end")

            for tag, pattern in self.syntax_highlighting_patterns.items():
                for match in re.finditer(pattern, code):
                    start = f"{line}.0+{match.start()}c"
                    end =   f"{line}.0+{match.end()}c"
                    self.text_widget.tag_add(tag, start, end)
                    if tag == "strings":
                        start =  f"{line}.0+{match.start()}c"
                        start_ = f"{line}.0+{match.start()+1}c"
                        end =    f"{line}.0+{match.end()-1}c"
                        end_ =   f"{line}.0+{match.end()}c"
                        self.text_widget.tag_add("quote_chars", start, start_)
                        self.text_widget.tag_add("quote_chars", end, end_)

    def new_project_callback(self, name):
        line = "mkdir -p " + self.treat_strings_for_posix_shell(self.get_destination_dir(name,False))+"\n"
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, line)
        self.text_widget.config(state=tk.DISABLED)
        self.syntax_highlight_lines((4+len(self.script_written_lines), ))
        self.text_widget.see("end")
        self.script_written_lines.add(line) # This is mainly to get syntax highlighting linue number working in add_file


def spell_check(self):
    nltk.download('wordnet')
    nltk.download('words')
    content=self.text.get("1.0",'end-1c')
    wn_lemmas = set(wordnet.all_lemma_names())
    for tag in self.text.tag_names():
        self.text.tag_delete(tag)
    self.text.tag_configure('spell_error', underline=True, underlinefg='red')
    fails=0
    for word in content.split(' '):
        word_to_check=re.sub(r'[^\w]', '', word.lower()).lower()
        if wordnet.synsets(word_to_check) == [] :
            if word_to_check not in words.words():
                if not any(True for _ in re.finditer('^[0-9]*$', word_to_check)):
                    position = content.find(word)
                    self.text.tag_add('spell_error', f'1.{position}', f'1.{position + len(word)}')
                    fails=fails+1
    return fails


class NewProject(tk.Toplevel):
    def __init__(self, root, ShellScriptWindowCallback, ProjectListCallback ):
        super().__init__(root)
        self.title("Create project")
        self.geometry("400x70")
        self.attributes('-type', 'dialog')

        self.ProjectListCallback = ProjectListCallback
        self.ShellScriptWindowCallback = ShellScriptWindowCallback

        self.entry_frame = tk.Frame(self)
        self.entry_label = tk.Label(self.entry_frame,text="Name:")
        self.entry_label.grid(row=0, column=0, padx=(5,0),pady=10)
        self.text=tk.Text(self.entry_frame)
        self.text.grid(row=0, column=1, sticky='we', padx=(5,9))
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

        self.button_grid=tk.Frame(self)
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
        if spell_check(self) == 0:
            self.spell_check_button.configure(style="Good.TButton")
        else:
            self.spell_check_button.configure(style="Bad.TButton")

    def space_to_underscore_exec(self):
        text=self.text.get("1.0", "1.end")
        self.text.delete('1.0', tk.END)
        self.text.insert(tk.END, text.replace(' ', '_'))
        self.space_to_underscore.configure(style="Good.TButton")

    def write_to_script_exec(self):
        text=self.text.get("1.0", "1.end")
        self.ProjectListCallback(text)
        self.ShellScriptWindowCallback(text)
        self.destroy()

    def select_all(self, event=None):
        self.text.tag_add(tk.SEL, "1.0", tk.END)
        #self.text.icursor('end')


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
        self.NewProject = NewProject(self, self.ShellScriptNewProjectCallback, self.new_project_callback)

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


def normalise_and_check(paths, check, string_to_print):
    output = []
    for i in paths:
        normalised = os.path.normpath(i)
        if check(normalised):
            output.append(normalised)
        else:
            raise FileNotFoundError("Failed to normalise "+string_to_print+" '"+i+"'")
    return output


class MediaSelectorApp:
    def __init__(self, root, unsanitised_input_data, thumb_size=(180, 180), item_border_size=6, item_padding=10):
        for interface in unsanitised_input_data["interfaces"]:
            if not os.path.isfile(interface):
                raise CmdLineError("Following provided interface file doesn\'t exist '"+interface+"'")
            if not os.access(interface, os.X_OK):
                raise CmdLineError("Following provided interface file isn\'t executable '"+interface+"'")
        for source in unsanitised_input_data["sources"]:
            if not os.path.isdir(source):
                raise CmdLineError("Following provided source directory doesn\'t exist: '"+source+"'")
        for destination in unsanitised_input_data["destinations"]:
            if not os.path.isdir(destination):
                raise CmdLineError("Following provided destination directory doesn\'t exist '"+destination+"'")

        if len(unsanitised_input_data["sources"]) != len(unsanitised_input_data["interfaces"]) and len(unsanitised_input_data["interfaces"]) != 1:
            raise CmdLineError("More than one instances of the interface flag must match the number of instances of the source flag to match each interface in the order they appear in the command line to each source in the order they appear in the command line")

        if len(unsanitised_input_data["sources"]) != 1 or len(unsanitised_input_data["destinations"]) != 1:
            raise CmdLineError("Multiple source directories or destination directories aren't implemented yet")

        self.input_data = {
            "interfaces": normalise_and_check(unsanitised_input_data["interfaces"], os.path.isfile,"interface"),
            "sources": normalise_and_check(unsanitised_input_data["sources"], os.path.isdir,"source"),
            "destinations": normalise_and_check(unsanitised_input_data["destinations"], os.path.isdir,"destination"),
            "destinations_append": unsanitised_input_data["destinations_append"],
        }

        self.selected_items = CountCallbackSet()  # set of selected file paths

        root.title("MEDIA organiser")

        self.upper_and_shell_pane = ttk.PanedWindow(root, orient=tk.VERTICAL)

        self.list_grid_pane = ttk.PanedWindow(self.upper_and_shell_pane, orient=tk.HORIZONTAL)

        self.grid_and_toolbar = tk.Frame(self.list_grid_pane)

        self.ItemGrid = ItemGrid(self.grid_and_toolbar, thumb_size, item_border_size, item_padding, self.selected_items, self.input_data, self.enter_full_screen, self.select_all_callback)

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
        self.clear_script_button.pack(side=tk.LEFT, padx=(2,4), pady=2)

        ttk.Separator(self.toolbar, orient='vertical').pack(side=tk.LEFT, padx=(5, 5), fill=tk.Y)

        self.select_all_button = tk.Button(self.toolbar, text="Select All", command=self.select_all)
        self.select_all_button.pack(side=tk.LEFT, padx=2)

        self.select_none_button = tk.Button(self.toolbar, text="Select None", command=self.select_none)
        self.select_none_button.pack(side=tk.LEFT, padx=2)

        self.select_invert_button = tk.Button(self.toolbar, text="Invert selections", command=self.select_invert)
        self.select_invert_button.pack(side=tk.LEFT, padx=2)

        self.item_count = tk.Label(self.toolbar, text="")
        self.item_count.pack(side=tk.RIGHT, padx=2)

        ttk.Separator(self.toolbar, orient='vertical').pack(side=tk.RIGHT, padx=(5, 5), fill=tk.Y)

        self.ItemGrid.grid(row=0, column=0, sticky='nswe')
        self.toolbar.grid(row=1, column=0, sticky='we')
        self.grid_and_toolbar.grid_rowconfigure(0, weight=1)
        self.grid_and_toolbar.grid_columnconfigure(0, weight=1)

        self.bash_side_channel_read_fd = None
        self.bash_side_channel_write_fd = None
        self.ShellScriptWindow = ShellScriptWindow(self.upper_and_shell_pane, self.input_data)
        self.ShellScriptWindow.grid(row=0, column=0, sticky='nswe')
        self.ShellScriptWindow.grid_rowconfigure(0, weight=1)
        self.ShellScriptWindow.grid_columnconfigure(0, weight=1)

        self.ProjectList = ProjectList(self.list_grid_pane, self.input_data["destinations"], self.ShellScriptWindow.new_project_callback)

        self.ShellScriptWindow.query_project_queued_in_script = self.ProjectList.query_project_queued_in_script
        self.clear_shell_script()

        self.list_grid_pane.add(self.grid_and_toolbar, weight=1)
        self.list_grid_pane.add(self.ProjectList, weight=1)

        self.upper_and_shell_pane.add(self.list_grid_pane, weight=1)
        self.upper_and_shell_pane.add(self.ShellScriptWindow, weight=0)

        self.upper_and_shell_pane.grid (row=0, column=0, sticky='nswe')
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.selected_items.register_callback(self.update_counter)
        self.selected_items.call_callbacks() # Write initial text on the counter label

        self.shell_script_error_line = None

    def enter_full_screen(self, path):
        self.ItemGrid.grid_forget()
        self.FullScreenItem = FullScreenItem(self.grid_and_toolbar, self.input_data, path, self.exit_full_screen)
        self.FullScreenItem.grid(row=0, column=0, sticky='nswe')

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

        bash_process = subprocess.Popen(["bash", "-c", shell_script_string],pass_fds=(self.bash_side_channel_write_fd, ))

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
            self.ShellScriptWindow.clear(self.bash_side_channel_write_fd)
            self.ProjectList.clear_projects_queued_in_script()
            self.ProjectList.full_update_list()

    def update_counter(self, count):
        self.item_count.config(text="Item count: "+str(count))

    def select_all_callback(self, event=None):
        self.select_all()

    def select_all(self):
        for i in self.ItemGrid.items:
            i.select()

    def select_none(self):
        for i in self.ItemGrid.items:
            if i.get_filename_path() in self.selected_items:
                i.deselect()

    def select_invert(self):
        for i in self.ItemGrid.items:
            if i.get_filename_path() in self.selected_items:
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
        selected_dir = self.ProjectList.get_selected_dir()
        if not selected_dir:
            messagebox.showinfo("Selection", "No project selection")
            return

        if not self.selected_items:
            messagebox.showinfo("Selection", "No items selected.")
            return

        try:
            for file_id in self.selected_items:
                for file_to_link in load_interface_data(self.input_data, 0, 'get-related', arg=file_id)["file_list"]:
                    self.ShellScriptWindow.add_file(file_to_link["filename"], selected_dir)
        except FileNotFoundError as error_message:
            messagebox.showinfo("ERROR", error_message)
        except ValueError as error_message:
            messagebox.showinfo("ERROR", error_message)

        self.select_none()


def load_interface_data(input_data , source_number, query, arg=None):
    pass_id = os.path.basename(os.path.normpath(input_data["sources"][source_number]))
    if arg != None:
        arg = os.path.relpath(arg, input_data["sources"][source_number])

    match query:
        case 'list-thumbnails':
            data = json.loads(subprocess.check_output([input_data["interfaces"][source_number], '-l', pass_id]))
        case 'get-related':
            if arg == None:
                print("Internal error: called load_interface_data without passing arg")
                return None
            data = json.loads(subprocess.check_output([input_data["interfaces"][source_number], '-g', pass_id, arg]))
        case 'get-info':
            if arg == None:
                print("Internal error: called load_interface_data without passing arg")
                return None
            data = json.loads(subprocess.check_output([input_data["interfaces"][source_number], '-i', pass_id, arg]))
        case _:
            raise KeyError

    if data["api_version"].split('.')[0] != "v1": #or (int)(card_item_list["api_version"].split('.')[1]) < 1:
        print("ERROR invalid api version on source media interface")
        return None

    return data


def main():
    version = "v0.0-dev"

    root = tk.Tk()
    root.geometry("1000x600")

    parser = argparse.ArgumentParser(description='Select and symlink media from one directory to another')
    parser.add_argument('-i', '--interface',          type=str, action='append',  required=True, help='Path to source direcotry interface executable')
    parser.add_argument('-s', '--source',             type=str, action='append',  required=True, help='Path to the source directory of media to get linked. This can be entered multiple times')
    parser.add_argument('-d', '--destination',        type=str, action='append',  required=True, help='Path to the distention directory for the links to stored in. This can be entered multiple times')
    parser.add_argument('-a', '--destination-append', type=str,                                  help='Path to be appended to the project directory selected in the destination directory. For example if media needs to be linked in a sub-folder')
    parser.add_argument('-v', '--version',                      action="version",                help='print the version of this program and exit successfully',  version=version)

    args = parser.parse_args()

    input_data = {
        "interfaces": args.interface,
        "sources": args.source,
        "destinations": args.destination,
        "destinations_append": (args.destination_append if args.destination_append is not None else ""),
    }

    try:
        app = MediaSelectorApp(root, input_data)
    except CmdLineError as error_message:
        print(f"ERROR: {error_message}", file=sys.stderr)
        sys.exit(1)

    root.mainloop()


if __name__ == "__main__":
    main()
