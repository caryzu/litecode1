import gi
import os
import subprocess
import threading
import socket
import getpass

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, Gdk, Gio, GLib

CSS_DATA = """
window { background-color: #1e1e1e; }
.vs-toolbar { background-color: #2d2d30; border-bottom: 1px solid #3f3f46; padding: 4px; }
.vs-tool-btn { background: transparent; border: none; color: #f1f1f1; padding: 6px; border-radius: 3px; }
.vs-tool-btn:hover { background-color: #3e3e40; }

.vs-activity-bar { background-color: #333333; border-right: 1px solid #252526; }
.vs-act-btn { padding: 15px; border: none; background: transparent; color: #858585; }
.vs-act-btn.active { color: #007acc; border-left: 2px solid #007acc; background-color: #252526; }
.vs-sidebar { background-color: #252526; border-right: 1px solid #3f3f46; color: #cccccc; }

/* Дерево файлов */
.file-tree { background-color: #252526; color: #cccccc; font-size: 9pt; }

textview { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Monospace'; font-size: 11pt; }
textview text { background-color: #1e1e1e; }

.terminal-container { background-color: #0c0c0c; border-top: 1px solid #007acc; }
.terminal-view { font-family: 'Monospace'; font-size: 10pt; color: #ffffff; background-color: #0c0c0c; }

.vs-status-bar { background-color: #007acc; color: white; padding: 2px 5px; font-size: 9pt; }
.status-btn { background: transparent; border: none; color: white; padding: 2px 10px; font-size: 8pt; }
.status-btn:hover { background-color: #1f8ad2; }
"""

