import sys
import os
import json
import logging
import shutil
import subprocess

if sys.stderr:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
log = logging.getLogger("bridge")

try:
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    desktop = os.path.join(exe_dir, "cnlb_fehler.txt")
    efh = logging.FileHandler(desktop, encoding="utf-8", mode="w")
    efh.setLevel(logging.ERROR)
    efh.setFormatter(logging.Formatter("%(asctime)s\n%(message)s", datefmt="%H:%M:%S"))
    log.addHandler(efh)
except Exception:
    pass

APP_NAME = "ClickNLoad Bridge"
APP_KEY = "ClickNLoadBridge"
PUBLISHER = "Lukas Sonderegger"
INSTALL_DIR = r"C:\Program Files\ClickNLoad Bridge"
UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\ClickNLoadBridge"

if getattr(sys, 'frozen', False):
    EXE_PATH = sys.executable
    EXE_DIR = os.path.dirname(EXE_PATH)
else:
    EXE_PATH = os.path.abspath(__file__)
    EXE_DIR = os.path.dirname(EXE_PATH)

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", EXE_DIR), "ClickNLoad Bridge")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
STARTUP_DIR = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs")
STARTUP_LNK = os.path.join(STARTUP_DIR, "ClickNLoad Bridge.lnk")


def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)


def config_exists():
    if not os.path.exists(CONFIG_PATH):
        return False
    try:
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        return all(k in cfg and cfg[k] for k in ("myjd_email", "myjd_password", "myjd_device_name"))
    except Exception:
        return False


def is_installed():
    if not os.path.exists(INSTALL_DIR):
        return False
    exe_in_inst = os.path.join(INSTALL_DIR, "ClickNLoadBridge.exe")
    return os.path.exists(exe_in_inst)


def handle_uninstall(from_gui=False):
    if from_gui:
        import tkinter as tk
        from tkinter import messagebox
        from tkinter.simpledialog import Dialog

        result = messagebox.askyesno(
            "Deinstallieren",
            "Soll Click'n'Load Bridge wirklich vollständig entfernt werden?\n\n"
            "1. Laufende Bridge beenden\n"
            "2. Autostart-Aufgabe entfernen\n"
            "3. Startmenü-Verknüpfung löschen\n"
            "4. Programmdateien löschen\n"
            "5. Konfiguration löschen\n"
            "6. Registry-Eintrag entfernen"
        )
        if not result:
            return

    log.info("Deinstalliere ...")

    # 1. Autostart entfernen
    subprocess.run(["schtasks", "/delete", "/tn", APP_NAME, "/f"], capture_output=True, timeout=10)
    startup_dir = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
    for name in ("ClickNLoad Bridge.lnk", "Click'n'Load Bridge.lnk"):
        path = os.path.join(startup_dir, name)
        if os.path.exists(path):
            os.remove(path)
    log.info("Autostart entfernt")

    # 1b. Startmenü-Verknüpfung entfernen
    try:
        if os.path.exists(STARTUP_LNK):
            os.remove(STARTUP_LNK)
            log.info("Startmenü-Verknüpfung entfernt")
    except Exception:
        pass

    # 2. Registry-Eintrag entfernen
    subprocess.run(["reg", "delete", f"HKLM\\{UNINSTALL_KEY}", "/f"], capture_output=True, timeout=10)
    log.info("Registry-Eintrag entfernt")

    # 3. Config-Ordner löschen
    appdata = os.environ.get("APPDATA", EXE_DIR)
    shutil.rmtree(os.path.join(appdata, "ClickNLoad Bridge"), ignore_errors=True)
    log.info("Konfiguration gelöscht")

    # 4. Program Files per PowerShell im Hintergrund löschen
    #    (muss ausgelagert werden, da wir die eigene EXE nicht selbst löschen können)
    ps_code = (
        f"Start-Sleep 2; "
        f"taskkill /f /im ClickNLoadBridge.exe 2>$null; "
        f"Start-Sleep 1; "
        f"Remove-Item -LiteralPath '{INSTALL_DIR}' -Recurse -Force -ErrorAction SilentlyContinue"
    )
    subprocess.Popen([
        "powershell", "-NoProfile", "-WindowStyle", "Hidden",
        "-Command", ps_code
    ])
    log.info("Deinstallation im Hintergrund gestartet")

    if from_gui:
        messagebox.showinfo("Deinstallation", "Click'n'Load Bridge wird entfernt.\nDas Fenster schließt sich.")
    log.info("Deinstallation abgeschlossen")
    sys.exit(0)


