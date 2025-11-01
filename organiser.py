import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import subprocess
import argparse


class MediaSelectorApp:
    def __init__(self, master, card_data, card_dir, media_dir, organised_dir):
        self.master = master
        self.master.title("Media Selector")
        self.organised_dir = organised_dir
        self.selected_items = set()  # set of selected file paths
        self.all_items = card_data   # list of file objects from JSON
        self.media_dir = media_dir
        self.card_dir = card_dir

        # Layout: main frame
        self.main_frame = tk.Frame(master)
        self.main_frame.pack(fill="both", expand=True)

        # Left panel: grid of items
        self.grid_frame = tk.Frame(self.main_frame)
        self.grid_frame.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(self.grid_frame)
        self.scrollbar = tk.Scrollbar(self.grid_frame, orient="vertical", command=self.canvas.yview)
        self.item_grid = tk.Frame(self.canvas)
        self.item_grid.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.item_grid, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Right panel: project listing
        self.dir_frame = tk.Frame(self.main_frame, width=400, bd=2, relief="sunken")
        self.dir_frame.pack(side="right", fill="y")
        self.dir_listbox = tk.Listbox(self.dir_frame)
        self.dir_listbox.pack(fill="both", expand=True)

        # Save button
        self.save_button = tk.Button(master, text="Save Selections", command=self.save_selections)
        self.save_button.pack(pady=5)

        # Load directories into listbox
        self.load_directories()

        # Display media grid
        self.display_media()

    def load_directories(self):
        if not os.path.isdir(self.organised_dir):
            print("ERROR: organised dir is invalid")
            return
        dirs = [d for d in os.listdir(self.organised_dir) if os.path.isdir(os.path.join(self.organised_dir, d))]
        dirs.sort()
        for d in dirs:
            self.dir_listbox.insert(tk.END, d)

    def display_media(self):
        """Display all media in a fixed 4-column grid."""
        for widget in self.item_grid.winfo_children():
            widget.destroy()

        thumb_size = (180, 180)
        cols = 4

        self.thumbnails = []

        for idx, file_obj in enumerate(self.all_items):
            filepath = self.media_dir+"/"+self.card_dir+"/"+file_obj["filename"]
            if not filepath or not os.path.exists(filepath):
                print("ERROR: file in json from source media interface executable couldn't be found")
                continue

            row = idx // cols
            col = idx % cols

            if file_obj["file_type"] in ["image-preview","image"]:
                #File type is image
                try:
                    img = Image.open(filepath).convert("RGB")
                    img.thumbnail(thumb_size)
                    photo = ImageTk.PhotoImage(img)
                except Exception:
                    #couldn't open or read the image file
                    img = Image.new("RGB", thumb_size, (100, 100, 100))
                    photo = ImageTk.PhotoImage(img)
            else:
                # Video placeholder
                img = Image.new("RGB", thumb_size, (60, 60, 60))
                photo = ImageTk.PhotoImage(img)

            self.thumbnails.append(photo)  # persist reference

            # Frame for each media item
            item_frame = tk.Frame(self.item_grid, bd=2)
            item_frame.grid(row=row, column=col, padx=10, pady=10)

            label = tk.Label(item_frame, image=photo)
            label.pack()
            name_label = tk.Label(item_frame, text=os.path.basename(filepath), wraplength=140)
            name_label.pack()

            # Click to select/deselect
            label.bind("<Button-1>", lambda e, path=filepath, f=item_frame: self.toggle_selection(path, f))

    def toggle_selection(self, filepath, frame):
        """Toggle selection highlight on click."""
        if filepath in self.selected_items:
            self.selected_items.remove(filepath)
            frame.config(bd=2, relief="ridge", bg="#FFFFFF")
        else:
            self.selected_items.add(filepath)
            frame.config(bd=4, relief="solid", bg="#b3d9ff")

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
    parser.add_argument('card_dir', type=str, help='The directory of the card to be organised relative to the current working directory or an absolute path')
    parser.add_argument('organised_dir', type=str, help='The organised dir the contains project directories. Relative to the current working directory or an absolute path')
    parser.add_argument('-v','--version', help='print the version of this program and exit successfully', action="version", version=version)

    args = parser.parse_args()

    if not os.path.isdir(args.card_dir):
        print("ERROR: Provided card_dir doesn\'t exist")
        return 1
    media_dir=os.path.abspath(args.card_dir).split("/MEDIA/")[0]+"/MEDIA"
    if not os.path.isdir(media_dir):
        print("ERROR: Calculated media_dir or card_dir doesn\'t exist")
        return 1
    card_dir_absolute=os.path.abspath(args.card_dir)
    if card_dir_absolute.find("/MEDIA/") == -1:
        print("ERROR: card_dir doesn't not seem to be in MEDIA or is the root of MEDIA")
        return 1
    card_dir=card_dir_absolute.split("/MEDIA/")[1]
    if not os.path.isdir(media_dir+"/"+card_dir):
        print("ERROR: Calculated card_dir is invalid")
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


    app = MediaSelectorApp(root,card_item_list["file_list"],card_dir,media_dir, media_dir+"/"+organised_dir_sanitised)
    root.mainloop()


if __name__ == "__main__":
    main()
