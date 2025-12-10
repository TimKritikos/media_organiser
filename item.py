import gnss_track_helpers
import constants
import tkinter as tk
from PIL import Image, ImageTk
import mpv
from datetime import datetime
from exiftool import ExifToolHelper
from datetime import timezone
import os
import time

import icons

class Item(tk.Frame):
    last_selected = None
    mouse_action = 1

    def __init__(self, root, item_data, selected_items, input_data, input_data_source_index, thumb_size, bg_color, select_color, enter_callback, leave_callback, full_screen_callback, shift_select_callback, select_all_callback, preloaded_image=None, preloaded_epoch=-1, **kwargs):
        super().__init__(root, **kwargs)

        self.selected_items = selected_items
        self.dragged_over = set()
        self.bg_color = bg_color
        self.select_color = select_color
        self.file_path = item_data[0]["file_path"]
        self.source_properties = item_data[1]
        self.full_screen_callback = full_screen_callback
        self.shift_select_callback = shift_select_callback
        self.select_all_callback = select_all_callback
        self.create_epoch = preloaded_epoch
        self.icon_check_label = None

        if preloaded_image:
            self.photo_obj = ImageTk.PhotoImage(preloaded_image)
        else:
            img = Image.new("RGB", thumb_size, (60, 60, 60))
            self.photo_obj = ImageTk.PhotoImage(img)


        self.image = tk.Label(self, image=self.photo_obj, borderwidth=0)
        self.image.pack()
        self.icons = tk.Frame(self)
        self.icons.pack(fill=tk.X)
        self.caption = tk.Label(self, text=os.path.basename(self.file_path), wraplength=thumb_size[0], borderwidth=0)
        self.caption.pack()

        self.icon_size=(thumb_size[0]/8, thumb_size[1]/8)

        if item_data[0]["item_type"] == "video":
            icon=icons.gen_video_icon(self.icon_size)
        elif item_data[0]["item_type"] == "image":
            icon=icons.gen_image_icon(self.icon_size)
        elif item_data[0]["item_type"] == "gnss-track":
            icon=icons.gen_gnss_icon(self.icon_size)
        else:
            icon=icons.gen_unknown_icon(self.icon_size)
        self.icon_photo_obj = ImageTk.PhotoImage(icon)
        self.icon_label = tk.Label(self.icons,image=self.icon_photo_obj)

        self.icon_label.pack(side=tk.LEFT)

        for i in (self.image,self.icons, self.caption, self.icon_label, self):
            i.bind("<Button-1>", self.on_click)
            i.bind("<B1-Motion>", self.on_drag)
            i.bind("<Enter>", enter_callback)
            i.bind("<Leave>", leave_callback)
            i.bind("<Key>", self.key_callback)

        if self.source_properties == constants.source_properties.read_only:
            for i in (self.image, self.caption, self):
                i.config(bg='#404040')
            self.caption.config(fg='lightgrey')

        if self.create_epoch == -1:
            tk.messagebox.showinfo("Error",(f"Warning: No create date could be found for file {self.file_path}"))

    @staticmethod
    def preload_media_data(queue_ref, item_data, thumb_size, input_data):

        file_path = item_data[0]["file_path"]

        create_epoch = -1

        if "metadata_file" in item_data[0]:
            exif_path = item_data[0]["metadata_file"]
        else:
            exif_path = file_path

        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError("File not found for item")

        #Create thumbnail image
        if item_data[0]["file_type"] in ["image-preview", "image"]:
            try:
                img = Image.open(file_path).convert("RGB")
                orig_width, orig_height = img.size
                target_height = int(orig_height*(thumb_size[0]/orig_width))
                img = img.resize((thumb_size[0],target_height))
            except Exception:
                img = icons.gen_corrupted_file_icon(thumb_size)

        elif item_data[0]["file_type"] == "video":
            player = mpv.MPV(vo='null', ao='null')
            player.pause = True
            player.play(file_path)
            start_time = datetime.now()
            while True:
                if (datetime.now() - start_time).total_seconds() > 15:
                    #Timeout
                    img = icons.gen_corrupted_file_icon(thumb_size)
                    messagebox.showinfo("Error", f"ERROR: Timed out loading video '{file_path}'. It might be corrupt")
                    break
                try:
                    img = player.screenshot_raw()
                    break;
                except Exception:
                    time.sleep(0.2)
            player.command('quit')
            del player
            orig_width, orig_height = img.size
            target_height = int(orig_height*(thumb_size[0]/orig_width))
            img = img.resize((thumb_size[0],target_height))
        elif item_data[0]["file_type"] == "gnss-track":
            img, create_epoch = gnss_track_helpers.gnss_thumbnail_and_timestamp(file_path, force_offline=input_data["force_offline"], map_database=input_data["map_database"])
            orig_width, orig_height = img.size
            target_height = int(orig_height*(thumb_size[0]/orig_width))
            img = img.resize((thumb_size[0],target_height))
        else:
            img = icons.gen_corrupted_file_icon(thumb_size)

        #Try to get epoch with PIL
        if create_epoch == -1:
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

        #Try to get epoch with exiftool
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
        if self.source_properties != constants.source_properties.read_only:
            to_color_list = [self.image, self.caption, self.icons, self.icon_label, self]
            if self.icon_check_label != None:
                to_color_list.append(self.icon_check_label)
            for i in to_color_list:
                i.config(bg=self.bg_color)
            if self.file_path in self.selected_items:
                self.selected_items.remove(self.file_path)

    def select(self):
        if self.source_properties != constants.source_properties.read_only:
            to_color_list = [self.image, self.caption, self.icons, self.icon_label, self]
            if self.icon_check_label != None:
                to_color_list.append(self.icon_check_label)
            for i in to_color_list:
                i.config(bg=self.select_color)
            self.selected_items.add(self.file_path)

    def add_checkmark(self):
        checkmark_icon=icons.gen_checkmark_icon(self.icon_size)
        self.icon_check_obj = ImageTk.PhotoImage(checkmark_icon)
        self.icon_check_label = tk.Label(self.icons,image=self.icon_check_obj)
        self.icon_check_label.pack(side=tk.LEFT)

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