def install():
    log.info(f"Installiere nach {INSTALL_DIR} ...")
    os.makedirs(INSTALL_DIR, exist_ok=True)
    dest_exe = os.path.join(INSTALL_DIR, "ClickNLoadBridge.exe")
    try:
        shutil.copy2(EXE_PATH, dest_exe)
    except PermissionError:
        log.error("Keine Admin-Rechte, versuche Elevation...")
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas",
                "powershell", f"-NoProfile -Command Copy-Item '{EXE_PATH}' '{dest_exe}' -Force",
                None, 0
            )
            log.info("Elevierter Kopiervorgang gestartet")
        except Exception as e:
            log.error(f"Elevation fehlgeschlagen: {e}")
            return False

    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, UNINSTALL_KEY)
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "1.0.0")
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, INSTALL_DIR)
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, dest_exe)
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{dest_exe}" /uninstall')
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        log.info("Deinstallations-Eintrag erstellt")
    except Exception as e:
        log.warning(f"Registry-Eintrag fehlgeschlagen: {e}")

    return True


def setup_autostart():
    installed_exe = os.path.join(INSTALL_DIR, "ClickNLoadBridge.exe")
    target = installed_exe if is_installed() else EXE_PATH
    task_name = APP_NAME
    import getpass
    username = getpass.getuser()
    script = (
        f"$action = New-ScheduledTaskAction -Execute '{target}' -Argument '/start'; "
        f"$trigger = New-ScheduledTaskTrigger -AtLogOn; "
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries; "
        f"$principal = New-ScheduledTaskPrincipal -UserId '{username}' -RunLevel Highest -LogonType Interactive; "
        f"Register-ScheduledTask -TaskName '{task_name}' -Action $action "
        f"-Trigger $trigger -Principal $principal -Settings $settings -Force"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, timeout=15, check=True)
        log.info(f"Autostart-Aufgabe angelegt: {task_name}")
        return True
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e)
        log.warning(f"Autostart fehlgeschlagen: {err}")
        return False
    except Exception as e:
        log.warning(f"Autostart fehlgeschlagen: {e}")
        return False


def setup_startup_shortcut():
    installed_exe = os.path.join(INSTALL_DIR, "ClickNLoadBridge.exe")
    target = installed_exe if os.path.exists(installed_exe) else EXE_PATH
    script = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{STARTUP_LNK}'); "
        f"$s.TargetPath = '{target}'; "
        f"$s.Arguments = '/start'; "
        f"$s.WorkingDirectory = '{os.path.dirname(target)}'; "
        f"$s.Description = 'ClickNLoad Bridge'; "
        f"$s.Save()"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script],
                       capture_output=True, timeout=15, check=True)
        log.info(f"Startmenü-Verknüpfung angelegt: {STARTUP_LNK}")
        return True
    except Exception as e:
        log.warning(f"Startmenü-Verknüpfung fehlgeschlagen: {e}")
        return False


