import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import os
import sys
import webbrowser
import json
import time
import subprocess
import urllib.request
import urllib.error
import tempfile

log = logging.getLogger("cnl")

CURRENT_VERSION = "1.0.5.0"
VERSION_URL = "https://raw.githubusercontent.com/soendi/clicknload/master/version.json"
RELEASES_URL = "https://github.com/soendi/clicknload/releases"

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", "."), "ClickNLoad Bridge")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


class LogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text = text_widget
        self.setLevel(logging.DEBUG)

    def emit(self, record):
        msg = self.format(record) + "\n"
        self.text.after(0, lambda: self._write(msg))

    def _write(self, msg):
        self.text.configure(state="normal")
        self.text.insert("end", msg)
        self.text.see("end")
        self.text.configure(state="disabled")


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ClickNLoad Bridge")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)

        try:
            ico = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), "icon.ico"))
            self.root.iconphoto(True, ico)
        except Exception:
            pass

        self.tray_icon = None
        self.bridge_thread = None
        self.myjd = None
        self._tray_pystray = None

        self._build_menu()
        self._build_ui()
        self._build_statusbar()
        self._setup_logging()
        self._load_config()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_minimize)

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        datei = tk.Menu(menubar, tearoff=0)
        datei.add_command(label="Einstellungen", command=self._show_settings_tab)
        datei.add_separator()
        datei.add_command(label="Beenden", command=self._on_exit)
        menubar.add_cascade(label="Datei", menu=datei)
        hilfe = tk.Menu(menubar, tearoff=0)
        hilfe.add_command(label="Nach Updates suchen", command=self.check_for_update)
        hilfe.add_separator()
        hilfe.add_command(label="Über", command=self._show_about)
        menubar.add_cascade(label="Hilfe", menu=hilfe)
        self.root.config(menu=menubar)

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=6, pady=(6, 0))

        self.settings_frame = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.settings_frame, text="Einstellungen")
        self._build_settings()

        self.console_frame = ttk.Frame(self.notebook, padding=6)
        self.notebook.add(self.console_frame, text="Konsole")
        self._build_console()

    def _build_statusbar(self):
        self.status_frame = tk.Frame(self.root, bg="#2d2d2d", height=28)
        self.status_frame.pack(fill="x", side="bottom")
        self.status_frame.pack_propagate(False)
        self.status_dot = tk.Canvas(self.status_frame, width=14, height=14,
                                     bg="#2d2d2d", highlightthickness=0)
        self.status_dot.pack(side="left", padx=(8, 4), pady=6)
        self.dot_id = self.status_dot.create_oval(2, 2, 12, 12, fill="gray", outline="")
        self.status_label = tk.Label(self.status_frame, text="Gestoppt",
                                      fg="#aaaaaa", bg="#2d2d2d", font=("Segoe UI", 9))
        self.status_label.pack(side="left", padx=4)
        self.version_label = tk.Label(self.status_frame, text=f"v{CURRENT_VERSION}",
                                       fg="#666666", bg="#2d2d2d", font=("Segoe UI", 8))
        self.version_label.pack(side="right", padx=8)

    def _set_status(self, text, color="gray"):
        self.status_dot.itemconfig(self.dot_id, fill=color)
        self.status_label.config(text=text)

    def _build_console(self):
        self._setup_logging()
        self.console_text = tk.Text(self.console_frame, state="disabled",
                                     bg="#1e1e1e", fg="#d4d4d4",
                                     font=("Consolas", 10), wrap="word")
        scroll = tk.Scrollbar(self.console_frame, command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=scroll.set)
        self.console_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        handler = LogHandler(self.console_text)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                                datefmt="%H:%M:%S"))
        log.addHandler(handler)

    def _build_settings(self):
        main = self.settings_frame
        main.columnconfigure(1, weight=1)

        row = 0
        tk.Label(main, text="MyJDownloader", font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
        row += 1

        self.fields = {}
        labels = [("myjd_email", "E-Mail"), ("myjd_password", "Passwort"),
                   ("myjd_device_name", "Gerät"), ("cnl_port", "Port")]
        for key, label in labels:
            tk.Label(main, text=label).grid(row=row, column=0, sticky="w", pady=3)
            if key == "myjd_password":
                e = tk.Entry(main, show="*", width=40)
            elif key == "cnl_port":
                e = tk.Entry(main, width=10)
                tk.Label(main, text="(Name @ Synology)").grid(row=row, column=2, sticky="w", padx=6)
            else:
                e = tk.Entry(main, width=40)
            e.grid(row=row, column=1, sticky="ew", padx=6)
            self.fields[key] = e
            row += 1

        tk.Button(main, text="Verbinden", command=self._test_connection).grid(
            row=row, column=1, sticky="w", pady=4)
        self.conn_status = tk.Label(main, text="", fg="green")
        self.conn_status.grid(row=row, column=2, sticky="w")
        row += 1

        ttk.Separator(main, orient="horizontal").grid(row=row, column=0, columnspan=3,
                                                       sticky="ew", pady=8)
        row += 1

        tk.Label(main, text="Optionen", font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
        row += 1

        self.autostart_var = tk.BooleanVar(value=True)
        tk.Checkbutton(main, text="Downloads direkt starten",
                        variable=self.autostart_var).grid(row=row, column=0, columnspan=3,
                                                          sticky="w", pady=2)
        row += 1

        self.toast_var = tk.BooleanVar(value=True)
        tk.Checkbutton(main, text="Toast anzeigen",
                        variable=self.toast_var).grid(row=row, column=0, columnspan=3,
                                                      sticky="w", pady=2)
        row += 1

        tk.Label(main, text="Toast-Dauer (s):").grid(row=row, column=0, sticky="w")
        self.dur_var = tk.StringVar(value="10")
        tk.Spinbox(main, from_=1, to=60, textvariable=self.dur_var, width=5).grid(
            row=row, column=1, sticky="w", padx=6)
        row += 1

        self.console_start_var = tk.BooleanVar(value=False)
        tk.Checkbutton(main, text="Konsole beim Start anzeigen",
                        variable=self.console_start_var).grid(row=row, column=0, columnspan=3,
                                                              sticky="w", pady=2)
        row += 1

        ttk.Separator(main, orient="horizontal").grid(row=row, column=0, columnspan=3,
                                                       sticky="ew", pady=8)
        row += 1

        tk.Label(main, text="Bridge starten / stoppen", font=("Segoe UI", 11, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
        row += 1

        btn_frame = tk.Frame(main)
        btn_frame.grid(row=row, column=0, columnspan=3, pady=6)
        self.start_btn = tk.Button(btn_frame, text="Bridge starten",
                                    command=self._start_bridge, width=18)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = tk.Button(btn_frame, text="Bridge stoppen",
                                   command=self._stop_bridge, width=18, state="disabled")
        self.stop_btn.pack(side="left", padx=4)

        self._bridge_running = False

    def _show_settings_tab(self):
        self.notebook.select(0)

    def _show_about(self):
        messagebox.showinfo("Über ClickNLoad Bridge",
                             f"ClickNLoad Bridge v{CURRENT_VERSION}\n\n"
                             "Leitet CNL2/DLC-Links an MyJDownloader weiter.\n\n"
                             "© Lukas Sonderegger")

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                cfg = json.load(f)
            for key, entry in self.fields.items():
                val = cfg.get(key, "")
                entry.delete(0, "end")
                entry.insert(0, str(val))
            self.autostart_var.set(cfg.get("autostart_downloads", True))
            self.toast_var.set(cfg.get("show_toast", True))
            self.dur_var.set(str(cfg.get("toast_duration", 10)))
        except Exception:
            pass

    def _save_config(self):
        cfg = {key: e.get().strip() for key, e in self.fields.items()}
        cfg["autostart_downloads"] = self.autostart_var.get()
        cfg["show_toast"] = self.toast_var.get()
        cfg["show_console"] = self.console_start_var.get()
        cfg["toast_duration"] = int(self.dur_var.get())
        cfg["listen_host"] = "127.0.0.1"
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass
        return cfg

    def _test_connection(self):
        cfg = self._save_config()
        self.conn_status.config(text="Prüfe...", fg="orange")
        self.root.update()
        def check():
            try:
                import myjdapi
                api = myjdapi.Myjdapi()
                api.set_app_key("clicknload_bridge")
                api.connect(cfg["myjd_email"], cfg["myjd_password"])
                devices = api.list_devices()
                names = [d.get("name", "?") for d in (devices or [])]
                api.disconnect()
                if cfg["myjd_device_name"] in names:
                    self.root.after(0, lambda: self.conn_status.config(
                        text="Verbunden", fg="green"))
                elif len(names) == 1:
                    self.fields["myjd_device_name"].delete(0, "end")
                    self.fields["myjd_device_name"].insert(0, names[0])
                    self.root.after(0, lambda: self.conn_status.config(
                        text="Gerät gefüllt", fg="green"))
                else:
                    self.root.after(0, lambda: self.conn_status.config(
                        text=f"Geräte: {', '.join(names)}", fg="orange"))
            except Exception as e:
                err = str(e)
                if "EMAIL_INVALID" in err:
                    self.root.after(0, lambda: self.conn_status.config(
                        text="E-Mail falsch", fg="red"))
                elif "AUTH_FAILED" in err:
                    self.root.after(0, lambda: self.conn_status.config(
                        text="Login fehlgeschlagen", fg="red"))
                else:
                    self.root.after(0, lambda: self.conn_status.config(
                        text=f"Fehler: {err[:40]}", fg="red"))
        threading.Thread(target=check, daemon=True).start()

    def _start_bridge(self):
        cfg = self._save_config()
        from main import start_bridge_components
        self._bridge_running = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self._set_status("Starte...", "orange")
        def run():
            try:
                start_bridge_components(cfg)
                self.root.after(0, lambda: self._set_status("Aktiv", "green"))
            except Exception as e:
                log.error(f"Bridge-Fehler: {e}")
                self.root.after(0, lambda: self._set_status(f"Fehler: {e}", "red"))
        self.bridge_thread = threading.Thread(target=run, daemon=True)
        self.bridge_thread.start()

    def _stop_bridge(self):
        self._bridge_running = False
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self._set_status("Gestoppt", "gray")

    def _on_minimize(self, event=None):
        if event and hasattr(event, "widget") and event.widget == self.root:
            self.root.withdraw()
            self._show_tray()

    def _on_close(self):
        self._show_tray()
        self.root.withdraw()

    def _on_exit(self):
        try:
            if self._tray_pystray:
                self._tray_pystray.stop()
        except Exception:
            pass
        self.root.destroy()
        os._exit(0)

    def _show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        try:
            if self._tray_pystray:
                self._tray_pystray.stop()
                self._tray_pystray = None
        except Exception:
            pass

    def _show_tray(self):
        if self._tray_pystray:
            return
        try:
            import pystray
            from PIL import Image, ImageDraw
            from main import GREEN_TRAY_ICON, RED_TRAY_ICON
            icon_img = GREEN_TRAY_ICON if self._bridge_running else \
                Image.new("RGBA", (64, 64), (100, 100, 100, 255))
            menu = pystray.Menu(
                pystray.MenuItem("Fenster öffnen", lambda: self._show_window()),
                pystray.MenuItem("Beenden", self._on_exit),
            )
            icon = pystray.Icon("clicknload_bridge", icon_img,
                                "ClickNLoad Bridge", menu)
            self._tray_pystray = icon
            threading.Thread(target=icon.run, daemon=True).start()
        except Exception as e:
            log.warning(f"Systray Fehler: {e}")

    def check_for_update(self):
        threading.Thread(target=self._do_update_check, daemon=True).start()

    def _do_update_check(self):
        try:
            req = urllib.request.Request(VERSION_URL,
                                          headers={"User-Agent": "ClickNLoadBridge"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                remote = data.get("version", "")
                if remote and remote > CURRENT_VERSION:
                    self.root.after(0, lambda: self._show_update_dialog(remote))
                else:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Update", f"Kein Update verfügbar (v{CURRENT_VERSION})"))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Update-Fehler", str(e)))

    def _show_update_dialog(self, version):
        result = messagebox.askyesno("Update verfügbar",
                                      f"Neue Version v{version} verfügbar.\n"
                                      f"Aktuell: v{CURRENT_VERSION}\n\n"
                                      "Herunterladen und installieren?")
        if result:
            self._download_and_install(version)

    def _download_and_install(self, version):
        msi_url = f"https://github.com/soendi/clicknload/releases/download/v{version}/ClickNLoadBridge_Setup.msi"
        tmp = os.path.join(tempfile.gettempdir(), "ClickNLoadBridge_Setup.msi")
        log.info(f"Lade Update v{version} herunter...")
        try:
            urllib.request.urlretrieve(msi_url, tmp)
            log.info("Download abgeschlossen, starte Installation...")
            subprocess.Popen(["msiexec", "/i", tmp, "/qn"])
            self._on_exit()
        except Exception as e:
            log.error(f"Update-Fehler: {e}")
            messagebox.showerror("Fehler", f"Download fehlgeschlagen:\n{e}")

    def run(self):
        self.root.mainloop()
