import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import subprocess


class MediaSelectorApp:
    def __init__(self, master, root_dir):
        self.master = master
        self.master.title("Media Selector")
        self.root_dir = root_dir

        self.selected = set()  # set of selected file paths
        self.files = []        # list of file objects from JSON
        self.thumbnails = []   # persistent references to PhotoImage objects

        # Load JSON
        data = json.loads(subprocess.check_output(['cat', '/home/user/hmm/info.json']))
        self.files = data.get("files", [])

        # Layout: main frame
        self.main_frame = tk.Frame(master)
        self.main_frame.pack(fill="both", expand=True)

        # Left panel: grid of media
        self.grid_frame = tk.Frame(self.main_frame)
        self.grid_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(self.grid_frame)
        self.scrollbar = tk.Scrollbar(self.grid_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Right panel: directory listing
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
        """Populate the right panel with directories under root_dir."""
        if not os.path.isdir(self.root_dir):
            return
        dirs = [d for d in os.listdir(self.root_dir) if os.path.isdir(os.path.join(self.root_dir, d))]
        dirs.sort()
        for d in dirs:
            self.dir_listbox.insert(tk.END, d)
        if self.dir_listbox.size() > 0:
            self.dir_listbox.select_set(0)

    def display_media(self):
        """Display all media in a fixed 4-column grid."""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        thumb_size = (180, 150)
        cols = 4

        self.thumbnails = []

        for idx, file_obj in enumerate(self.files):
            filepath = file_obj.get("filename_here")
            if not filepath or not os.path.exists(filepath):
                continue

            row = idx // cols
            col = idx % cols

            ext = os.path.splitext(filepath)[1].lower()
            is_image = ext in [".jpg", ".jpeg", ".png", ".gif", ".bmp"]

            if is_image:
                try:
                    img = Image.open(filepath).convert("RGB")
                    img.thumbnail(thumb_size)
                    photo = ImageTk.PhotoImage(img)
                except Exception:
                    img = Image.new("RGB", thumb_size, (100, 100, 100))
                    photo = ImageTk.PhotoImage(img)
            else:
                # Video placeholder
                img = Image.new("RGB", thumb_size, (60, 60, 60))
                photo = ImageTk.PhotoImage(img)

            self.thumbnails.append(photo)  # persist reference

            # Frame for each media item
            item_frame = tk.Frame(self.scrollable_frame, bd=2, relief="ridge")
            item_frame.grid(row=row, column=col, padx=10, pady=10)

            label = tk.Label(item_frame, image=photo)
            label.pack()
            name_label = tk.Label(item_frame, text=os.path.basename(filepath), wraplength=140)
            name_label.pack()

            # Click to select/deselect
            label.bind("<Button-1>", lambda e, path=filepath, f=item_frame: self.toggle_selection(path, f))

    def toggle_selection(self, filepath, frame):
        """Toggle selection highlight on click."""
        if filepath in self.selected:
            self.selected.remove(filepath)
            frame.config(bd=2, relief="ridge", bg="#FFFFFF")
        else:
            self.selected.add(filepath)
            frame.config(bd=4, relief="solid", bg="#b3d9ff")

    def save_selections(self):
        """Save selected files and chosen directory to JSON."""
        if not self.selected:
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

        # Save full objects corresponding to selected paths
        #selected_objects = [f for f in self.files if f.get("filename_here") in self.selected]
        
        data = {
                "selected_directory": selected_dir,
                "selected_files": [f for f in self.selected ]
        }

        with open(save_path, "w") as f:
            json.dump(data, f, indent=4)

        messagebox.showinfo("Saved", f"Selections saved to:\n{save_path}")


def main():
    root = tk.Tk()
    root.geometry("1000x600")

    #json_path = filedialog.askopenfilename(
    #    title="Select JSON File",
    #    filetypes=[("JSON Files", "*.json")]
    #)
    #if not json_path:
    #    tk.messagebox.showwarning("No file selected", "No JSON file selected.")
    #    root.destroy()
    #    return

    root_dir = filedialog.askdirectory(
        title="Select Root Directory for Directory Panel"
    )
    if not root_dir:
        tk.messagebox.showwarning("No directory selected", "No root directory selected.")
        root.destroy()
        return

    app = MediaSelectorApp(root, root_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
