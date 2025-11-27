import tkinter as tk
from exiftool import ExifToolHelper
from datetime import datetime
from datetime import timezone
import mpv
import os
from PIL import Image, ImageTk
from tkinter import ttk
import tkintermapview

import media_interface

def get_video_length(file):
    player = mpv.MPV(vo='null',ao='null')
    player.pause=True
    player.play(file)
    start_time=datetime.now()
    while player.duration == None:
        if (datetime.now()-start_time).total_seconds() > 15 :
            #Timeout
            break;
    ret=player.duration
    player.command('quit')
    del player
    return ret

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

        self.best_file_path = self.best_file["file_path"]

        if "metadata_file" in data:
            self.exif_path = data["metadata_file"]
        else:
            self.exif_path = self.best_file_path

        self.content_frame = tk.Frame(self)
        self.metadata_frame = tk.Frame(self)

        with ExifToolHelper() as et:
            metadata = et.get_metadata(self.exif_path)
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
                                    self.metadata["Shutter speed"] = "1/"+"{:.2f}".format(1/value)+" s"
                            else:
                                    self.metadata["Shutter speed"] = "{:.2f}".format(value)+" s"
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
                            if value == 1:
                                self.metadata["Image stabilization"] = "enabled"
                            else:
                                self.metadata["Image stabilization"] = "disabled"
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
                        case "MakerNotes:Shutter":
                            if value == '0 0 0':
                                self.metadata["Shutter type:"]="electronic"
                            else:
                                self.metadata["Shutter type:"]="mechanical"
                        case "Composite:GPSPosition":
                            self.metadata["GPS"]=value

        metadata_key_x_end = 150
        metadata_value_x_start = metadata_key_x_end+5
        metadata_y_border = 20
        metadata_y_step = 15

        print()
        self.metadata_canvas = tk.Canvas(self.metadata_frame, highlightthickness=0, width=250, height=len(self.metadata)*metadata_y_step+metadata_y_border*2)
        self.metadata_canvas.grid(row=0, column=0, sticky='nwe')
        self.metadata_canvas.grid_rowconfigure(0, weight=1)
        self.metadata_canvas.grid_columnconfigure(0, weight=1)

        if "GPS" in self.metadata:
            long,lat = self.metadata["GPS"].split(' ')
            self.map_widget = tkintermapview.TkinterMapView(self.metadata_frame, width=400, height=400, corner_radius=10)
            self.map_widget.set_position(float(long),float(lat))
            self.map_widget.set_marker(float(long),float(lat))
            self.map_widget.set_zoom(15)
            self.map_widget.grid(row=1, column=0, sticky='nswe')
            self.map_widget.grid_rowconfigure(1, weight=1)
            self.map_widget.grid_columnconfigure(1, weight=1)

        for i, (key, value) in enumerate(self.metadata.items()):
            y = metadata_y_border + i * metadata_y_step

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

            self.video_parts_matching=[]

            related = media_interface.load_interface_data(input_data, 0, 'get-related', arg=file_path)

            start=0
            end=0
            for part_id_to_process in range(1,self.best_file["part_count"]+1):
                for i in related["file_list"]:
                    if i["part_num"] == part_id_to_process and i["file_type"] == 'video':
                        file=i
                        break;
                length=get_video_length(file["file_path"])
                start=end
                end=start+length
                self.video_parts_matching.append((file["file_path"],start,end))

            window_id = self.video_frame.winfo_id()
            self.mpv = mpv.MPV( wid=window_id, vo='x11', keep_open=True)

            self.mpv.pause = True
            self.playing_file=self.video_parts_matching[0]
            self.video = self.mpv.play(self.playing_file[0])

            self.mpv.observe_property('time-pos', self.video_time_callback)
            self.mpv.observe_property('eof-reached', self.on_end_file)

    def on_end_file(self, name, value):
        get_next=False
        if value is True:
            for i in self.video_parts_matching:
                if get_next==True:
                    self.switch_video_files_mpv(i)
                    break;
                if i[0] == self.playing_file[0]:
                    get_next=True


    def video_time_callback(self, name, value):
        scale_time_length = self.video_parts_matching[-1][2]
        if value != None :
            self.scale.set(((value+self.playing_file[1])*100)/scale_time_length)

    def switch_video_files_mpv(self, new_file):
        self.playing_file=new_file
        self.video = self.mpv.play(self.playing_file[0])
        #Wait for it to load the new video
        start_time=datetime.now()
        while ( self.mpv.time_pos == None ): #or self.mpv.time_pos < .2):
            if (datetime.now()-start_time).total_seconds() > 15 :
                #Timeout
                break;

    def video_scale_click(self, event):
        orig_pause=self.mpv.pause
        self.mpv.pause=True
        scale_pixel_length = self.scale.winfo_width()
        scale_time_length = self.video_parts_matching[-1][2]
        self.scale.set((event.x/scale_pixel_length)*100)

        new_time = (event.x/scale_pixel_length)*scale_time_length
        for i in self.video_parts_matching:
            if i[2] > new_time:
                file_to_play=i
                break;
        if self.playing_file[0]!=file_to_play[0]:
            self.switch_video_files_mpv(file_to_play)
        relative_time=new_time-self.playing_file[1];
        self.mpv.time_pos=relative_time
        self.mpv.pause=orig_pause

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
