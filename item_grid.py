import tkinter as tk
import threading
import os
from PIL import Image, ImageTk
import mpv
import time
from datetime import datetime
from exiftool import ExifToolHelper
from datetime import timezone
import concurrent.futures
import queue
import random

import constants

class ItemGrid(tk.Frame):
    def __init__(self, root, thumb_size, item_border_size, item_padding, selected_items, input_data, full_screen_callback, select_all_callback, update_progress_bar_callback, load_interface_data, tk_root, profile_save_filename, thread_count):
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
        self.profile_save_filename = profile_save_filename
        self.tk_root = tk_root

        self.rows_per_page = 100 # TODO caluclaute based on item icon size and maximum drawabale area
        self.total_page_count = 1
        self.current_page = 1

        # --- Paging Control Frame ---
        self.control_frame = tk.Frame(self)
        self.control_frame.pack(side="top", fill="x")

        self.prev_button = tk.Button(self.control_frame, text="< Previous", command=lambda: self.switch_page(-1), state=tk.DISABLED)
        self.prev_button.pack(side="left", padx=5)

        self.page_label = tk.Label(self.control_frame)
        self.update_page_text()
        self.page_label.pack(side="left", padx=10)

        self.next_button = tk.Button(self.control_frame, text="Next >", command=lambda: self.switch_page(1), state=tk.DISABLED)
        self.next_button.pack(side="left", padx=5)
        # ----------------------------

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.item_grid = tk.Frame(self.canvas)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.item_grid, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.item_grid.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda x: self.canvas.after_idle(self.update_item_layout))

        for i in (self.canvas, self.item_grid):
            i.bind("<Enter>", self.bind_grid_scroll)
            i.bind("<Leave>", self.unbind_grid_scroll)
            i.bind("<Control-a>", self.select_all_callback)
            i.bind("<Control-A>", self.select_all_callback)

        self.result_queue = queue.Queue()
        self.processing_threads_pool = concurrent.futures.ThreadPoolExecutor(max_workers=thread_count)

        if self.profile_save_filename != None:
            import cProfile
            self.profiler = cProfile.Profile()
            self.profiler.enable()

        self.item_list=[]
        for index, data in enumerate(self.input_data["sources"]):
            interface_data = load_interface_data(self.input_data, index, 'list-thumbnails')
            for item in interface_data["file_list"]:
                self.item_list.append(item)
        random.shuffle(self.item_list)

        self.after(0, self.check_queue)

    def update_page_button_state(self):
        if len(self.items) == len(self.item_list):
            if self.current_page == 1 :
                self.prev_button.config(state=tk.DISABLED)
            else:
                self.prev_button.config(state=tk.NORMAL)

            if self.current_page == self.total_page_count:
                self.next_button.config(state=tk.DISABLED)
            else:
                self.next_button.config(state=tk.NORMAL)

    def switch_page(self,num):
        self.current_page += num
        self.update_page_button_state()
        self.update_item_layout( force_regrid=True )
        self.canvas.yview_moveto(0)
        self.update_page_text()

    def start_loading(self):
        for item_data in self.item_list:
            self.processing_threads_pool.submit(Item.preload_media_data, self.result_queue, item_data, self.thumb_size)

    def check_queue(self):
        try:
            while not self.result_queue.empty():
                result = self.result_queue.get_nowait()
                self.add_item(result)
        except queue.Empty:
            pass

        if len(self.items) != len(self.item_list):
            self.after(1, self.check_queue)
        else:
            self.processing_threads_pool.shutdown(wait=False)


    def add_item(self, result):
        item_data, pil_image, create_epoch = result

        new_item = Item(
            self.item_grid,
            item_data,
            self.selected_items,
            self.input_data,
            0,
            self.thumb_size,
            self.cget('bg'),
            "#5293fa",
            self.bind_grid_scroll,
            self.unbind_grid_scroll,
            self.full_screen_callback,
            self.shift_select,
            self.select_all_callback,
            bd=self.item_border_size,
            preloaded_image=pil_image,
            preloaded_epoch=create_epoch
        )

        self.items.append(new_item)
        self.update_item_layout()
        new_item.update_idletasks()

        self.update_progress_bar_callback(len(self.items))

        if len(self.item_list) == len(self.items):
            self.items.sort(key=lambda x: x.create_epoch)
            self.update_item_layout(force_regrid=True)
            if self.profile_save_filename != None:
                self.profiler.disable()
                self.profiler.dump_stats(self.profile_save_filename)
                self.tk_root.destroy()


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

    def calculate_item_location(self, idx, items_per_row):
        page = ((( idx // items_per_row )) // self.rows_per_page)+1
        row = ( idx // items_per_row ) % self.rows_per_page
        col = idx % items_per_row
        return (page,row,col)

    def update_page_text(self):
        self.page_label.config(text=f"Page {self.current_page} of {self.total_page_count}")

    def update_item_layout(self, event=None, force_regrid=False):
        canvas_width = self.canvas.winfo_width()

        items_per_row = max(1, canvas_width // (self.thumb_size[0] + self.item_border_size*2 + self.item_padding*2))

        if self.last_items_per_row != items_per_row or force_regrid==True:
            new_pages = self.calculate_item_location(self.last_item_count, items_per_row)[0];
            if new_pages != self.total_page_count:
                self.total_page_count = new_pages
                if self.current_page > self.total_page_count:
                    self.current_page = self.total_page_count
                self.update_page_text()
                self.update_page_button_state()

            for item in self.items:
                item.grid_forget()

            for idx, item in enumerate(self.items):
                page,row,col = self.calculate_item_location(idx,items_per_row)
                if page == self.current_page:
                    item.grid(row=row, column=col, padx=self.item_padding, pady=self.item_padding, sticky="nsew")

            if self.last_items_per_row<items_per_row:
                self.update_scrollregion()

            self.last_items_per_row = items_per_row
            self.last_item_count = len(self.items)

        elif self.last_item_count != len(self.items):
            idx = len(self.items)-1
            item = self.items[-1]
            max_pages_now, row, col = self.calculate_item_location(idx,items_per_row)

            updated_pages = False
            if max_pages_now > self.total_page_count:
                for item in self.items:
                    item.grid_forget()

                self.total_page_count = max_pages_now
                self.current_page = max_pages_now

                self.update_page_text()
                self.update_scrollregion()
                self.canvas.yview_moveto(0)
                updated_pages = True

            item.grid(row=row, column=col, padx=self.item_padding, pady=self.item_padding, sticky="nsew")
            self.last_item_count = idx

            if updated_pages == False:
                self.canvas.yview_moveto(1)

            #It checks if all items have been loaded and if they have it initialises the buttons
            self.update_page_button_state()

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

    def __init__(self, root, item_data, selected_items, input_data, input_data_source_index, thumb_size, bg_color, select_color, enter_callback, leave_callback, full_screen_callback, shift_select_callback, select_all_callback, preloaded_image=None, preloaded_epoch=-1, **kwargs):
        super().__init__(root, **kwargs)

        self.selected_items = selected_items
        self.dragged_over = set()
        self.bg_color = bg_color
        self.select_color = select_color
        self.file_path = item_data["file_path"]
        self.full_screen_callback = full_screen_callback
        self.shift_select_callback = shift_select_callback
        self.select_all_callback = select_all_callback
        self.create_epoch = preloaded_epoch

        if preloaded_image:
            self.photo_obj = ImageTk.PhotoImage(preloaded_image)
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

        if self.create_epoch == -1:
            print(f"Warning: No create date could be found for file {self.file_path}")

    @staticmethod
    def preload_media_data(queue_ref, item_data, thumb_size):

        file_path = item_data["file_path"]

        if "metadata_file" in item_data:
            exif_path = item_data["metadata_file"]
        else:
            exif_path = file_path

        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError("File not found for item")

        #Create thumbnail image
        if item_data["file_type"] in ["image-preview", "image"]:
            try:
                img = Image.open(file_path).convert("RGB")
                img.thumbnail(thumb_size)
            except Exception:
                img = Image.new("RGB", thumb_size, (100, 100, 100))

        elif item_data["file_type"] == "video":
            player = mpv.MPV(vo='null', ao='null')
            player.pause = True
            player.play(file_path)
            start_time = datetime.now()
            while True:
                if (datetime.now() - start_time).total_seconds() > 15:
                    #Timeout
                    img = Image.new("RGB", thumb_size, (100, 100, 100))
                    print(f"Timed out loading video '{file_path}'")
                    break
                try:
                    img = player.screenshot_raw()
                    break;
                except Exception:
                    time.sleep(0.2)
            player.command('quit')
            del player
            img.thumbnail(thumb_size)
        else:
            img = Image.new("RGB", thumb_size, (60, 60, 60))

        create_epoch = -1

        try:
            pil_img = Image.open(exif_path)
            exif_data = pil_img._getexif()
            if exif_data:
                # 36867 is DateTimeOriginal, 306 is DateTime
                date_str = exif_data.get(36867) or exif_data.get(306)
                if date_str:
                    dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    create_epoch = int(dt.replace(tzinfo=timezone.utc).timestamp())
        except Exception:
            pass

        if create_epoch == -1:
            try:
                with ExifToolHelper() as et:
                    metadata = et.get_metadata(exif_path)
                    for d in metadata:
                        for key, value in d.items():
                            match key:
                                case "EXIF:CreateDate"|"QuickTime:CreateDate": #TODO add subseconds
                                    create_date_notz = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                                    create_date = create_date_notz.replace(tzinfo=timezone.utc)
                                    create_epoch = int(create_date.timestamp())
            except Exception:
                pass

        queue_ref.put((item_data, img, create_epoch))

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
