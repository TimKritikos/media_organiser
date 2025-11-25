import tkinter as tk
import re
import os

# Note: clear needs to be called to initialise the contents of the window
class ShellScriptWindow(tk.Frame):
    def __init__(self, root, input_data):
        super().__init__(root)
        self.text_widget = tk.Text(self, bg='black', fg='white', height=8)
        self.text_widget.grid(row=0, column=0, sticky='nswe')
        self.script_written_lines = set()
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.text_widget.yview)
        self.text_widget['yscrollcommand'] = self.scrollbar.set
        self.scrollbar.grid(row=0, column=1, sticky='ns')
        self.input_data = input_data
        self.query_project_queued_in_script = None

        self.text_widget.tag_configure("parameters", foreground="#FC8DF5")
        self.text_widget.tag_configure("keywords_builtins", foreground="#B5732D")
        self.text_widget.tag_configure("posix_commands", foreground="#B5732D")
        self.text_widget.tag_configure("strings", foreground="#EB2626")
        self.text_widget.tag_configure("comments", foreground="#26A2EB")
        self.text_widget.tag_configure("quote_chars", foreground="#B5732D")

        self.syntax_highlighting_patterns = {
                "keywords_builtins": r"\b(set|trap)\b",
                "posix_commands": r"\b(ln|mkdir)\b",
                "strings": r"(['\"]).*?\1",
                "comments": r"#.*",
                "parameters": r"-[a-zA-Z0-9_]+"
                }

        self.text_widget.tag_configure("error", background="red")

    def treat_strings_for_posix_shell(self, string):
        return "'"+string.replace('\'','\'"\'"\'')+"'"

    def add_file(self, file_path, project_name):
        destination_project_dir = self.get_destination_dir(project_name)

        link_contents=os.path.relpath( file_path, destination_project_dir )
        print(os.path.join(os.path.dirname(destination_project_dir), link_contents))
        if not os.path.isfile(os.path.join(os.path.dirname(destination_project_dir), link_contents)) and not self.query_project_queued_in_script(project_name):
            raise ValueError("Link contents when resolved don't exist. This should only happen if this code generated absolute paths in a different way than the interface, one using physical and the other logical resolution")
        line = "ln -s " + self.treat_strings_for_posix_shell(link_contents) + " " + self.treat_strings_for_posix_shell(destination_project_dir) + "\n"
        if line not in self.script_written_lines:
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, line)
            self.text_widget.config(state=tk.DISABLED)
            self.syntax_highlight_lines((4+len(self.script_written_lines), ))
            self.script_written_lines.add(line)
            self.text_widget.see("end")

    def get_script(self):
        return self.text_widget.get("1.0", tk.END)

    def get_destination_dir(self, project_name):
        if self.query_project_queued_in_script == None:
            raise TypeError # This should never happen

        destination_project_dir = os.path.join(os.path.realpath(os.path.join(self.input_data["destinations"][0], project_name, self.input_data["destinations_append"])),'.')

        if not self.query_project_queued_in_script(project_name) and not os.path.isdir(destination_project_dir):
            raise FileNotFoundError("Selected project directory with the set destination append path doesn't exist")
            return

        # This is a last line of defense. This shouldn't ever be true
        if destination_project_dir.find('//') != -1 or destination_project_dir.find('/./') != -1 or destination_project_dir.find('/../') != -1:
            raise ValueError("Created a path that's not fully efficient")

        return destination_project_dir

    def clear(self, bash_side_channel_write_fd):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(tk.END, "#!/bin/sh\nset -eu\n\n")
        self.text_widget.config(state=tk.DISABLED)
        self.syntax_highlight_lines((1, 2))
        self.update_bash_side_channel_write_fd(bash_side_channel_write_fd)
        self.script_written_lines.clear()

    def mark_error_line(self, line):
        for tag in self.syntax_highlighting_patterns:
            self.text_widget.tag_remove(tag, f"{line}.0", f"{line}.end")
        self.text_widget.tag_add("error", f"{line}.0", f"{line}.end")
        self.text_widget.see(f"{line}.0")

    def unmark_error_line(self, line):
        self.text_widget.tag_remove("error", f"{line}.0", f"{line}.end")
        self.syntax_highlight_lines((line, ))

    def update_bash_side_channel_write_fd(self, fd):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete('3.0', '4.0')
        self.text_widget.insert('3.0', f"trap 'echo \"$LINENO\" >&{fd}' ERR # For debug\n")
        self.text_widget.config(state=tk.DISABLED)
        self.syntax_highlight_lines((3, ))

    def syntax_highlight_lines(self, lines):
        for line in lines:
            code = self.text_widget.get(f"{line}.0", f"{line}.end")

            for tag in self.syntax_highlighting_patterns:
                self.text_widget.tag_remove(tag, f"{line}.0", f"{line}.end")

            for tag, pattern in self.syntax_highlighting_patterns.items():
                for match in re.finditer(pattern, code):
                    start = f"{line}.0+{match.start()}c"
                    end =   f"{line}.0+{match.end()}c"
                    self.text_widget.tag_add(tag, start, end)
                    if tag == "strings":
                        start =  f"{line}.0+{match.start()}c"
                        start_ = f"{line}.0+{match.start()+1}c"
                        end =    f"{line}.0+{match.end()-1}c"
                        end_ =   f"{line}.0+{match.end()}c"
                        self.text_widget.tag_add("quote_chars", start, start_)
                        self.text_widget.tag_add("quote_chars", end, end_)

    def new_project_callback(self, name):
        line = "mkdir -p " + self.treat_strings_for_posix_shell(self.get_destination_dir(name))+"\n"
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, line)
        self.text_widget.config(state=tk.DISABLED)
        self.syntax_highlight_lines((4+len(self.script_written_lines), ))
        self.text_widget.see("end")
        self.script_written_lines.add(line) # This is mainly to get syntax highlighting linue number working in add_file
