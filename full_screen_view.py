import tkinter as tk
from exiftool import ExifToolHelper
from datetime import datetime
from datetime import timezone
import mpv
import os
from PIL import Image, ImageTk
from tkinter import ttk

import media_interface

class FullScreenItem(tk.Frame):
    def __init__(self, root, input_data, file_path, exit_callback, **kwargs):
        super().__init__(root, **kwargs)

        self.best_file = None
        self.exit_callback = exit_callback
        self.image = None
        self.old_image_size = (0, 0)

        data = media_interface.load_interface_data(input_data, 0, 'get-related', arg=file_path)

        for file in data["file_list"]:
            if file["item_type"] == file["file_type"]:
                self.best_file = file

        if self.best_file == None:
            raise ValueError

        self.best_file_path = os.path.join(input_data["sources"][0], self.best_file["file_path"])

        self.content_frame = tk.Frame(self)
        self.metadata_frame = tk.Frame(self)

        with ExifToolHelper() as et:
            metadata = et.get_metadata(self.best_file_path)
            self.metadata = {
                    "Filename": "",
                    "Create date": "",
                    "Create time": ""
                    }
            for d in metadata:
                if "Composite:ShutterSpeed" in d:
                    #Add the exposure values in this order if they exist
                    self.metadata["Shutter speed"]=""
                    self.metadata["Aperature"]=""
                    self.metadata["ISO"]=""
                    self.metadata["Focal length (35mm)"]=""
                    break

            for d in metadata:
                for key, value in d.items():
                    match key:
                        case "File:FileName":
                            self.metadata["Filename"] = value
                        case "EXIF:Make":
                            self.metadata["Camera make"] = value
                        case "EXIF:Model"|"QuickTime:Model":
                            self.metadata["Camera model"] = value
                        case "EXIF:CreateDate"|"QuickTime:CreateDate":
                            try:
                                create_date_notz = datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                                create_date = create_date_notz.replace(tzinfo=timezone.utc)
                                self.metadata["Create date"] = create_date.strftime("%Y-%m-%d")
                                self.metadata["Create time"] = create_date.strftime("%H:%M:%S")
                            except AttributeError:
                                True
                        case "Composite:ShutterSpeed":
                            if int(value) < 1:
                                if (1/value) % 1 < 0.01:
                                    self.metadata["Shutter speed"] = "1/"+str(int(1/value))+" s"
                                else:
                                    self.metadata["Shutter speed"] = "1/"+str(1/value)+" s"
                            else:
                                if value % 1 < 0.01:
                                    self.metadata["Shutter speed"] = str(int(value))+" s"
                                else:
                                    self.metadata["Shutter speed"] = str(value)+" s"
                        case "EXIF:ISO":
                            self.metadata["ISO"] = str(value)
                        case "EXIF:FNumber":
                            self.metadata["Aperature"]="f"+str(value)
                        case "EXIF:Software"|"QuickTime:FirmwareVersion":
                            self.metadata["Software version"] = value
                        case "EXIF:SubSecTimeOriginal":
                            self.metadata["Create time"] += "."+str(value)
                        case "EXIF:ExposureCompensation"|"QuickTime:ExposureCompensation":
                            self.metadata["Exposure compensation"] = str(value)
                        case "EXIF:FocalLengthIn35mmFormat":
                            self.metadata["Focal length (35mm)"] = str(value)+"mm"
                        case "EXIF:Contrast":
                            self.metadata["Contrast"] = str(value)
                        case "EXIF:Saturation":
                            self.metadata["Saturation"] = str(value)
                        case "EXIF:Sharpness"|"QuickTime:Sharpness":
                            self.metadata["Sharpness"] = str(value)
                        case "EXIF:SerialNumber"|"QuickTime:CameraSerialNumber":
                            self.metadata["Serial Number"] = value
                        case "APP6:HDRSetting"|"QuickTime:HDRVideo":
                            self.metadata["HDR Setting"] = value
                        case "EXIF:DigitalZoomRatio"|"QuickTime:DigitalZoomAmount":
                            self.metadata["Digital Zoom ratio"] = str(value)
                        case "EXIF:LensModel":
                            self.metadata["Lens model"] = value
                        case "MakerNotes:ImageStabilization":
                            self.metadata["Image stabilization"] = str(value) #TODO figure what the values mean
                        case "MakerNotes:ElectronicFrontCurtainShutter":
                            self.metadata["Electronic Front Curtain"] = str(value)
                        case "MakerNotes:FocusMode":
                            self.metadata["Focus mode"] = str(value) #TODO figure what the values mean
                        case "MakerNotes:FocusLocation":
                            True #TODO maybe draw it?
                        case "MakerNotes:BatteryTemperature":
                            self.metadata["Battery temprature"]="{:.1f}".format(value)+"°C"#TODO make sure it's celsius
                        case "MakerNotes:BatteryLevel":
                            self.metadata["Battery level"] = str(value)+"%"
                        case "MakerNotes:ShutterCount":
                            self.metadata["Shutter count"] = str(value)
                        case "Composite:FocusDistance2":
                            self.metadata["Focus distance"] = str(value)+"m"
                        case "QuickTime:ElectronicStabilizationOn":
                            self.metadata["S/W Image stabilization"] = str(value)
                        case "QuickTime:BitrateSetting":
                            self.metadata["Video bitrate"] = str(value)
                        #case "QuickTime:BitDepth":
                        #    self.metadata["Bit depth"] = int(value/3)
                        case "QuickTime:VideoFrameRate":
                            self.metadata["Framerate"] = str(value)
                        case "Composite:AvgBitrate":
                            self.metadata["Average bitrate"]="{:.1f}".format(value/1000/1000)+"Mbps"
                        case "Composite:ImageSize":
                            self.metadata["Resolution"] = str(value).replace(' ','x')
                        case "QuickTime:AudioSampleRate":
                            self.metadata["Audio Sample rate"]="{:.1f}".format(value/1000)+"kHz"
                        case "QuickTime:AudioBitsPerSample":
                            self.metadata["Audio Bit depth"] = str(value)
                        case "QuickTime:AudioChannels":
                            self.metadata["Audio Channels"] = str(value)
                        case "QuickTime:CompressorName":
                            self.metadata["Video Compressor name"] = str(value)
                        case "QuickTime:CompressorID":
                            codec="unknown ("+value+")"
                            match value:
                                case "hvc1":
                                    codec="H.265"
                            self.metadata["Video codec"] = codec

        self.metadata_canvas = tk.Canvas(self.metadata_frame, highlightthickness=0, width=250, height=1000)
        self.metadata_canvas.grid(row=0, column=0, sticky='nswe')
        self.metadata_canvas.grid_rowconfigure(0, weight=1)
        self.metadata_canvas.grid_columnconfigure(0, weight=1)

        metadata_key_x_end = 150
        metadata_value_x_start = metadata_key_x_end+5
        metadata_y_start = 20
        metadata_y_step = 15

        for i, (key, value) in enumerate(self.metadata.items()):
            y = metadata_y_start + i * metadata_y_step

            key_id = self.metadata_canvas.create_text(metadata_key_x_end, y, text=key+":", anchor="e", fill="#333")
            val_id = self.metadata_canvas.create_text(metadata_value_x_start, y, text=value, anchor="w", fill="#000")

        self.attach_binds(self.metadata_canvas)

        self.content_frame.grid(row=0, column=0, sticky='nswe')
        self.attach_binds(self.content_frame)

        self.metadata_frame.grid(row=0, column=1, sticky='nse')
        self.attach_binds(self.metadata_frame)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.attach_binds(self)
        self.mpv = None

        if self.best_file["item_type"] == "image":
            self.img = Image.open(self.best_file_path).convert("RGB")
        elif self.best_file["item_type"] == "video":
            self.video_frame = tk.Frame(self.content_frame)
            self.video_frame.pack(fill=tk.BOTH, expand=True)
            self.control_frame = tk.Frame(self.content_frame, bg="grey")
            self.control_frame.pack(fill=tk.X)

            self.video_play_button = ttk.Button(self.control_frame, text="Play", command=self.video_play_pause)
            self.video_play_button.pack(side=tk.LEFT, padx=5)
            self.scale = ttk.Scale(self.control_frame, from_=0, to=100, orient=tk.HORIZONTAL)
            self.scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            self.scale.bind("<Button-1>", self.video_scale_click)

            self.attach_binds(self.video_frame)
            self.attach_binds(self.control_frame)

            window_id = self.video_frame.winfo_id()
            self.mpv = mpv.MPV( wid=window_id, vo='x11', keep_open=True)

            if self.best_file["file_type"] == "video":
                self.mpv.pause = True
                self.video = self.mpv.play(self.best_file_path)

            self.mpv.observe_property('time-pos', self.video_time_callback)

    def video_time_callback(self, name, value):
        if value != None and self.mpv.duration != None:
            self.scale.set((value*100)/self.mpv.duration)

    def video_scale_click(self, event):
        scale_length = self.scale.winfo_width()
        self.scale.set((event.x/scale_length)*100)
        self.mpv.time_pos = (event.x/scale_length)*self.mpv.duration

    def video_play_pause(self):
        if self.mpv.pause == False:
            self.video_play_button.config(text="play")
            self.mpv.pause = True
        elif self.mpv.pause == True:
            self.video_play_button.config(text="pause")
            self.mpv.pause = False

    def attach_binds(self, widget):
        widget.bind("<Configure>", lambda x: self.after_idle(self.update_size))
        widget.bind("<Key>", self.key_callback)
        widget.bind("<Enter>", lambda x: x.widget.focus_set() )

    def enter(self, event):
        event.widget.focus_set()

    def key_callback(self, event):
        match event.char:
            case '\r':
                self.exit_callback()
            case ' ':
                self.video_play_pause()
            case '.':
                self.mpv.command('frame-step')
                self.video_play_button.config(text="play")
            case ',':
                self.mpv.command('frame-back-step')
                self.video_play_button.config(text="play")

    def update_size(self):
        if self.best_file["item_type"] == "image":
            frame_width = self.content_frame.winfo_width()
            frame_height = self.content_frame.winfo_height()
            image_size = (frame_width, frame_height)
            if image_size != self.old_image_size:
                self.old_image_size = image_size
                if self.image:
                    self.image.destroy()
                if self.best_file["item_type"] in [ "image"]:
                    image_resized = self.img.copy()
                    image_resized.thumbnail(image_size)
                else:
                    image_resized = Image.new("RGB", image_size, (60, 60, 60))

                self.photo_obj = ImageTk.PhotoImage(image_resized)
                self.image = tk.Label(self.content_frame, image=self.photo_obj, borderwidth=0)
                self.image.grid(row=0, column=0, sticky='nw')
