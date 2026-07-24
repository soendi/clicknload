import tkinter as tk
from tkinter import ttk, messagebox
import threading
import logging
import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error
import tempfile

log = logging.getLogger("cnl")

CURRENT_VERSION = "1.0.16.1"
RELEASES_API = "https://api.github.com/repos/soendi/clicknload/releases?per_page=10"

REGISTRY_KEY = r"Software\ClickNLoadBridge"


def registry_read(name, default=""):
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, name)
            return val
        except FileNotFoundError:
            return default
        finally:
            winreg.CloseKey(key)
    except OSError:
        return default


def registry_write(name, value):
    try:
        import winreg
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REGISTRY_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(value))
        winreg.CloseKey(key)
    except Exception as e:
        log.warning(f"Registry-Schreibfehler ({name}): {e}")


def registry_delete_all():
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REGISTRY_KEY)
    except OSError:
        pass


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
        self._load_config()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Unmap>", self._on_minimize)

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        datei = tk.Menu(menubar, tearoff=0)
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
        labels = [("myjd_email", "E-Mail"), ("myjd_password", "Passwort")]
        for key, label in labels:
            tk.Label(main, text=label).grid(row=row, column=0, sticky="w", pady=3)
            e = tk.Entry(main, show="*" if key == "myjd_password" else None, width=40)
            e.grid(row=row, column=1, sticky="ew", padx=6)
            self.fields[key] = e
            row += 1

        self.fields["myjd_email"].bind("<FocusOut>", lambda e: self._on_creds_changed())
        self.fields["myjd_password"].bind("<FocusOut>", lambda e: self._on_creds_changed())
        self.fields["myjd_email"].bind("<Return>", lambda e: self._on_creds_changed())
        self.fields["myjd_password"].bind("<Return>", lambda e: self._on_creds_changed())

        tk.Label(main, text="Gerät").grid(row=row, column=0, sticky="w", pady=3)
        self.device_combo = ttk.Combobox(main, font=("Segoe UI", 10), state="readonly", width=38)
        self.device_combo.grid(row=row, column=1, sticky="ew", padx=6)
        self.conn_status = tk.Label(main, text="", fg="green")
        self.conn_status.grid(row=row, column=2, sticky="w")
        row += 1

        tk.Label(main, text="Port").grid(row=row, column=0, sticky="w", pady=3)
        self.port_field = tk.Entry(main, width=10)
        self.port_field.grid(row=row, column=1, sticky="w", padx=6)
        row += 1

        tk.Button(main, text="Verbinden", command=self._test_connection).grid(
            row=row, column=1, sticky="w", pady=4)
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

        from run import is_autostart_enabled, setup_autostart, remove_autostart
        self.win_autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        self._setup_autostart = setup_autostart
        self._remove_autostart = remove_autostart
        tk.Checkbutton(main, text="Mit Windows starten",
                        variable=self.win_autostart_var,
                        command=self._on_toggle_win_autostart).grid(
                            row=row, column=0, columnspan=3, sticky="w", pady=2)
        row += 1

        toast_row = tk.Frame(main)
        toast_row.grid(row=row, column=0, columnspan=3, sticky="w", pady=2)
        self.toast_var = tk.BooleanVar(value=True)
        tk.Checkbutton(toast_row, text="Toast anzeigen",
                        variable=self.toast_var).pack(side="left")
        tk.Label(toast_row, text="Dauer:").pack(side="left", padx=(12, 2))
        self.dur_var = tk.StringVar(value="10")
        tk.Spinbox(toast_row, from_=1, to=60, textvariable=self.dur_var, width=4).pack(side="left")
        tk.Label(toast_row, text="s").pack(side="left")
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

    def _on_creds_changed(self):
        email = self.fields["myjd_email"].get().strip()
        pw = self.fields["myjd_password"].get().strip()
        if not email or not pw:
            return
        self.conn_status.config(text="Prüfe...", fg="orange")
        self.root.update()
        threading.Thread(target=self._validate_and_fetch_devices, args=(email, pw), daemon=True).start()

    def _on_toggle_win_autostart(self):
        if self.win_autostart_var.get():
            ok = self._setup_autostart()
            if ok:
                log.info("Mit Windows starten: aktiviert")
            else:
                log.warning("Autostart konnte nicht eingerichtet werden")
        else:
            ok = self._remove_autostart()
            if ok:
                log.info("Mit Windows starten: deaktiviert")
            else:
                log.warning("Autostart konnte nicht entfernt werden")

    def _validate_and_fetch_devices(self, email, pw):
        try:
            import myjdapi
            api = myjdapi.Myjdapi()
            api.set_app_key("clicknload_bridge")
            api.connect(email, pw)
            devices = api.list_devices()
            names = [d.get("name", "?") for d in (devices or [])]
            api.disconnect()
            self.root.after(0, lambda: self._populate_devices(names))
        except Exception as e:
            err = str(e)
            if "EMAIL_INVALID" in err:
                msg = "E-Mail Adresse nicht korrekt"
            elif "AUTH_FAILED" in err:
                msg = "Login fehlgeschlagen"
            else:
                msg = err[:50]
            self.root.after(0, lambda: self.conn_status.config(text=msg, fg="red"))
            self.root.after(0, lambda: self.device_combo.configure(values=[]))

    def _populate_devices(self, names):
        self.device_combo.configure(values=names)
        if len(names) == 1:
            self.device_combo.set(names[0])
            self.conn_status.config(text="Verbunden", fg="green")
        elif len(names) == 0:
            self.conn_status.config(text="Kein Gerät gefunden", fg="red")
        else:
            current = self.device_combo.get()
            if current in names:
                self.device_combo.set(current)
            self.conn_status.config(text=f"{len(names)} Geräte verfügbar", fg="green")

    def _show_about(self):
        messagebox.showinfo("Über ClickNLoad Bridge",
                             f"ClickNLoad Bridge v{CURRENT_VERSION}\n\n"
                             "Leitet CNL2/DLC-Links an MyJDownloader weiter.\n\n"
                             "© Lukas Sonderegger")

    def _load_config(self):
        try:
            email = registry_read("myjd_email")
            pw = registry_read("myjd_password")
            device = registry_read("myjd_device_name")
            port = registry_read("cnl_port", "9666")

            if email:
                self.fields["myjd_email"].delete(0, "end")
                self.fields["myjd_email"].insert(0, email)
            if pw:
                self.fields["myjd_password"].delete(0, "end")
                self.fields["myjd_password"].insert(0, pw)
            if device:
                self.device_combo.set(device)
            if port:
                self.port_field.delete(0, "end")
                self.port_field.insert(0, port)

            self.autostart_var.set(registry_read("autostart_downloads", "1") == "1")
            self.toast_var.set(registry_read("show_toast", "1") == "1")
            self.dur_var.set(registry_read("toast_duration", "10"))
            self.console_start_var.set(registry_read("show_console", "0") == "1")
        except Exception as e:
            log.warning(f"Config-Laden fehlgeschlagen: {e}")

    def _save_config(self):
        email = self.fields["myjd_email"].get().strip()
        pw = self.fields["myjd_password"].get().strip()
        device = self.device_combo.get().strip()
        port = self.port_field.get().strip()

        registry_write("myjd_email", email)
        registry_write("myjd_password", pw)
        registry_write("myjd_device_name", device)
        registry_write("cnl_port", port)
        registry_write("autostart_downloads", "1" if self.autostart_var.get() else "0")
        registry_write("show_toast", "1" if self.toast_var.get() else "0")
        registry_write("show_console", "1" if self.console_start_var.get() else "0")
        registry_write("toast_duration", self.dur_var.get())

        return {
            "myjd_email": email,
            "myjd_password": pw,
            "myjd_device_name": device,
            "cnl_port": int(port) if port.isdigit() else 9666,
            "listen_host": "127.0.0.1",
            "autostart_downloads": self.autostart_var.get(),
            "show_toast": self.toast_var.get(),
            "show_console": self.console_start_var.get(),
            "toast_duration": int(self.dur_var.get()) if self.dur_var.get().isdigit() else 10,
        }

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
                    self.device_combo.configure(values=names)
                    self.device_combo.set(names[0])
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
                server = start_bridge_components(cfg)
                self.root.after(0, lambda: self._set_status("Aktiv", "green"))
                server.serve_forever()
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
            from main import GREEN_TRAY_ICON
            icon_img = GREEN_TRAY_ICON if self._bridge_running else \
                Image.new("RGBA", (64, 64), (100, 100, 100, 255))

            def on_device_selected(icon, item):
                device_name = str(item)
                registry_write("myjd_device_name", device_name)
                self.root.after(0, lambda: self.device_combo.set(device_name))

            devices = list(self.device_combo.cget("values") or [])
            current_device = self.device_combo.get()

            menu_items = [
                pystray.MenuItem(f"ClickNLoad Bridge v{CURRENT_VERSION}", None, enabled=False),
                pystray.Menu.SEPARATOR,
            ]

            if len(devices) > 1:
                device_menu = pystray.Menu(
                    *[pystray.MenuItem(d, on_device_selected,
                                       checked=lambda item, d=d: str(item) == current_device)
                      for d in devices]
                )
                menu_items.append(pystray.MenuItem("Gerät", device_menu))
            elif len(devices) == 1:
                menu_items.append(pystray.MenuItem(f"Gerät: {devices[0]}", None, enabled=False))

            menu_items.extend([
                pystray.MenuItem("Nach Updates suchen", lambda: self.check_for_update()),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Beenden", self._on_exit),
            ])

            menu = pystray.Menu(*menu_items)
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
            req = urllib.request.Request(RELEASES_API,
                                          headers={"User-Agent": "ClickNLoadBridge"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                releases = json.loads(resp.read().decode())

            for rel in releases:
                if rel.get("draft") or rel.get("prerelease"):
                    continue
                tag = rel.get("tag_name", "")
                if not tag.startswith("v"):
                    continue
                remote = tag[1:]
                if remote > CURRENT_VERSION:
                    exe_asset = None
                    for asset in rel.get("assets", []):
                        if asset["name"].endswith(".exe"):
                            exe_asset = asset
                            break
                    if exe_asset:
                        self._remote_exe_url = exe_asset["browser_download_url"]
                        self._remote_version = remote
                        self.root.after(0, lambda: self._show_update_dialog(remote))
                    else:
                        self.root.after(0, lambda v=remote: messagebox.showinfo(
                            "Update", f"Neue Version v{v} verfügbar,\n"
                                      f"aber der Build ist noch nicht abgeschlossen.\n"
                                      f"Bitte später erneut versuchen."))
                    return

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
        exe_url = getattr(self, '_remote_exe_url',
                          f"https://github.com/soendi/clicknload/releases/download/v{version}/ClickNLoadBridge_Setup.exe")
        tmp = os.path.join(tempfile.gettempdir(), "ClickNLoadBridge_Setup.exe")

        win = tk.Toplevel(self.root)
        win.title("Update")
        win.geometry("420x150")
        win.resizable(False, False)
        win.configure(bg="#193D43")
        win.attributes("-topmost", True)
        try:
            ico = tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), "icon.ico"))
            win.iconphoto(True, ico)
        except Exception:
            pass

        tk.Label(win, text=f"Update v{version} wird heruntergeladen...",
                 bg="#193D43", fg="#DDF1F6", font=("Segoe UI", 11, "bold")).pack(pady=(18, 8), padx=16, anchor="w")
        tk.Label(win, text="Bitte warten...", bg="#193D43", fg="#aaaaaa",
                 font=("Segoe UI", 9)).pack(padx=16, anchor="w")

        progress = ttk.Progressbar(win, length=380, mode="determinate")
        progress.pack(padx=16, pady=(4, 0))
        status_label = tk.Label(win, text="0 %", bg="#193D43", fg="#E6B002",
                                 font=("Segoe UI", 9))
        status_label.pack(padx=16, anchor="w")

        def do_download():
            try:
                req = urllib.request.Request(exe_url, headers={"User-Agent": "ClickNLoadBridge"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    chunk_size = 256 * 1024
                    with open(tmp, "wb") as f:
                        while True:
                            chunk = resp.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                pct = int(downloaded * 100 / total)
                                self.root.after(0, lambda p=pct: (
                                    progress.configure(value=p),
                                    status_label.config(text=f"{p}%  ({downloaded // 1024} KB / {total // 1024} KB)")
                                ))
                            else:
                                self.root.after(0, lambda d=downloaded: (
                                    status_label.config(text=f"{d // 1024} KB heruntergeladen")
                                ))
                self.root.after(0, lambda: self._launch_installer(tmp, version))
            except Exception as e:
                self.root.after(0, lambda: (
                    win.destroy(),
                    messagebox.showerror("Fehler", f"Download fehlgeschlagen:\n{e}")
                ))

        threading.Thread(target=do_download, daemon=True).start()

    def _launch_installer(self, path, version):
        log.info(f"Starte Installation v{version}...")
        subprocess.Popen([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"])
        self.root.after(1000, self._on_exit)

    def run(self):
        self.root.mainloop()