def show_setup_wizard(prefill=None):
    if not prefill:
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                prefill = json.load(f)
        except Exception:
            pass

    import tkinter as tk
    from tkinter import ttk, messagebox

    root = tk.Tk()
    root.title(f"{APP_NAME} - Einrichtung")
    root.resizable(False, False)
    root.minsize(620, 0)
    frame = ttk.Frame(root, padding=24)
    frame.grid()
    frame.grid_columnconfigure(1, weight=1)

    ttk.Label(frame, text=APP_NAME, font=("Segoe UI", 16, "bold")).grid(
        row=0, column=0, columnspan=6, pady=(0, 20)
    )

    field_defaults = {
        "MyJDownloader Email": "",
        "Passwort": "",
        "Gerätename": "JDownloader@SYNOLOGY",
        "Port": "9666",
    }

    if prefill:
        field_defaults["MyJDownloader Email"] = prefill.get("myjd_email", "")
        field_defaults["Passwort"] = prefill.get("myjd_password", "")
        field_defaults["Gerätename"] = prefill.get("myjd_device_name", field_defaults["Gerätename"])
        field_defaults["Port"] = str(prefill.get("cnl_port", 9666))

    entries = {}
    for idx, label in enumerate(["MyJDownloader Email", "Passwort", "Gerätename", "Port"]):
        row = idx + 1
        ttk.Label(frame, text=label, font=("Segoe UI", 10)).grid(
            row=row, column=0, sticky="w", pady=6
        )
        if label == "Gerätename":
            entry = ttk.Combobox(frame, font=("Segoe UI", 10), values=[field_defaults[label]])
            entry.configure(state="normal")
            def on_cb_select(*_):
                status_var.set("")
                if entry.get():
                    device_val = entry.get()
                    if device_val not in entry.cget("values"):
                        entry.configure(values=list(entry.cget("values")) + [device_val])
            entry.bind("<<ComboboxSelected>>", on_cb_select)
            entry.bind("<KeyRelease>", on_cb_select)
        else:
            entry = ttk.Entry(frame, font=("Segoe UI", 10))
        entry.grid(row=row, column=1, columnspan=5, sticky="ew", padx=(12, 8), pady=6)
        entry.insert(0, field_defaults[label])
        if label == "Passwort":
            entry.config(show="*")
        entries[label] = entry

    install_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        frame, text=f"In Program Files installieren ({INSTALL_DIR})",
        variable=install_var
    ).grid(row=5, column=0, columnspan=6, sticky="w", pady=(8, 0))

    autostart_var = tk.BooleanVar(value=not prefill or prefill.get("autostart_enabled", True))
    autostart_cb = ttk.Checkbutton(
        frame, text="Autostart (startet bei Windows-Login mit)",
        variable=autostart_var
    )
    autostart_cb.grid(row=6, column=0, sticky="w", pady=2, padx=(20, 0))

    startup_lnk_var = tk.BooleanVar(value=not prefill or prefill.get("startup_shortcut", True))
    startup_lnk_cb = ttk.Checkbutton(
        frame, text="Verkn\u00fcpfung im Startmen\u00fc anlegen",
        variable=startup_lnk_var
    )
    startup_lnk_cb.grid(row=7, column=0, columnspan=6, sticky="w", pady=2, padx=(20, 0))

    autostart_dl_var = tk.BooleanVar(value=prefill.get("autostart_downloads", True) if prefill else True)
    ttk.Checkbutton(
        frame, text="Downloads direkt starten (nach Linkgrabber)",
        variable=autostart_dl_var
    ).grid(row=8, column=0, columnspan=6, sticky="w", pady=2)

    toast_var = tk.BooleanVar(value=prefill.get("show_toast", True) if prefill else True)
    toast_frame = ttk.Frame(frame)
    toast_frame.grid(row=9, column=0, columnspan=6, sticky="w", pady=2)
    ttk.Checkbutton(
        toast_frame, text="Toast anzeigen bei erfolgreicher \u00dcbertragung",
        variable=toast_var
    ).pack(side="left")

    dur_default = prefill.get("toast_duration", 10) if prefill else 10
    dur_var = tk.StringVar(value=str(dur_default).zfill(2))
    dur_entry = ttk.Entry(toast_frame, textvariable=dur_var, width=3,
                          validate="key",
                          validatecommand=(root.register(lambda P: len(P) <= 2 and P.isdigit() or P == ""), "%P"))
    dur_entry.pack(side="left", padx=(6, 2))
    ttk.Label(toast_frame, text="Sekunden", font=("Segoe UI", 10)).pack(side="left")

    color_rows = []

    def make_color_row(row_idx, label_key, default_hex):
        var = tk.StringVar(value=prefill.get(label_key, default_hex) if prefill else default_hex)
        hex_var = tk.StringVar(value=var.get().lstrip("#").upper())
        color_rows.append((var, hex_var, label_key))

        row_frame = tk.Frame(frame)
        row_frame.grid(row=10 + row_idx, column=0, columnspan=6, sticky="w", pady=1, padx=(20, 0))

        tk.Label(row_frame, text=label_key + ":", font=("Segoe UI", 10),
                 anchor="w", width=12).pack(side="left")

        rb_frame = ttk.Frame(row_frame)
        rb_frame.pack(side="left")

        defaults = {
            "Schrift": "#DDF1F6", "Hintergrund": "#193D43", "Akzent": "#E6B002"
        }
        jd2 = defaults.get(label_key, "#DDF1F6")
        for rlabel, code in [
            ("JD2", jd2), ("Rot", "#FF0000"), ("Gr\u00fcn", "#00FF00"),
            ("Gelb", "#FFFF00"), ("Blau", "#0000FF"), ("Schwarz", "#000000"),
            ("Weiss", "#FFFFFF"),
        ]:
            tk.Radiobutton(rb_frame, text=rlabel, variable=var, value=code,
                           indicatoron=1, selectcolor="white",
                           command=lambda c=code, hv=hex_var: hv.set(c.lstrip("#").upper())
                           ).pack(side="left", padx=(0, 2))

        ttk.Label(rb_frame, text="HEX:").pack(side="left", padx=(4, 2))

        vcmd = root.register(lambda P: len(P) <= 6 and all(c in "0123456789abcdefABCDEF" for c in P))
        entry = ttk.Entry(rb_frame, textvariable=hex_var, width=8,
                          validate="key", validatecommand=(vcmd, "%P"))
        entry.pack(side="left", padx=(0, 4))

        def pick(parent=root, v=var, hv=hex_var):
            try:
                from tkinter import colorchooser
                c = colorchooser.askcolor(title=label_key, parent=parent, initialcolor=v.get())
                if c and c[1]:
                    v.set(c[1])
                    hv.set(c[1].lstrip("#").upper())
            except Exception:
                pass

        ttk.Button(rb_frame, text="\ud83c\udfa8", command=pick, width=3).pack(side="left")

        def trace_apply(*_, v=var, hv=hex_var):
            h = hv.get().strip().upper()
            if len(h) == 6 and all(c in "0123456789ABCDEF" for c in h):
                v.set(f"#{h}")

        def trace_color(*_, v=var, hv=hex_var):
            hv.set(v.get().lstrip("#").upper())

        hex_var.trace_add("write", trace_apply)
        var.trace_add("write", trace_color)

        return var, hex_var, entry

    text_var, text_hex, _ = make_color_row(0, "Schrift", "#DDF1F6")
    bg_var, bg_hex, _ = make_color_row(1, "Hintergrund", "#193D43")
    accent_var, accent_hex, accent_entry = make_color_row(2, "Akzent", "#E6B002")

    def on_toggle_toast(*_):
        state = "normal" if toast_var.get() else "disabled"
        for _, _, key in color_rows:
            for child in frame.winfo_children():
                try:
                    child.configure(state=state) if hasattr(child, "configure") else None
                except Exception:
                    pass

    toast_var.trace_add("write", on_toggle_toast)
    on_toggle_toast()

    # graue Trennlinie
    sep = ttk.Separator(frame, orient="horizontal")
    sep.grid(row=13, column=0, columnspan=6, sticky="ew", pady=6)

    console_var = tk.BooleanVar(value=prefill.get("show_console", False) if prefill else False)
    ttk.Checkbutton(
        frame, text="Konsole f\u00fcr Debugging anzeigen",
        variable=console_var
    ).grid(row=14, column=0, columnspan=6, sticky="w", pady=2)

    status_var = tk.StringVar()
    status_label = ttk.Label(frame, textvariable=status_var, font=("Segoe UI", 9))
    status_label.grid(row=15, column=0, columnspan=6, pady=4)

    def on_toggle_install(*_):
        if install_var.get():
            autostart_var.set(True)
            autostart_cb.config(state="normal")
            startup_lnk_var.set(True)
            startup_lnk_cb.config(state="normal")
        else:
            autostart_var.set(False)
            autostart_cb.config(state="disabled")
            startup_lnk_var.set(False)
            startup_lnk_cb.config(state="disabled")
        start_btn.config(text="Installieren und starten" if install_var.get() else "Starten")

    install_var.trace_add("write", on_toggle_install)

    def on_start():
        email = entries["MyJDownloader Email"].get().strip()
        pw = entries["Passwort"].get().strip()
        device = entries["Gerätename"].get().strip()
        port_str = entries["Port"].get().strip()

        if not email or not pw or not port_str:
            messagebox.showerror("Fehler", "Bitte E-Mail, Passwort und Port ausfüllen")
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("Fehler", "Port muss eine Zahl sein")
            return
        if port < 1 or port > 65535:
            messagebox.showerror("Fehler", "Port muss zwischen 1 und 65535 liegen")
            return

        status_var.set("Prüfe MyJDownloader-Login ...")
        root.update()
        try:
            import myjdapi
            api = myjdapi.Myjdapi()
            api.set_app_key("clicknload_bridge")
            api.connect(email, pw)
            devices = api.list_devices()
            names = [d.get("name", "?") for d in (devices or [])]
            cb = entries["Gerätename"]
            cb.configure(values=names)
            if not device and len(names) == 1:
                cb.delete(0, "end")
                cb.insert(0, names[0])
                device = names[0]
            elif not device and len(names) == 0:
                api.disconnect()
                messagebox.showerror("Fehler", "Kein Gerät in MyJDownloader gefunden.")
                status_var.set("")
                return
            elif not device:
                cb.delete(0, "end")
                cb.set("")
                status_var.set(f"Gerät auswählen: {', '.join(names)}")
                root.update()
                api.disconnect()
                return
            api.disconnect()
        except Exception as e:
            status_var.set("")
            err = str(e)
            if "EMAIL_INVALID" in err:
                messagebox.showerror("Fehler", f"MyJDownloader-Fehler:\nE-Mail Adresse nicht korrekt.\n\n{err}")
            elif "AUTH_FAILED" in err:
                messagebox.showerror("Fehler", f"MyJDownloader-Fehler:\nE-Mail Adresse oder Passwort nicht korrekt.\n\n{err}")
            else:
                messagebox.showerror("Fehler", f"MyJDownloader-Fehler:\n{err}")
            return

        config = {
            "myjd_email": email,
            "myjd_password": pw,
            "myjd_device_name": device,
            "cnl_port": port,
            "listen_host": "127.0.0.1",
            "startup_shortcut": startup_lnk_var.get(),
            "autostart_downloads": autostart_dl_var.get(),
            "show_toast": toast_var.get(),
            "show_console": console_var.get(),
            "text_color": text_var.get(),
            "bg_color": bg_var.get(),
            "toast_color": accent_var.get(),
            "toast_duration": int(dur_var.get()) if dur_var.get().isdigit() else 10
        }
        ensure_config_dir()
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)

        if install_var.get() and not is_admin():
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
            root.destroy()
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, "/install", None, 1)
            return

        if install_var.get():
            install()

        if autostart_var.get():
            setup_autostart()
        else:
            subprocess.run(["schtasks", "/delete", "/tn", APP_NAME, "/f"], capture_output=True, timeout=10)

        if startup_lnk_var.get():
            setup_startup_shortcut()

        subprocess.run(["taskkill", "/f", "/fi", f"PID ne {os.getpid()}", "/im", "ClickNLoadBridge.exe"], capture_output=True, timeout=10)
        status_var.set("Starte Bridge ...")
        root.update()
        root.after(200, lambda: start_bridge(root))

    btn_frame = ttk.Frame(frame)
    btn_frame.grid(row=16, column=0, columnspan=6, pady=(12, 0))

    start_btn = ttk.Button(btn_frame, text="Installieren und starten" if install_var.get() else "Starten", command=on_start, width=22)
    start_btn.pack(side="left", padx=6)
    on_toggle_install()

    ttk.Button(btn_frame, text="Deinstallieren", command=lambda: handle_uninstall(from_gui=True), width=22).pack(side="left", padx=6)

    root.eval("tk::PlaceWindow %s center" % root.winfo_pathname(root.winfo_id()))
    root.mainloop()


