import tkinter as tk
import threading
import os
from PIL import Image, ImageTk
import mpv
import time
from datetime import datetime

import constants

class ItemGrid(tk.Frame):
    def __init__(self, root, thumb_size, item_border_size, item_padding, selected_items, input_data, full_screen_callback, select_all_callback, update_progress_bar_callback, load_interface_data):
        super().__init__(root)

        self.thumb_size = thumb_size
        self.item_border_size = item_border_size
        self.item_padding = item_padding
        self.last_items_per_row = 0
        self.last_item_count = 0
        self.dragged_over = set()
        self.items = []
        self.selected_items = selected_items
        self.input_data = input_data
        self.full_screen_callback = full_screen_callback
        self.select_all_callback = select_all_callback
        self.update_progress_bar_callback = update_progress_bar_callback

        self.item_list = load_interface_data(self.input_data, 0, 'list-thumbnails')

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.item_grid = tk.Frame(self.canvas)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.item_grid, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        threading.Thread(target=self.load_items_thread, daemon=True).start()

        self.item_grid.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda x: self.canvas.after_idle(self.update_item_layout))
        for i in (self.canvas, self.item_grid):
            i.bind("<Enter>", self.bind_grid_scroll)
            i.bind("<Leave>", self.unbind_grid_scroll)
            i.bind("<Control-a>", self.select_all_callback)
            i.bind("<Control-A>", self.select_all_callback)

    def add_item(self,item):
            self.items.append(Item(self.item_grid, item, self.selected_items, self.input_data, 0, self.thumb_size, self.cget('bg'), "#5293fa", self.bind_grid_scroll, self.unbind_grid_scroll, self.full_screen_callback, self.shift_select, self.select_all_callback, bd=self.item_border_size))
            self.update_item_layout()
            self.items[-1].update_idletasks()
            self.update_progress_bar_callback(len(self.items))

    def load_items_thread(self):
        for item in self.item_list["file_list"]:
            self.after(0, self.add_item,item)

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

    def update_scrollregion(self, event=None):
        self.item_grid.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

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
            if self.last_items_per_row<items_per_row:
                self.update_scrollregion()
            self.last_items_per_row = items_per_row
            self.last_item_count = len(self.items)
        elif self.last_item_count != len(self.items):
            idx = len(self.items)-1
            item = self.items[-1]
            row = idx // items_per_row
            col = idx % items_per_row
            item.grid(row=row, column=col, padx=self.item_padding, pady=self.item_padding, sticky="nsew")
            self.last_item_count = idx
            self.canvas.yview_moveto(1)

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


class Item(tk.Frame):
    last_selected = None
    mouse_action = 1

    def __init__(self, root, item_data, selected_items, input_data, input_data_source_index, thumb_size, bg_color, select_color, enter_callback, leave_callback, full_screen_callback, shift_select_callback, select_all_callback, **kwargs):
        super().__init__(root, **kwargs)

        self.selected_items = selected_items
        self.dragged_over = set()
        self.bg_color = bg_color
        self.select_color = select_color
        self.file_path = os.path.join(input_data["sources"][input_data_source_index], item_data["file_path"])
        self.full_screen_callback = full_screen_callback
        self.shift_select_callback = shift_select_callback
        self.select_all_callback = select_all_callback

        if not self.file_path or not os.path.exists(self.file_path):
            print("ERROR: file in json from source media interface executable couldn't be found")
            return -1

        #Create thumbnail image
        if item_data["file_type"] in ["image-preview", "image"]:
            try:
                img = Image.open(self.file_path).convert("RGB")
                img.thumbnail(thumb_size)
                self.photo_obj = ImageTk.PhotoImage(img)
            except Exception:
                img = Image.new("RGB", thumb_size, (100, 100, 100))
                self.photo_obj = ImageTk.PhotoImage(img)
        elif item_data["file_type"] == "video":
                player = mpv.MPV(vo='null',ao='null')
                player.pause=True
                player.play(self.file_path)
                start_time=datetime.now()
                while True:
                    if (datetime.now()-start_time).total_seconds() > 15 :
                        #Timeout
                        img = Image.new("RGB", thumb_size, (100, 100, 100))
                        print("Timed out loading video '"+self.file_path+"'")
                        break;
                    try:
                        img=player.screenshot_raw()
                        break;
                    except Exception:
                        time.sleep(.2)
                player.command('quit')
                del player
                img.thumbnail(thumb_size)
                self.photo_obj = ImageTk.PhotoImage(img)
        else:
            img = Image.new("RGB", thumb_size, (60, 60, 60))
            self.photo_obj = ImageTk.PhotoImage(img)

        self.image = tk.Label(self, image=self.photo_obj, borderwidth=0)
        self.image.pack()
        self.caption = tk.Label(self, text=os.path.basename(self.file_path), wraplength=thumb_size[0], borderwidth=0)
        self.caption.pack()

        for i in (self.image, self.caption, self):
            i.bind("<Button-1>", self.on_click)
            i.bind("<B1-Motion>", self.on_drag)
            i.bind("<Enter>", enter_callback)
            i.bind("<Leave>", leave_callback)
            i.bind("<Key>", self.key_callback)

    def key_callback(self, event):
        if event.char == '\r' :
            self.full_screen_callback(self.file_path)
        if event.state & constants.TK_CONTROL_MASK and event.keysym == 'a':
            self.select_all_callback()

    def deselect(self):
        for i in (self.image, self.caption, self):
            i.config(bg=self.bg_color)
        if self.file_path in self.selected_items:
            self.selected_items.remove(self.file_path)

    def select(self):
        for i in (self.image, self.caption, self):
            i.config(bg=self.select_color)
        self.selected_items.add(self.file_path)

    def on_click(self, event):
        self.dragged_over.clear()
        if self.file_path in self.selected_items:
            self.deselect()
            Item.mouse_action = 0
        else:
            self.select()
            Item.mouse_action = 1
        self.dragged_over.add(self)
        if event.state & constants.TK_SHIFT_MASK and Item.last_selected != None:
            self.shift_select_callback(Item.last_selected, self, Item.mouse_action)
        Item.last_selected = self

    def get_file_path(self):
        return self.file_path

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
