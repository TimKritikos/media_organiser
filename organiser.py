import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import subprocess
import argparse
from tkinter import ttk

class CmdLineError(Exception):
    pass

class CountCallbackSet:
    def __init__(self):
        self.set=set()
        self.callback=None
    def add(self,item):
        self.set.add(item)
        self.update()
    def remove(self,item):
        self.set.remove(item)
        self.update()
    def __len__(self):
        return len(self.set)
    def __iter__(self):
        return iter(self.set)

    def update(self):
        if self.callback != None:
            self.callback(len(self.set))
    def register_callback(self,callback):
        self.callback=callback

class Item(tk.Frame):
    def __init__(self, root, item_data,  selected_items, input_data, input_data_source_index, thumb_size, bg_color, select_color, **kwargs):
        super().__init__(root,**kwargs)

        self.filename_path=input_data["sources"][input_data_source_index]+"/"+item_data["filename"]

        if not self.filename_path or not os.path.exists(self.filename_path):
            print("ERROR: file in json from source media interface executable couldn't be found")
            return -1

        if item_data["file_type"] in ["image-preview","image"]:
            #File type is image
            try:
                img = Image.open(self.filename_path).convert("RGB")
                img.thumbnail(thumb_size)
                self.photo_obj = ImageTk.PhotoImage(img)
            except Exception:
                #couldn't open or read the image file
                img = Image.new("RGB", thumb_size, (100, 100, 100))
                self.photo_obj = ImageTk.PhotoImage(img)
        else:
            # Video placeholder
            img = Image.new("RGB", thumb_size, (60, 60, 60))
            self.photo_obj = ImageTk.PhotoImage(img)


        self.image = tk.Label(self, image=self.photo_obj, borderwidth=0)
        self.image.pack()
        self.caption = tk.Label(self, text=os.path.basename(self.filename_path), wraplength=thumb_size[0], borderwidth=0)
        self.caption.pack()

        for i in (self.image, self.caption, self):
            i.bind("<Button-1>", self.on_click)
            i.bind("<B1-Motion>",self.on_drag)

        self.selected_items=selected_items
        self.dragged_over=set()

        self.bg_color=bg_color
        self.select_color=select_color

    def deselect(self):
        self.image.config(bg=self.bg_color)
        self.caption.config(bg=self.bg_color)
        self.config(bg=self.bg_color)
        self.selected_items.remove(self.filename_path)

    def select(self):
        self.image.config(bg=self.select_color)
        self.caption.config(bg=self.select_color)
        self.config(bg=self.select_color)
        self.selected_items.add(self.filename_path)

    def on_click(self,event):
        self.dragged_over.clear()
        if self not in self.dragged_over:
            if self.filename_path in self.selected_items:
                self.deselect()
                self.mouse_action=0
            else:
                self.select()
                self.mouse_action=1
            self.dragged_over.add(self)
    def get_filename_path(self):
        return self.filename_path
    def on_drag(self, event):
        widget=event.widget.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return
        while widget and not isinstance(widget, Item):
            widget = widget.master
        if isinstance(widget, Item) and widget not in self.dragged_over:
            if self.mouse_action == 1:
                widget.select()
            elif widget.get_filename_path() in self.selected_items:
                widget.deselect()
            self.dragged_over.add(widget)

