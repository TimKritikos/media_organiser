import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import subprocess
import argparse

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
    def __init__(self, root, item_data,media_dir,card_dir, selected_items, thumb_size,bg_color,select_color, **kwargs):
        super().__init__(root,**kwargs)

        self.filename_path=media_dir+"/"+card_dir+"/"+item_data["filename"]
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
    def __init__(self, root, organised_dir, thumb_size, item_border_size, item_padding, selected_items, card_data, media_dir, card_dir):
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

        # create the items
        for file_obj in card_data:
            self.items.append(Item(self.item_grid, file_obj,media_dir,card_dir, selected_items, self.thumb_size ,root.cget('bg'),"#5293fa", bd=self.item_border_size))


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


class MediaSelectorApp:
    def __init__(self, root, card_data, card_dir, media_dir, organised_dir, thumb_size, item_border_size, item_padding):
        root.title("MEDIA organiser")
        self.selected_items = CountCallbackSet()  # set of selected file paths
        self.organised_dir=organised_dir

        # Left panel: grid of items
        self.grid_frame = ItemGrid(root,organised_dir,thumb_size,item_border_size,item_padding,self.selected_items,card_data,media_dir,card_dir)

        # Toolbar
        self.toolbar=tk.Frame(root, bd=3)
        self.toolbar.config(relief="groove")
        self.save_button = tk.Button(self.toolbar, text="Save Selections", command=self.save_selections)
        self.select_all = tk.Button(self.toolbar, text="Select All", command=self.select_all)
        self.select_none = tk.Button(self.toolbar, text="Select None", command=self.select_none)
        self.select_invert = tk.Button(self.toolbar, text="Invert selections", command=self.select_invert)
        self.item_count = tk.Label(self.toolbar, text="")
        self.save_button.pack(side=tk.LEFT,padx=(4,2),pady=2)
        self.select_all.pack(side=tk.LEFT,padx=2)
        self.select_none.pack(side=tk.LEFT,padx=2)
        self.select_invert.pack(side=tk.LEFT,padx=2)
        self.item_count.pack(side=tk.RIGHT,padx=2)


        # Right panel: project listing
        self.dir_frame = tk.Frame(root, width=400, bd=2, relief="sunken")
        self.dir_listbox = tk.Listbox(self.dir_frame)
        self.dir_listbox.pack(fill="both", expand=True)

        self.grid_frame.grid (row=0,column=0,sticky='nswe')
        self.dir_frame.grid  (row=0,column=1,rowspan=2,sticky='sn')
        self.toolbar.grid(row=1,column=0,sticky='we')
        root.grid_rowconfigure(0, weight=1)
        root.grid_columnconfigure(0, weight=1)

        self.selected_items.register_callback(self.update_counter)
        self.selected_items.update() # Write initial text on the counter label

        # Load directories into listbox
        self.load_directories()

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

    def load_directories(self):
        if not os.path.isdir(self.organised_dir):
            print("ERROR: organised dir is invalid")
            return
        dirs = [d for d in os.listdir(self.organised_dir) if os.path.isdir(os.path.join(self.organised_dir, d))]
        dirs.sort()
        for d in dirs:
            self.dir_listbox.insert(tk.END, d)


    def save_selections(self):
        """Save selected files and chosen directory to JSON."""
        if not self.selected_items:
            messagebox.showinfo("No Selection", "No items selected.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if not save_path:
            return

        # Get selected directory
        selection = self.dir_listbox.curselection()
        selected_dir = self.dir_listbox.get(selection[0]) if selection else None

        data = {
                "selected_directory": selected_dir,
                "selected_files": [f for f in self.selected_items ]
        }

        with open(save_path, "w") as f:
            json.dump(data, f, indent=4)

        messagebox.showinfo("Saved", f"Selections saved to:\n{save_path}")


def main():
    version="v0.0-dev"

    root = tk.Tk()
    root.geometry("1000x600")

    parser = argparse.ArgumentParser(description='Organise a card of a source_media dir')
    parser.add_argument('organised_dir', type=str, help='The organised dir the contains project directories. Relative to the current working directory or an absolute path')
    parser.add_argument('card_dir', type=str, help='The directory of the card to be organised relative to the current working directory or an absolute path')
    parser.add_argument('-v','--version', help='print the version of this program and exit successfully', action="version", version=version)

    args = parser.parse_args()

    if not os.path.isdir(args.card_dir):
        print("ERROR: Provided card_dir doesn\'t exist")
        return 1
    media_dir=os.path.abspath(args.card_dir).split("/MEDIA/")[0]+"/MEDIA"
    if not os.path.isdir(media_dir):
        print("ERROR: Calculated media_dir or card_dir doesn\'t exist")
        return 1
    try:
        structure_version_file = open(media_dir+"/structure_version")
    except Exception:
        print("ERROR: Could find structure_version in media dir of provided card_dir")
        return 1
    if structure_version_file.read().split('.')[0] != "v2":
        print("ERROR: Major media version is incompatible")
        return 1
    structure_version_file.close()
    card_dir_absolute=os.path.abspath(args.card_dir)
    if card_dir_absolute.find("/MEDIA/") == -1:
        print("ERROR: card_dir doesn't not seem to be in MEDIA or is the root of MEDIA")
        return 1
    card_dir=card_dir_absolute.split("/MEDIA/")[1]
    if not os.path.isdir(media_dir+"/"+card_dir):
        print("ERROR: Calculated card_dir is invalid")
        return 1
    if card_dir.find("/DATA/") == -1:
        print("ERROR: card_dir is invalid")
        return 1
    source_media_dir=card_dir.split("/DATA/")[0]
    if not os.path.isdir(media_dir+"/"+source_media_dir):
        print("ERROR: Calculated source_media_dir from card_dir is invalid")
        return 1
    card_id=card_dir.split("/DATA/")[1]
    if not os.path.isdir(media_dir+"/"+source_media_dir+"/DATA/"+card_id) or not card_id:
        print("ERROR: Calculated card id is invalid")
        return 1
    interface_executable_path=media_dir+"/"+source_media_dir+"/interface"
    if not os.path.isfile(interface_executable_path):
        print("ERROR: source media directory doesn't have an interface executable")
        return 1
    if not os.access(interface_executable_path, os.X_OK):
        print("ERROR: source media directory has a file named interface but it's not executable")
        return 1

    if not os.path.isdir(args.organised_dir):
        print("ERROR: Provided organised_dir doesn\'t exist")
        return 1
    organised_absolute_dir=os.path.abspath(args.organised_dir)
    if organised_absolute_dir.find("/MEDIA/") == -1:
        print("ERROR: organised_dir doesn't not seem to be in MEDIA or is the root of MEDIA")
        return 1
    if not os.path.isdir(organised_absolute_dir):
        print("ERROR: Calculated organised dir doesn\'t exist")
        return 1
    organised_media_dir=organised_absolute_dir.split("/MEDIA/")[0]+"/MEDIA"
    if not os.path.isdir(organised_media_dir) or not organised_media_dir:
        print("ERROR: Calculated media_dir of organised dir doesn\'t exist")
        return 1
    if media_dir != organised_media_dir:
        print("ERROR: Calculated media_dir of card_id doesn't match the calculated media_dir of the organised_dir")
        return 1
    organised_dir_sanitised=organised_absolute_dir.split("/MEDIA/")[1]
    if not os.path.isdir(media_dir+"/"+organised_dir_sanitised):
        print("ERROR: Calculated card_dir is invalid")
        return 1

    card_item_list = json.loads(subprocess.check_output([interface_executable_path, "-l", card_id]))
    if card_item_list["api_version"].split('.')[0] != "v1": #or (int)(card_item_list["api_version"].split('.')[1]) < 1:
        print("ERROR invalid api version on source media interface")
        return 1


    app = MediaSelectorApp(root,card_item_list["file_list"],card_dir,media_dir, media_dir+"/"+organised_dir_sanitised,(180,180),6,10)
    root.mainloop()


if __name__ == "__main__":
    main()