class LiteCode(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("LiteCode")
        self.set_default_size(1100, 700)
        
        self.current_path = None
        # Запускаем shell
        self.shell_process = subprocess.Popen(
            ["/bin/sh"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=0
        )

        provider = Gtk.CssProvider()
        provider.load_from_data(CSS_DATA.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_child(self.root)

        self.create_toolbar()

        self.main_hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.main_hbox.set_vexpand(True)
        self.root.append(self.main_hbox)

        self.create_activity_bar()
        self.create_sidebar()

        self.right_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.right_vbox.set_hexpand(True)
        self.main_hbox.append(self.right_vbox)

        self.create_editor_area()
        self.create_terminal_area()
        self.create_status_bar()

        threading.Thread(target=self.read_shell_output, daemon=True).start()
        
        # Контроллер клавиш
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_ctrl)

    def create_toolbar(self):
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        tb.add_css_class("vs-toolbar")
        btns = [("document-new-symbolic", self.on_new), 
                ("document-open-symbolic", self.on_open),
                ("document-save-symbolic", self.on_save),
                ("media-playback-start-symbolic", self.on_run)]
        for icon, func in btns:
            btn = Gtk.Button.new_from_icon_name(icon)
            btn.add_css_class("vs-tool-btn")
            btn.connect("clicked", func)
            tb.append(btn)
        self.root.append(tb)

    def create_activity_bar(self):
        self.ab = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.ab.add_css_class("vs-activity-bar")
        self.act_btns = {}
        items = [("system-file-manager-symbolic", "explorer"), 
                 ("edit-find-symbolic", "search"), 
                 ("emblem-system-symbolic", "settings")]
        for icon, name in items:
            btn = Gtk.Button.new_from_icon_name(icon)
            btn.add_css_class("vs-act-btn")
            btn.connect("clicked", self.on_side_switch, name)
            self.ab.append(btn)
            self.act_btns[name] = btn
        self.act_btns["explorer"].add_css_class("active")
        self.main_hbox.append(self.ab)

    def create_sidebar(self):
        self.side_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.side_box.add_css_class("vs-sidebar")
        self.side_box.set_size_request(240, -1)
        self.side_stack = Gtk.Stack()
        self.side_box.append(self.side_stack)
        
        # Explorer
        exp = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        exp.append(Gtk.Label(label="EXPLORER", xalign=0, margin_start=15, margin_top=10))
        self.file_store = Gtk.ListStore(str, str)
        tree = Gtk.TreeView(model=self.file_store)
        tree.add_css_class("file-tree")
        tree.set_headers_visible(False)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("", renderer, text=0)
        tree.append_column(column)
        tree.connect("row-activated", lambda t, p, c: self.load_file(t.get_model()[p][1]))
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        scroll.set_child(tree); exp.append(scroll)
        self.side_stack.add_named(exp, "explorer")
        
        # Search (Исправлено свойство margin)
        search = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        search.append(Gtk.Label(label="SEARCH", xalign=0, margin_start=15, margin_top=10))
        s_entry = Gtk.Entry(placeholder_text="Find...")
        s_entry.set_margin_start(10); s_entry.set_margin_end(10); s_entry.set_margin_top(10)
        search.append(s_entry)
        self.side_stack.add_named(search, "search")

        # Settings
        sett = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sett.append(Gtk.Label(label="SETTINGS", xalign=0, margin_start=15, margin_top=10))
        cb = Gtk.CheckButton(label="Auto Save")
        cb.set_margin_start(15); cb.set_margin_top(10)
        sett.append(cb)
        self.side_stack.add_named(sett, "settings")

        self.main_hbox.append(self.side_box)
        self.refresh_explorer()

    def create_editor_area(self):
        self.tab_label = Gtk.Label(label="welcome.py", xalign=0, margin_start=15)
        self.right_vbox.append(self.tab_label)
        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        self.text_view = Gtk.TextView(); self.buffer = self.text_view.get_buffer()
        scroll.set_child(self.text_view)
        self.right_vbox.append(scroll)

    def create_terminal_area(self):
        self.term_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.term_container.add_css_class("terminal-container")
        self.term_container.set_size_request(-1, 200)
        self.term_container.set_visible(False)

        scroll = Gtk.ScrolledWindow(); scroll.set_vexpand(True)
        self.term_view = Gtk.TextView()
        self.term_view.add_css_class("terminal-view")
        self.term_buffer = self.term_view.get_buffer()
        
        term_ctrl = Gtk.EventControllerKey()
        term_ctrl.connect("key-pressed", self.on_term_key_pressed)
        self.term_view.add_controller(term_ctrl)

        scroll.set_child(self.term_view)
        self.term_container.append(scroll)
        self.right_vbox.append(self.term_container)

    def create_status_bar(self):
        sb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        sb.add_css_class("vs-status-bar")
        self.term_toggle = Gtk.Button(label="Terminal")
        self.term_toggle.add_css_class("status-btn")
        self.term_toggle.connect("clicked", lambda _: self.toggle_terminal())
        sb.append(self.term_toggle)
        self.root.append(sb)

    def toggle_terminal(self):
        new_state = not self.term_container.get_visible()
        self.term_container.set_visible(new_state)
        if new_state: self.term_view.grab_focus()

    def on_side_switch(self, btn, name):
        self.side_stack.set_visible_child_name(name)
        for b in self.act_btns.values(): b.remove_css_class("active")
        btn.add_css_class("active")

    def read_shell_output(self):
        while True:
            line = self.shell_process.stdout.readline()
            if line: GLib.idle_add(self.update_term, line)

    def update_term(self, text):
        self.term_buffer.insert(self.term_buffer.get_end_iter(), text)

    def on_term_key_pressed(self, ctrl, keyval, keycode, state):
        if keyval == Gdk.KEY_Return:
            line_count = self.term_buffer.get_line_count()
            start_iter = self.term_buffer.get_iter_at_line(line_count - 1)
            line_text = self.term_buffer.get_text(start_iter, self.term_buffer.get_end_iter(), True)
            clean_cmd = line_text.strip().split('\n')[-1] # Берем только последнюю строку
            self.shell_process.stdin.write(clean_cmd + "\n")
            self.shell_process.stdin.flush()
            return False
        return False

    def on_key_pressed(self, ctrl, keyval, keycode, state):
        if (state & Gdk.ModifierType.CONTROL_MASK):
            if keyval == Gdk.KEY_s: self.on_save(); return True
            if keyval == Gdk.KEY_o: self.on_open(); return True
            if keyval == Gdk.KEY_n: self.on_new(); return True
            if keyval == Gdk.KEY_quoteleft or keyval == 96: # Ctrl + ~
                self.toggle_terminal(); return True
        return False

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f: self.buffer.set_text(f.read())
            self.current_path = path
            self.tab_label.set_text(os.path.basename(path))
        except: pass

    def on_save(self, *args):
        if not self.current_path:
            d = Gtk.FileDialog(); d.save(self, None, self.on_save_finish)
        else: self.write_file(self.current_path)

    def on_save_finish(self, d, res):
        try:
            f = d.save_finish(res)
            if f: self.write_file(f.get_path())
        except: pass

    def write_file(self, path):
        start, end = self.buffer.get_bounds()
        with open(path, 'w', encoding='utf-8') as f: f.write(self.buffer.get_text(start, end, True))
        self.current_path = path
        self.refresh_explorer()

    def on_open(self, *args):
        d = Gtk.FileDialog(); d.open(self, None, self.on_open_done)

    def on_open_done(self, d, res):
        try:
            f = d.open_finish(res)
            if f: self.load_file(f.get_path())
        except: pass
    
    def on_new(self, *args):
        self.buffer.set_text(""); self.current_path = None; self.tab_label.set_text("untitled.py")

    def on_run(self, *args):
        if self.current_path:
            self.toggle_terminal()
            self.shell_process.stdin.write(f"python3 {self.current_path}\n")
            self.shell_process.stdin.flush()

    def refresh_explorer(self):
        self.file_store.clear()
        try:
            for f in sorted(os.listdir('.')):
                if os.path.isfile(f): self.file_store.append([f, os.path.abspath(f)])
        except: pass

def on_activate(app):
    win = LiteCode(application=app); win.present()

app = Gtk.Application(application_id="com.litecode.fixed")
app.connect('activate', on_activate)
app.run(None)