class ItemGrid(tk.Frame):
    def __init__(self, root, thumb_size, item_border_size, item_padding, selected_items, input_data):
        super().__init__(root)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.item_grid = tk.Frame(self.canvas)
        self.item_grid.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window=self.canvas.create_window((0, 0), window=self.item_grid, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.thumb_size=thumb_size
        self.item_border_size=item_border_size
        self.item_padding=item_padding
        self.items_per_row=0

        self.dragged_over = set()
        self.items=[]

        self.item_list=load_interface_data(input_data,0,'list-thumbnails')

        # create the items
        for item in self.item_list["file_list"]:
            self.items.append(Item(self.item_grid, item, selected_items, input_data, 0, self.thumb_size ,root.cget('bg'), "#5293fa", bd=self.item_border_size))


        self.canvas.bind("<Configure>", lambda x: self.canvas.after_idle(self.update_item_layout))
        self.canvas.bind("<Enter>", self.bind_grid_scroll)
        self.canvas.bind("<Leave>", self.unbind_grid_scroll)

    def bind_grid_scroll(self, event):
        self.canvas.bind_all("<Button-4>", self.scroll_steps)
        self.canvas.bind_all("<Button-5>", self.scroll_steps)
    def unbind_grid_scroll(self, event):
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
    def scroll_steps(self,event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
    def update_item_layout(self, event=None):

        self.canvas.update_idletasks()
        canvas_width = self.canvas.winfo_width()

        if canvas_width <= 1:  # not yet drawn
            return

        per_row = max(1, canvas_width // (self.thumb_size[0] + self.item_border_size*2 + self.item_padding*2))
        if self.items_per_row != per_row:
            self.canvas.itemconfig(self.canvas_window, width=canvas_width)
            for item in self.items:
                item.grid_forget()

            for idx, item in enumerate(self.items):
                row = idx // per_row
                col = idx % per_row
                item.grid(row=row, column=col, padx=self.item_padding, pady=self.item_padding, sticky="nsew")
            self.items_per_row=per_row

class ShellScriptWindow(tk.Frame):
    def __init__(self, root):
        super().__init__(root)
        self.text_widget=tk.Text(self, bg='black', fg='white')
        self.text_widget.grid(row=0,column=0,sticky='nswe')
        self.script_lines=set()
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.text_widget.yview)
        self.text_widget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar.grid(row=0,column=1,sticky='ns')
        self.clear()
    def add_file(self, file, project_dir,input_data):
        source_dir=input_data["sources"][0]
        destination_dir=input_data["destinations"][0]
        if destination_dir[-1]!='/':
            destination_dir=destination_dir+'/'
        destination_append=input_data["destinations_append"]
        if destination_append[-1]!='/':
            destination_append=destination_append+'/'
        if destination_append[0]!='/':
            destination_append='/'+destination_append
        destination_dir=destination_dir+project_dir+destination_append
        if not os.path.isdir(destination_dir):
            raise FileNotFound
        line="ln -s '"+os.path.relpath(source_dir+file,destination_dir)+"' '"+destination_dir+"'\n"
        if line not in self.script_lines:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, line)
            self.text_widget.config(state=tk.DISABLED)
            self.script_lines.add(line)
            self.text_widget.see("end")
    def get_script(self):
        return self.text_widget.get("1.0",tk.END)
    def clear(self):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete(1.0,tk.END)
        self.text_widget.insert(tk.END, "#!/bin/sh\nset -eu\n")
        self.text_widget.config(state=tk.DISABLED)
        self.script_lines.clear()

class  ProjectList(tk.Frame):
    def __init__(self, root, destinations):
        super().__init__(root, bd=2, relief="sunken")

        self.dir_listbox = tk.Listbox(self, width=60)
        self.dir_listbox.pack(fill="both", expand=True)

        self.dir_listbox.delete(0, tk.END)
        dirs = [d for d in os.listdir(destinations[0]) if os.path.isdir(os.path.join(destinations[0], d))]
        dirs.sort()
        for d in dirs:
            self.dir_listbox.insert(tk.END, d)
    def get_selected_dir(self):
        selection = self.dir_listbox.curselection()
        if not selection:
            return None
        else:
            return self.dir_listbox.get(selection[0])

class MediaSelectorApp:
    def __init__(self,root, input_data, thumb_size=(180,180), item_border_size=6, item_padding=10):

        for interface in input_data["interfaces"]:
            if not os.path.isfile(interface):
                raise CmdLineError("Following provided interface file doesn\'t exist '"+interface+"'")
            if not os.access(interface, os.X_OK):
                raise CmdLineError("Following provided interface file isn\'t executable '"+interface+"'")
        for source in input_data["sources"]:
            if not os.path.isdir(source):
                raise CmdLineError("Following provided source directory doesn\'t exist: '"+source+"'")
        for destination in input_data["destinations"]:
            if not os.path.isdir(destination):
                raise CmdLineError("Following provided destination directory doesn\'t exist '"+destination+"'")

        if len(input_data["sources"]) != len(input_data["interfaces"]) and len(input_data["interfaces"])!=1:
            raise CmdLineError("Non-one instances of the interface flag must match the number of instances of the source flag to match each interface in the order they appear in the command line to each source in the order they appear in the command line")

        if len(input_data["sources"])!=1 or len(input_data["destinations"])!=1:
            raise CmdLineError("Multiple source dirs or destination dirs aren't implemented yet")

        self.input_data=input_data

        root.title("MEDIA organiser")

        self.selected_items = CountCallbackSet()  # set of selected file paths

        self.upper_and_shell_pane = ttk.PanedWindow(root, orient=tk.VERTICAL)
        self.list_grid_pane = ttk.PanedWindow(self.upper_and_shell_pane, orient=tk.HORIZONTAL)

        grid_and_toolbar=tk.Frame(self.list_grid_pane)
        # Left panel: grid of items
        self.grid_frame = ItemGrid(grid_and_toolbar, thumb_size, item_border_size, item_padding, self.selected_items, input_data)

        # Toolbar
        self.toolbar=tk.Frame(grid_and_toolbar, bd=3)
        self.toolbar.config(relief="groove")
        self.danger_style = ttk.Style()
        self.danger_style.configure("Danger.TButton", background="#d18282")
        self.danger_style.map("Danger.TButton",background=[('hover', '#cf3838')])
        self.danger_style.configure("Normal.TButton", background="#82b5d1")
        self.danger_style.map("Normal.TButton",background=[('hover', '#3899cf')])
        self.danger_style.configure("Clear.TButton", background="#424242", foreground='#DDDDDD')
        self.danger_style.map("Clear.TButton",background=[('hover', '#000000')])

        self.execute_button = ttk.Button(self.toolbar, text="Execute", command=self.execute_shell, style="Danger.TButton")
        self.execute_button.pack(side=tk.LEFT,padx=(4,2),pady=2)

        self.add_to_script_button = ttk.Button(self.toolbar, text="Add to script", command=self.add_to_script, style="Normal.TButton")
        self.add_to_script_button.pack(side=tk.LEFT,padx=(2,2),pady=2)

        self.clear_script_button = ttk.Button(self.toolbar, text="Clear script", command=self.clear_shell_script, style="Clear.TButton")
        self.clear_script_button.pack(side=tk.LEFT,padx=2)

        ttk.Separator(self.toolbar, orient='vertical').pack(side=tk.LEFT,padx=(5,5),fill=tk.Y)

        self.select_all = tk.Button(self.toolbar, text="Select All", command=self.select_all)
        self.select_all.pack(side=tk.LEFT,padx=2)

        self.select_none = tk.Button(self.toolbar, text="Select None", command=self.select_none)
        self.select_none.pack(side=tk.LEFT,padx=2)

        self.select_invert = tk.Button(self.toolbar, text="Invert selections", command=self.select_invert)
        self.select_invert.pack(side=tk.LEFT,padx=2)

        self.item_count = tk.Label(self.toolbar, text="")
        self.item_count.pack(side=tk.RIGHT,padx=2)

        ttk.Separator(self.toolbar, orient='vertical').pack(side=tk.RIGHT,padx=(5,5),fill=tk.Y)

        self.grid_frame.grid(row=0,column=0,sticky='nswe')
        self.toolbar.grid(row=1,column=0,sticky='we')
        grid_and_toolbar.grid_rowconfigure(0, weight=1)
        grid_and_toolbar.grid_columnconfigure(0, weight=1)

        # Right panel: project listing
        self.ProjectList=ProjectList(self.list_grid_pane, self.input_data["destinations"])

        self.list_grid_pane.add(grid_and_toolbar, weight=1)
        self.list_grid_pane.add(self.ProjectList, weight=1)


        self.shell_script_window=ShellScriptWindow(self.upper_and_shell_pane)
        self.shell_script_window.grid(row=0,column=0,sticky='nswe')
        self.shell_script_window.grid_rowconfigure(0, weight=1)
        self.shell_script_window.grid_columnconfigure(0, weight=1)

        self.upper_and_shell_pane.add(self.list_grid_pane, weight=1)
        self.upper_and_shell_pane.add(self.shell_script_window, weight=1)

        self.upper_and_shell_pane.grid (row=0,column=0,sticky='nswe')
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.selected_items.register_callback(self.update_counter)
        self.selected_items.update() # Write initial text on the counter label

    def clear_shell_script(self):
        self.shell_script_window.clear()
    def execute_shell(self):
        shell_script_string = self.shell_script_window.get_script()
        data=subprocess.run(["bash","-c", shell_script_string])
        self.shell_script_window.clear()
    def update_counter(self,count):
        self.item_count.config(text="Item count: "+str(count))

    def select_all(self):
        for i in self.grid_frame.items:
            i.select()
    def select_none(self):
        for i in self.grid_frame.items:
            if i.get_filename_path() in self.selected_items:
                i.deselect()
    def select_invert(self):
        for i in self.grid_frame.items:
            if i.get_filename_path() in self.selected_items:
                i.deselect()
            else:
                i.select()

    def add_to_script(self):
        selected_dir = self.ProjectList.get_selected_dir()
        if not selected_dir:
            messagebox.showinfo("No project selection", "No project selection")
            return

        if not self.selected_items:
            messagebox.showinfo("No items selected.", "No items selected.")
            return

        files_to_link=[]
        for file_id in self.selected_items:
            for file_to_link in load_interface_data(self.input_data, 0, 'get-related',arg=file_id)["file_list"]:
                self.shell_script_window.add_file(file_to_link["filename"],selected_dir,self.input_data)


def load_interface_data(input_data , source_number, query, arg=None):
    #Convert the relative or absolute paths to the paths relative to the source dir that the interface expects
    pass_id=input_data["sources"][source_number]
    if pass_id[-1]=='/':
        pass_id=pass_id.rstrip("/")
    pass_id=pass_id.split('/')[-1]
    if arg!=None:
        arg=arg.removeprefix(input_data["sources"][0])
        if arg[0]=='/':
            arg=arg.removeprefix('/')

    match query:
        case 'list-thumbnails':
            data=json.loads(subprocess.check_output([input_data["interfaces"][source_number], '-l', pass_id]))
        case 'get-related':
            if arg == None:
                print("Internal error: called load_interface_data without passing arg")
                return None
            data=json.loads(subprocess.check_output([input_data["interfaces"][source_number], '-g', pass_id, arg]))
        case 'get-info':
            if arg == None:
                print("Internal error: called load_interface_data without passing arg")
                return None
            data=json.loads(subprocess.check_output([input_data["interfaces"][source_number], '-i', pass_id, arg]))
        case _:
            raise KeyError
    if data["api_version"].split('.')[0] != "v1": #or (int)(card_item_list["api_version"].split('.')[1]) < 1:
        print("ERROR invalid api version on source media interface")
        return None
    return data

def main():
    version="v0.0-dev"

    root = tk.Tk()
    root.geometry("1000x600")

    parser = argparse.ArgumentParser(description='Organise a card of a source_media dir')
    parser.add_argument('-i','--interface',          type=str, action='append', required=True, help='Path to source dir interface executable')
    parser.add_argument('-s','--source',             type=str, action='append', required=True, help='Path to the source dir of media to be linked. This can be enetered multiple times')
    parser.add_argument('-d','--destination',        type=str, action='append', required=True, help='Path to the deistantion dir for links to be. This can be entered multiple times')
    parser.add_argument('-a','--destination-append', type=str,                                 help='Path to be appended to the dir selected in the destination dir. For example if media needs to be linked in a subfolder')
    parser.add_argument('-v','--version',                      action="version",               help='print the version of this program and exit successfully',  version=version)

    args = parser.parse_args()

    input_data={
        "interfaces": args.interface,
        "sources": args.source,
        "destinations": args.destination,
        "destinations_append": args.destination_append,
    }

    try:
        app = MediaSelectorApp(root,input_data)
    except CmdLineError as error_message:
        print(f"ERROR: {error_message}", file=sys.stderr)
        sys.exit(1)

    root.mainloop()


if __name__ == "__main__":
    main()