def start_bridge(root=None):
    if root:
        root.destroy()
    installed_exe = os.path.join(INSTALL_DIR, "ClickNLoadBridge.exe")
    if os.path.exists(installed_exe) and EXE_PATH != installed_exe:
        log.info(f"Starte installierte Version: {installed_exe}")
        subprocess.Popen([installed_exe, "/start"], cwd=INSTALL_DIR)
        return
    log.info("Starte Bridge ...")
    os.chdir(CONFIG_DIR)
    from main import main as bridge_main
    bridge_main()


def is_admin():
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def main():
    subprocess.run(["taskkill", "/f", "/fi", f"PID ne {os.getpid()}", "/im", "ClickNLoadBridge.exe"],
                   capture_output=True, timeout=10)

    if len(sys.argv) > 1:
        if sys.argv[1] == "/uninstall":
            handle_uninstall()
            return
        if sys.argv[1] == "/start":
            if config_exists():
                from gui import MainWindow
                win = MainWindow()
                win._start_bridge()
                win.run()
            else:
                log.info("Keine Config – starte GUI")
                from gui import MainWindow
                win = MainWindow()
                win.run()
            return

    if "/install" in sys.argv:
        if not is_admin():
            log.warning("Install angefordert, aber kein Admin")
            sys.exit(1)
        install()
        setup_autostart()
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            if cfg.get("startup_shortcut", True):
                setup_startup_shortcut()
        except Exception:
            pass
        from gui import MainWindow
        win = MainWindow()
        win._start_bridge()
        win.run()
        return

    if not is_admin():
        log.info("Keine Admin-Rechte – starte neu mit Elevation")
        import ctypes
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, "/install", None, 1
        )
        sys.exit(0)

    from gui import MainWindow
    win = MainWindow()
    if config_exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        log.info("Config gefunden")
        for key, val in cfg.items():
            if key in win.fields:
                win.fields[key].delete(0, "end")
                win.fields[key].insert(0, str(val))
        win.autostart_var.set(cfg.get("autostart_downloads", True))
        win.toast_var.set(cfg.get("show_toast", True))
        win.dur_var.set(str(cfg.get("toast_duration", 10)))
    win.run()
if __name__ == "__main__":
    main()
