import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import re
import subprocess
import os
import sys
import time
from threading import Thread
from collections import OrderedDict
import json
import http.server
import socketserver
import webbrowser

class VSCodelikeIDE(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LiteCode")
        self.geometry("1200x900")
        self.configure(bg="#1e1e1e")
        
        self.filename = None
        self.files = OrderedDict()
        self.language = "python"
        self.last_run_time = 0
        self.breakpoints = set()
        self.current_dir = os.getcwd()
        self.config_file = "codelite_config.json"
        self.folded_blocks = {}
        self.server_thread = None
        self.server_port = 8000
        self.settings = self.load_default_settings()
        self.lang_var = tk.StringVar(value="Python")
        
        self.lang_configs = self.load_language_configs()
        
        self.create_icon_set()
        self.dialog_set_theme()  # Corrected method name
        self.create_folder_explorer()
        self.create_main_area()
        self.create_menu()
        self.create_toolbar()
        self.create_status_bar()
        self.configure_syntax_highlighting()
        
        self.load_last_state()
        if not self.files: self.new_file()
        self.update_folder_explorer()
        self.setup_keybindings()

    # --- Language Configurations ---
    def load_language_configs(self):    #ne-roboaet-compiler-blet(    
        return {
        "python": {
            "ext": ".py",
            "keywords": ["def", "if", "else", "for", "while", "import", "class", "try", "except", "with"],
            "comment": r'#.*$',
            "runner": [sys.executable, "{file}"],
            "builtins": ["print", "len", "range", "input"]
        },
        "javascript": {
            "ext": ".js",
            "keywords": ["function", "if", "else", "for", "let", "const", "var", "return", "async", "await"],
            "comment": r'//.*$',
            "runner": ["node", "{file}"],
            "builtins": ["console.log", "alert", "fetch"]
        },
        "html": {
            "ext": ".html",
            "keywords": ["html", "head", "body", "div", "script", "style", "title", "p", "a", "img"],
            "comment": r'<!--[\s\S]*?-->',
            "runner": None,
            "builtins": []
        },
        "java": {
            "ext": ".java",
            "keywords": ["public", "class", "static", "void", "if", "else", "for", "int", "new", "return"],
            "comment": r'//.*$',
            "runner": ["sh", "-c", "javac {file} && java {class}"],
            "builtins": ["System.out.println", "Math.random"]
        },
        "c": {
            "ext": ".c",
            "keywords": ["int", "float", "if", "else", "for", "while", "return", "void", "struct", "char"],
            "comment": r'//.*$',
            "runner": ["sh", "-c", "gcc {file} -o a.out && ./a.out"],
            "builtins": ["printf", "scanf"]
        },
        "cpp": {
            "ext": ".cpp",
            "keywords": ["int", "float", "if", "else", "for", "while", "return", "class", "public", "private"],
            "comment": r'//.*$',
            "runner": ["sh", "-c", "g++ {file} -o a.out && ./a.out"],
            "builtins": ["cout", "cin"]
        }
    }
    # --- Settings ---
    def load_default_settings(self):
        return {
            "Editor": {"Font Size": ["8", "10", "12", "14", "16", "18", "20", "22", "24", "26"], "Font Family": ["Consolas", "Courier New", "Arial", "Times New Roman", "Monospace", "JetBrains Mono", "Fira Code", "Source Code Pro", "DejaVu Sans Mono", "Hack"],
                       "Tab Width": ["2", "4", "8", "12", "16", "20", "24", "28", "32", "36"], "Word Wrap": ["On", "Off", "Word", "Char", "None", "Auto", "Smart", "Line", "Block", "Custom"],
                       "Line Numbers": ["On", "Off", "Relative", "Absolute", "Hybrid", "Minimal", "Full", "Dynamic", "Static", "Custom"], "Auto Indent": ["On", "Off", "Smart", "Basic", "Advanced", "None", "Auto", "Manual", "Context", "Custom"],
                       "Syntax Highlighting": ["On", "Off", "Minimal", "Full", "Custom", "Dark", "Light", "Mono", "Vivid", "Subtle"], "Theme": ["Dark", "Light", "Solarized", "Monokai", "Dracula", "Nord", "One Dark", "Gruvbox", "Material", "Custom"],
                       "Cursor Style": ["Block", "Line", "Underline", "Box", "Bar", "Thin", "Thick", "Blink", "Solid", "Custom"], "Show Whitespace": ["On", "Off", "Tabs", "Spaces", "All", "None", "Minimal", "Dots", "Lines", "Custom"]},
            "File": {"Auto Save": ["On", "Off", "After Delay", "On Focus Loss", "On Run", "Manual", "Smart", "Periodic", "Custom", "None"], "Default Language": ["Python", "JavaScript", "HTML", "Java", "C", "C++", "C#", "TypeScript", "PHP", "Ruby"],
                     "File Encoding": ["UTF-8", "ASCII", "UTF-16", "ISO-8859-1", "Windows-1252", "UTF-32", "Big5", "Shift-JIS", "EUC-JP", "Custom"], "Line Ending": ["CRLF", "LF", "CR", "Auto", "System", "Unix", "Windows", "Mac", "Custom", "None"],
                     "Backup Files": ["On", "Off", "Daily", "Weekly", "Monthly", "On Save", "Manual", "Smart", "Custom", "None"], "Recent Files": ["5", "10", "15", "20", "25", "30", "35", "40", "45", "50"],
                     "Folder View": ["Tree", "List", "Flat", "Compact", "Detailed", "Icons", "Thumbnails", "Minimal", "Custom", "None"], "Save Prompt": ["On", "Off", "Always", "Never", "Modified", "Smart", "Auto", "Manual", "Custom", "None"],
                     "Open Last": ["On", "Off", "Folder", "File", "Both", "None", "Recent", "Pinned", "Custom", "Smart"], "File Extensions": ["Show", "Hide", "Custom", "Minimal", "Full", "Auto", "Smart", "None", "Icons", "Text"]},
        }

    # --- Set Theme for Dialogs ---
    def dialog_set_theme(self):
        self.option_add("*Background", "#1e1e1e")
        self.option_add("*Foreground", "white")
        self.option_add("*Entry.Background", "#2d2d2d")
        self.option_add("*Entry.Foreground", "white")
        self.option_add("*Button.Background", "#3c3c3c")
        self.option_add("*Button.Foreground", "white")
        self.option_add("*Label.Background", "#1e1e1e")
        self.option_add("*Label.Foreground", "white")

    # --- UI Setup ---
    def create_icon_set(self):
        self.icons = {"new": "📄", "open": "📂", "save": "💾", "run": "▶️", "debug": "🐞", "search": "🔍", "fold": "📘", "server": "🌐", "settings": "⚙️", "folder": "📁", "file": "📜"}

    def create_folder_explorer(self):
        self.explorer_frame = ttk.LabelFrame(self, text="Explorer", padding=5, style="Dark.TLabelframe")
        self.explorer_frame.pack(side="left", fill="y", padx=5)
        self.folder_tree = ttk.Treeview(self.explorer_frame, show="tree", selectmode="browse", style="Dark.Treeview")
        self.folder_tree.pack(fill="both", expand=True)
        self.folder_tree.bind("<Double-1>", self.open_from_explorer)

    def create_menu(self):
        menubar = tk.Menu(self, bg="#2d2d2d", fg="white", activebackground="#3c3c3c", activeforeground="white")
        self.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#3c3c3c", activeforeground="white")
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New File", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open File", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Open Folder", command=self.open_folder, accelerator="Ctrl+K Ctrl+O")
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As", command=self.save_file_as)
        file_menu.add_command(label="Close Tab", command=self.close_tab, accelerator="Ctrl+W")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        edit_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#3c3c3c", activeforeground="white")
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.text.edit_undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.text.edit_redo, accelerator="Ctrl+Y")
        edit_menu.add_command(label="Cut", command=lambda: self.text.event_generate("<<Cut>>"), accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=lambda: self.text.event_generate("<<Copy>>"), accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=lambda: self.text.event_generate("<<Paste>>"), accelerator="Ctrl+V")
        edit_menu.add_command(label="Find", command=self.find_text, accelerator="Ctrl+F")
        edit_menu.add_command(label="Replace", command=self.replace_text, accelerator="Ctrl+H")
        edit_menu.add_command(label="Find in Files", command=self.find_in_files, accelerator="Ctrl+Shift+F")
        
        run_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#3c3c3c", activeforeground="white")
        menubar.add_cascade(label="Run", menu=run_menu)
        run_menu.add_command(label="Run Code", command=self.run_code, accelerator="F5")
        run_menu.add_command(label="Debug", command=self.debug_code, accelerator="F10")
        run_menu.add_command(label="Start Live Server", command=self.start_live_server, accelerator="F6")
        
        settings_menu = tk.Menu(menubar, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#3c3c3c", activeforeground="white")
        menubar.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Open Settings", command=self.open_settings)

    def create_toolbar(self):
        toolbar = ttk.Frame(self, padding=5, relief="flat", style="Dark.TFrame")
        toolbar.pack(fill="x")
        
        for text, cmd in [(self.icons["new"] + " New", self.new_file), (self.icons["open"] + " Open", self.open_file),
                         (self.icons["save"] + " Save", self.save_file), (self.icons["run"] + " Run", self.run_code),
                         (self.icons["debug"] + " Debug", self.debug_code), (self.icons["search"] + " Find", self.find_in_files),
                         (self.icons["fold"] + " Fold", self.toggle_fold), (self.icons["server"] + " Live", self.start_live_server),
                         (self.icons["settings"] + " Settings", self.open_settings)]:
            btn = ttk.Button(toolbar, text=text, command=cmd, style="Dark.TButton")
            btn.pack(side="left", padx=2, pady=2)
        
        lang_menu = ttk.OptionMenu(toolbar, self.lang_var, "Python", *self.lang_configs.keys(), command=self.set_language, style="Dark.TMenubutton")
        lang_menu.pack(side="right", padx=5)

    def create_main_area(self):
        self.tab_bar = ttk.Notebook(self, style="Dark.TNotebook")
        self.tab_bar.pack(fill="x", padx=5, pady=2)
        self.tab_bar.bind("<<NotebookTabChanged>>", self.switch_tab)
        self.tab_bar.bind("<Button-3>", self.show_tab_context_menu)
        
        main_frame = ttk.Frame(self, style="Dark.TFrame")
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.line_numbers = tk.Text(main_frame, width=4, bg="#252526", fg="gray", font=("Consolas", 12), state="disabled", bd=0)
        self.line_numbers.pack(side="left", fill="y")
        self.line_numbers.bind("<Double-1>", self.toggle_fold_at_line)
        
        self.text = tk.Text(main_frame, wrap="none", undo=True, bg="#1e1e1e", fg="white", insertbackground="white",
                           font=("Consolas", 12), borderwidth=0, relief="flat")
        self.text.pack(side="left", fill="both", expand=True)
        
        v_scroll = ttk.Scrollbar(main_frame, orient="vertical", command=self.on_v_scroll, style="Dark.Vertical.TScrollbar")
        v_scroll.pack(side="right", fill="y")
        h_scroll = ttk.Scrollbar(main_frame, orient="horizontal", command=self.text.xview, style="Dark.Horizontal.TScrollbar")
        h_scroll.pack(side="bottom", fill="x")
        self.text.config(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        self.line_numbers.config(yscrollcommand=v_scroll.set)
        
        self.output_frame = ttk.LabelFrame(self, text="Output", padding=5, style="Dark.TLabelframe")
        self.output_frame.pack(fill="x", padx=5, pady=5)
        self.output = tk.Text(self.output_frame, height=12, bg="#1e1e1e", fg="lime", font=("Consolas", 10), state="disabled", bd=0)
        self.output.pack(fill="x")

    def create_status_bar(self):
        self.status_bar = ttk.Frame(self, relief="flat", padding=2, style="Dark.TFrame")
        self.status_bar.pack(fill="x", side="bottom")
        self.status_label = ttk.Label(self.status_bar, text="Ready", anchor="w", width=20, style="Dark.TLabel")
        self.status_label.pack(side="left", padx=5)
        self.lang_label = ttk.Label(self.status_bar, text="Python", anchor="w", width=10, style="Dark.TLabel")
        self.lang_label.pack(side="left")
        self.line_col_label = ttk.Label(self.status_bar, text="Ln 1, Col 1", anchor="e", style="Dark.TLabel")
        self.line_col_label.pack(side="right", padx=5)

    def configure_syntax_highlighting(self):
        self.text.tag_configure("keyword", foreground="#569cd6")
        self.text.tag_configure("number", foreground="#b5cea8")
        self.text.tag_configure("string", foreground="#ce9178")
        self.text.tag_configure("comment", foreground="#6a9955")
        self.text.tag_configure("builtin", foreground="#dcdcaa")
        self.text.tag_configure("breakpoint", background="#ff5555")
        self.text.tag_configure("search", background="yellow")
        self.text.tag_configure("folded", foreground="gray")

    # --- Keybindings ---
    def setup_keybindings(self):
        bindings = {
            "<Control-n>": lambda e: self.new_file(), "<Control-o>": lambda e: self.open_file(),
            "<Control-k><Control-o>": lambda e: self.open_folder(), "<Control-s>": lambda e: self.save_file(),
            "<Control-w>": lambda e: self.close_tab(), "<Control-z>": lambda e: self.text.edit_undo(),
            "<Control-y>": lambda e: self.text.edit_redo(), "<Control-f>": lambda e: self.find_text(),
            "<Control-h>": lambda e: self.replace_text(), "<Control-Shift-f>": lambda e: self.find_in_files(),
            "<F5>": lambda e: self.run_code(), "<F10>": lambda e: self.debug_code(),
            "<F6>": lambda e: self.start_live_server(), "<Control-d>": lambda e: self.toggle_breakpoint(),
            "<KeyRelease-exclam>": lambda e: self.check_html_emmet()
        }
        for key, cmd in bindings.items():
            self.bind_all(key, cmd)

    # --- Core Functionality ---
    def on_v_scroll(self, *args):
        self.text.yview(*args)
        self.update_line_numbers()

    def update_line_numbers(self):
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", "end")
        lines = self.text.get("1.0", "end-1c").count("\n") + 1
        for i in range(1, lines + 1):
            tag = "breakpoint" if f"{i}.0" in self.breakpoints else ""
            if f"{i}.0" in self.folded_blocks.get(self.filename, {}):
                self.line_numbers.insert("end", f"{i} ▶\n", tag)
            else:
                self.line_numbers.insert("end", f"{i}\n", tag)
        self.line_numbers.config(state="disabled")
        self.line_numbers.yview_moveto(self.text.yview()[0])

    def on_key_release(self, event=None):
        self.highlight_syntax()
        self.update_line_numbers()
        self.update_status()
        if time.time() - self.last_run_time > 1.0:
            self.live_preview()
        self.after(2000, self.auto_save)

    def highlight_syntax(self):
        data = self.text.get("1.0", "end-1c")
        for tag in ("keyword", "number", "string", "comment", "builtin"):
            self.text.tag_remove(tag, "1.0", "end")
        
        config = self.lang_configs.get(self.language, {})
        keywords = config.get("keywords", [])
        builtins = config.get("builtins", [])
        
        for word in keywords:
            start = "1.0"
            while True:
                pos = self.text.search(r'\m' + word + r'\M', start, stopindex="end", regexp=True)
                if not pos: break
                self.text.tag_add("keyword", pos, f"{pos}+{len(word)}c")
                start = f"{pos}+{len(word)}c"
        
        for word in builtins:
            start = "1.0"
            while True:
                pos = self.text.search(r'\m' + word + r'\M', start, stopindex="end", regexp=True)
                if not pos: break
                self.text.tag_add("builtin", pos, f"{pos}+{len(word)}c")
                start = f"{pos}+{len(word)}c"
        
        for match in re.finditer(r'\b\d+\.?\d*\b', data):
            self.text.tag_add("number", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        
        for match in re.finditer(r'".*?"|\'.*?\'', data):
            self.text.tag_add("string", f"1.0+{match.start()}c", f"1.0+{match.end()}c")
        
        comment_pat = config.get("comment", r'#.*$')
        for match in re.finditer(comment_pat, data, re.MULTILINE):
            self.text.tag_add("comment", f"1.0+{match.start()}c", f"1.0+{match.end()}c")

    def set_language(self, lang):
        self.language = lang.lower()
        self.files[self.filename]["language"] = self.language
        self.lang_label.config(text=lang.capitalize())
        self.update_file_extension()
        self.highlight_syntax()
        if self.language == "html" and self.server_thread:
            self.live_preview()

    def update_file_extension(self):
        if not self.filename or self.filename is None: return
        new_ext = self.lang_configs[self.language]["ext"]
        old_ext = os.path.splitext(self.filename)[1]
        if new_ext != old_ext:
            new_filename = os.path.splitext(self.filename)[0] + new_ext
            if os.path.exists(self.filename):
                os.rename(self.filename, new_filename)
            old_data = self.files.pop(self.filename)
            self.files[new_filename] = old_data
            self.filename = new_filename
            self.tab_bar.tab(self.tab_bar.select(), text=os.path.basename(new_filename))
            self.save_file()

    def new_file(self):
        self.files[None] = {"content": "", "modified": False, "language": self.lang_var.get().lower()}
        self.tab_bar.add(ttk.Frame(self.tab_bar), text="Untitled")
        self.tab_bar.select(self.tab_bar.index("end") - 1)
        self.switch_tab()
        
    def open_file(self):
        file = filedialog.askopenfilename(filetypes=[("All Files", "*.*")])
        if file:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()
            ext = os.path.splitext(file)[1]
            lang = next((l for l, c in self.lang_configs.items() if c["ext"] == ext), "python")
            self.files[file] = {"content": content, "modified": False, "language": lang}
            self.tab_bar.add(ttk.Frame(self.tab_bar), text=os.path.basename(file))
            self.tab_bar.select(self.tab_bar.index("end") - 1)
            self.switch_tab()

    def open_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.current_dir = folder
            os.chdir(folder)
            self.update_folder_explorer()

    def save_file(self):
        if not self.filename:
            self.save_file_as()
        else:
            with open(self.filename, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
            self.files[self.filename]["modified"] = False
            self.tab_bar.tab(self.tab_bar.select(), text=os.path.basename(self.filename))
            if self.language == "html" and self.server_thread:
                self.live_preview()

    def save_file_as(self):
        ext = self.lang_configs[self.language]["ext"]
        file = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[("All Files", "*.*")])
        if file:
            old_filename = self.filename
            self.filename = file
            self.save_file()
            if old_filename is None:
                self.files[file] = self.files.pop(None)
            elif old_filename in self.files:
                self.files[file] = self.files.pop(old_filename)
            self.tab_bar.tab(self.tab_bar.select(), text=os.path.basename(file))

    def auto_save(self):
        if self.filename and self.files[self.filename]["modified"]:
            self.save_file()

    def close_tab(self):
        if not self.tab_bar.tabs(): return
        current = self.tab_bar.select()
        fname = next(k for k, v in self.files.items() if self.tab_bar.tab(current, "text") in (os.path.basename(k) if k else "Untitled"))
        if self.files[fname]["modified"] and not self.confirm_discard(): return
        del self.files[fname]
        self.tab_bar.forget(current)
        if self.files: self.switch_tab()

    def switch_tab(self, event=None):
        if not self.tab_bar.tabs():
            self.filename = None
            self.text.delete("1.0", "end")
            return
        current = self.tab_bar.select()
        fname = next(k for k, v in self.files.items() if self.tab_bar.tab(current, "text") in (os.path.basename(k) if k else "Untitled"))
        self.filename = fname
        self.language = self.files[fname]["language"]
        self.lang_var.set(self.language.capitalize())
        self.text.delete("1.0", "end")
        content = self.files[fname]["content"]
        for start, end in self.folded_blocks.get(fname, {}).items():
            content = content[:int(start.split('.')[0])-1] + "[FOLDED]\n" + content[int(end.split('.')[0]):]
        self.text.insert("1.0", content)
        self.highlight_syntax()
        self.update_line_numbers()
        self.update_status()

    def show_tab_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg="#2d2d2d", fg="white", activebackground="#3c3c3c", activeforeground="white")
        menu.add_command(label="Close", command=self.close_tab)
        menu.add_command(label="Close All", command=self.close_all_tabs)
        menu.tk_popup(event.x_root, event.y_root)

    def close_all_tabs(self):
        for fname in list(self.files.keys()):
            if self.files[fname]["modified"] and not self.confirm_discard(): return
            del self.files[fname]
            self.tab_bar.forget(0)
        self.switch_tab()

    # --- Execution and Debugging ---
    def run_code(self):
        if not self.filename: self.save_file()
        if self.filename and self.language != "html":
            self.output.config(state="normal")
            self.output.delete("1.0", "end")
            Thread(target=self._execute_code).start()
        elif self.language == "html":
            self.start_live_server()

    def _execute_code(self):
        config = self.lang_configs.get(self.language, {})
        file_no_ext = os.path.splitext(self.filename)[0]
        cmd = [c.replace("{file}", self.filename).replace("{class}", os.path.basename(file_no_ext)).replace("{file_no_ext}", file_no_ext)
               for c in config.get("runner", [sys.executable, self.filename])]
        try:
            result = subprocess.check_output(" ".join(cmd), shell=True, stderr=subprocess.STDOUT, timeout=10, universal_newlines=True)
            self.after(0, lambda text=result: self.output.insert("end", text))
        except subprocess.CalledProcessError as e:
            self.after(0, lambda text=f"Error: {e.output}": self.output.insert("end", text))
        except subprocess.TimeoutExpired:
            self.after(0, lambda: self.output.insert("end", "Error: Execution timed out"))
        except Exception as e:
            self.after(0, lambda text=f"Unexpected error: {str(e)}": self.output.insert("end", text))
        finally:
            self.after(0, lambda: self.output.config(state="disabled"))
            self.last_run_time = time.time()

    def debug_code(self):
        if not self.filename: self.save_file()
        if self.filename and self.language != "html":
            self.output.config(state="normal")
            self.output.delete("1.0", "end")
            self.output.insert("end", "Debugging started...\n")
            Thread(target=self._debug_code).start()

    def _debug_code(self):
        bps = sorted(int(b.split('.')[0]) for b in self.breakpoints)
        self.after(0, lambda: self.output.insert("end", f"Breakpoints at lines: {bps}\n"))
        self.after(0, lambda: self.output.insert("end", "Debugging simulation complete.\n"))
        self.after(0, lambda: self.output.config(state="disabled"))

    # --- Live Server ---
    def start_live_server(self):
        if not self.filename: self.save_file()
        if self.language != "html" or not self.filename: return
        if self.server_thread and self.server_thread.is_alive():
            return
        
        os.chdir(self.current_dir)
        handler = http.server.SimpleHTTPRequestHandler
        
        class QuietHandler(handler):
            def log_message(self, format, *args):
                pass
        
        self.server = socketserver.TCPServer(("", self.server_port), QuietHandler)
        self.server_thread = Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        url = f"http://localhost:{self.server_port}/{os.path.basename(self.filename)}"
        webbrowser.open(url)
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        self.output.insert("end", f"Live server running at {url}\n")
        self.output.config(state="disabled")

    def live_preview(self):
        if self.language == "html" and self.server_thread and self.filename:
            self.save_file()

    # --- HTML Emmet (!) ---
    def check_html_emmet(self):
        if self.language != "html": return
        pos = self.text.index("insert")
        line_start = f"{pos.split('.')[0]}.0"
        line_content = self.text.get(line_start, f"{line_start} lineend")
        if line_content.strip() == "!":
            self.text.delete(line_start, f"{line_start} lineend")
            html_structure = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>
    
</body>
</html>"""
            self.text.insert(line_start, html_structure)
            self.highlight_syntax()

    # --- Code Folding ---
    def toggle_fold(self):
        line = self.text.index("insert").split(".")[0]
        self.toggle_fold_at_line(None, line)

    def toggle_fold_at_line(self, event, line=None):
        if not line:
            line = self.line_numbers.index("@%d,%d" % (event.x, event.y)).split(".")[0]
        start = f"{line}.0"
        content = self.text.get("1.0", "end-1c")
        lines = content.split("\n")
        indent = len(lines[int(line)-1]) - len(lines[int(line)-1].lstrip())
        
        if not indent: return
        
        end_line = int(line)
        for i in range(int(line), len(lines)):
            if lines[i].strip() and (len(lines[i]) - len(lines[i].lstrip())) <= indent:
                end_line = i
                break
            end_line = i + 1
        
        end = f"{end_line}.0"
        if self.filename not in self.folded_blocks:
            self.folded_blocks[self.filename] = {}
        
        if start in self.folded_blocks[self.filename]:
            del self.folded_blocks[self.filename][start]
        else:
            self.folded_blocks[self.filename][start] = end
            self.text.delete(start, end)
            self.text.insert(start, "[FOLDED]\n")
            self.text.tag_add("folded", start, f"{start}+7c")
        
        self.update_line_numbers()

    # --- Find in Files ---
    def find_in_files(self):
        term = simpledialog.askstring("Find in Files", "Enter search term:", parent=self)
        if not term: return
        results = []
        for root, _, files in os.walk(self.current_dir):
            for file in files:
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                        for i, line in enumerate(content.split("\n"), 1):
                            if term in line:
                                results.append(f"{path}:{i} - {line.strip()}")
                except:
                    continue
        
        self.output.config(state="normal")
        self.output.delete("1.0", "end")
        if results:
            self.output.insert("end", f"Found {len(results)} matches:\n" + "\n".join(results[:20]))
            if len(results) > 20:
                self.output.insert("end", f"\n...and {len(results)-20} more")
        else:
            self.output.insert("end", f"No matches found for '{term}'")
        self.output.config(state="disabled")

    # --- Settings Panel ---
    def open_settings(self):
        settings_win = tk.Toplevel(self, bg="#1e1e1e")
        settings_win.title("Settings")
        settings_win.geometry("600x400")
        
        notebook = ttk.Notebook(settings_win, style="Dark.TNotebook")
        notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        for category, options in self.settings.items():
            frame = ttk.Frame(notebook, style="Dark.TFrame")
            notebook.add(frame, text=category)
            canvas = tk.Canvas(frame, bg="#1e1e1e", highlightthickness=0)
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas, style="Dark.TFrame")
            
            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            for i, (setting, values) in enumerate(options.items()):
                ttk.Label(scrollable_frame, text=setting, style="Dark.TLabel").grid(row=i, column=0, padx=5, pady=2, sticky="w")
                var = tk.StringVar(value=values[0])
                menu = ttk.OptionMenu(scrollable_frame, var, values[0], *values, style="Dark.TMenubutton")
                menu.configure(style="Dark.TMenubutton")
                menu.grid(row=i, column=1, padx=5, pady=2, sticky="w")

    # --- Folder Explorer ---
    def update_folder_explorer(self):
        self.folder_tree.delete(*self.folder_tree.get_children())
        self.add_folder_to_tree("", self.current_dir)

    def add_folder_to_tree(self, parent, path):
        for item in os.listdir(path):
            full_path = os.path.join(path, item)
            icon = self.icons["folder"] if os.path.isdir(full_path) else self.icons["file"]
            node = self.folder_tree.insert(parent, "end", text=f"{icon} {item}", values=(full_path,))
            if os.path.isdir(full_path): self.add_folder_to_tree(node, full_path)

    def open_from_explorer(self, event):
        sel = self.folder_tree.selection()
        if not sel: return
        path = self.folder_tree.item(sel, "values")[0]
        if os.path.isfile(path): self.open_file_from_path(path)

    def open_file_from_path(self, path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        ext = os.path.splitext(path)[1]
        lang = next((l for l, c in self.lang_configs.items() if c["ext"] == ext), "python")
        self.files[path] = {"content": content, "modified": False, "language": lang}
        self.tab_bar.add(ttk.Frame(self.tab_bar), text=os.path.basename(path))
        self.tab_bar.select(self.tab_bar.index("end") - 1)
        self.switch_tab()

    # --- Search and Replace ---
    def find_text(self):
        term = simpledialog.askstring("Find", "Enter search term:", parent=self)
        if term:
            self.text.tag_remove("search", "1.0", "end")
            start = "1.0"
            while True:
                pos = self.text.search(term, start, stopindex="end")
                if not pos: break
                self.text.tag_add("search", pos, f"{pos}+{len(term)}c")
                start = f"{pos}+{len(term)}c"

    def replace_text(self):
        find_term = simpledialog.askstring("Replace", "Find what:", parent=self)
        if not find_term: return
        replace_term = simpledialog.askstring("Replace", "Replace with:", parent=self)
        if replace_term is None: return
        content = self.text.get("1.0", "end-1c")
        new_content = content.replace(find_term, replace_term)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", new_content)
        self.highlight_syntax()

    # --- Breakpoints ---
    def toggle_breakpoint(self):
        line = self.text.index("insert").split(".")[0] + ".0"
        if line in self.breakpoints: self.breakpoints.remove(line)
        else: self.breakpoints.add(line)
        self.update_line_numbers()

    # --- State Management ---
    def load_last_state(self):
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
            last_folder = config.get("last_folder")
            last_file = config.get("last_file")
            if last_folder and os.path.isdir(last_folder):
                self.current_dir = last_folder
                os.chdir(last_folder)
            if last_file and os.path.isfile(last_file):
                self.open_file_from_path(last_file)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save_last_state(self):
        config = {"last_folder": self.current_dir, "last_file": self.filename if self.filename else ""}
        with open(self.config_file, "w") as f:
            json.dump(config, f)

    # --- Utility Functions ---
    def update_status(self):
        line, col = self.text.index("insert").split(".")
        self.line_col_label.config(text=f"Ln {line}, Col {int(col) + 1}")
        self.status_label.config(text="Modified" if self.files.get(self.filename, {}).get("modified", False) else "Saved")
        self.lang_label.config(text=self.language.capitalize())

    def set_modified(self, value):
        if self.filename in self.files:
            self.files[self.filename]["modified"] = value
            self.files[self.filename]["content"] = self.text.get("1.0", "end-1c")
        self.update_status()

    def confirm_discard(self):
        return messagebox.askyesno("Unsaved Changes", "Discard unsaved changes?", parent=self)

    def on_closing(self):
        for fname, data in self.files.items():
            if data["modified"] and not self.confirm_discard(): return
        if self.server_thread:
            self.server.shutdown()
            self.server.server_close()
        self.save_last_state()
        self.destroy()

if __name__ == "__main__":
    app = VSCodelikeIDE()
    style = ttk.Style()
    style.theme_use("default")
    style.configure("Dark.TFrame", background="#1e1e1e")
    style.configure("Dark.TLabelframe", background="#1e1e1e", foreground="white")
    style.configure("Dark.TLabelframe.Label", background="#1e1e1e", foreground="white")
    style.configure("Dark.TButton", background="#3c3c3c", foreground="white", padding=4, borderwidth=1, relief="flat")
    style.map("Dark.TButton", background=[("active", "#569cd6")])
    style.configure("Dark.TMenubutton", background="#3c3c3c", foreground="white")
    style.map("Dark.TMenubutton", background=[("active", "#3c3c3c")])
    style.configure("Dark.TNotebook", background="#1e1e1e", foreground="white")
    style.configure("Dark.TNotebook.Tab", background="#2d2d2d", foreground="white", padding=[10, 4], borderwidth=1)
    style.map("Dark.TNotebook.Tab", background=[("selected", "#1e1e1e"), ("active", "#3c3c3c")])
    style.configure("Dark.Treeview", background="#1e1e1e", foreground="white", fieldbackground="#1e1e1e")
    style.map("Dark.Treeview", background=[("selected", "#569cd6")])
    style.configure("Dark.Vertical.TScrollbar", background="#3c3c3c", troughcolor="#1e1e1e")
    style.configure("Dark.Horizontal.TScrollbar", background="#3c3c3c", troughcolor="#1e1e1e")
    style.configure("Dark.TLabel", background="#1e1e1e", foreground="white")
    app.text.bind("<<Modified>>", lambda e: app.set_modified(True))
    app.text.bind("<KeyRelease>", app.on_key_release)
    app.mainloop()
