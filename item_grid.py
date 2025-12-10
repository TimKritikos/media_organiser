import tkinter as tk
import concurrent.futures
import queue
import random

import item

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
        self.linked_count = 0

        self.rows_per_page = 100 # TODO caluclaute based on item icon size and maximum drawabale area
        self.total_page_count = 1
        self.current_page = 1

        # --- Paging Control Frame ---
        self.control_frame = tk.Frame(self)

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
        self.canvas.grid   (row=1, column=0, sticky='nswe')
        self.scrollbar.grid(row=0, column=1, sticky='nse', rowspan=2)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

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
                self.item_list.append((item,data[1]))
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
            self.processing_threads_pool.submit(item.Item.preload_media_data, self.result_queue, item_data, self.thumb_size, self.input_data)

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

        new_item = item.Item(
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
        self.startup_update_item_layout()
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

        if self.last_items_per_row != items_per_row or force_regrid :
            new_pages = self.calculate_item_location(len(self.items)-1, items_per_row)[0];
            if  new_pages != 0 and ( new_pages != self.total_page_count or (self.current_page != self.total_page_count and ( len(self.items) != len(self.item_list) ) ) ):
                if new_pages == 1:
                    self.control_frame.grid_forget()
                elif self.total_page_count == 1:
                    self.control_frame.grid(row=0, column=0, sticky='nwe')
                self.total_page_count = new_pages
                # Handles case where after we load all data, the page count decreases and the second part when we still load data
                if self.current_page > self.total_page_count or len(self.items) != len(self.item_list):
                    self.current_page = self.total_page_count
                self.update_page_text()
                self.update_page_button_state()

            for item in self.items:
                item.grid_forget()

            for idx, item in enumerate(self.items):
                page,row,col = self.calculate_item_location(idx,items_per_row)
                if page == self.current_page:
                    item.grid(row=row, column=col, padx=self.item_padding, pady=self.item_padding, sticky="nsew")

            self.update_scrollregion()

            self.last_items_per_row = items_per_row
            return True
        return False

    def startup_update_item_layout(self):
        canvas_width = self.canvas.winfo_width()
        items_per_row = max(1, canvas_width // (self.thumb_size[0] + self.item_border_size*2 + self.item_padding*2))

        if self.update_item_layout() == False:
            idx = len(self.items)-1
            item = self.items[-1]
            max_pages_now, row, col = self.calculate_item_location(idx,items_per_row)

            if max_pages_now > self.total_page_count:
                self.update_item_layout(force_regrid=True)
                self.canvas.yview_moveto(0)
            else:
                item.grid(row=row, column=col, padx=self.item_padding, pady=self.item_padding, sticky="nsew")
                self.canvas.yview_moveto(1)

            #It checks if all items have been loaded and if they have it initialises the buttons
            self.update_page_button_state()

        self.update_scrollregion()

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

    def checkmark_items(self, file_list):
        for i in self.items:
            if i.file_path in file_list:
                i.add_checkmark()
                self.linked_count += 1
