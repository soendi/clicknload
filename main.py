import http.server
import json
import base64
import os
import sys
import socketserver
import logging
import signal
import threading
import urllib.parse
import re
from myjd import MyJDownloader
from dlc import start_dlc_watcher

if sys.stderr:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )
for h in logging.root.handlers[:]:
    if isinstance(h, logging.StreamHandler):
        logging.root.removeHandler(h)

log = logging.getLogger("cnl")
log.setLevel(logging.DEBUG)

CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__))), "ClickNLoad Bridge")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

try:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    fh = logging.FileHandler(os.path.join(CONFIG_DIR, "bridge.log"), encoding="utf-8", mode="a")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
    log.addHandler(fh)
    fh.acquire()
    try:
        fh.stream.write("=== Logging gestartet ===\n")
    finally:
        fh.release()
except Exception:
    pass

try:
    exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    err_log = os.path.join(exe_dir, "cnlb_fehler.txt")
    efh = logging.FileHandler(err_log, encoding="utf-8", mode="w")
    efh.setLevel(logging.ERROR)
    efh.setFormatter(logging.Formatter("%(asctime)s\n%(message)s", datefmt="%H:%M:%S"))
    log.addHandler(efh)
except Exception:
    pass

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

config = load_config()
autostart_downloads = config.get("autostart_downloads", True)
show_toast = config.get("show_toast", True)
show_console = config.get("show_console", False)
toast_duration = config.get("toast_duration", 10)
text_color = config.get("text_color", "#DDF1F6")
bg_color = config.get("bg_color", "#193D43")
toast_color = config.get("toast_color", "#E6B002")
myjd = MyJDownloader(
    email=config["myjd_email"],
    password=config["myjd_password"],
    device_name=config["myjd_device_name"]
)


def toggle_console(show):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        hwnd = kernel32.GetConsoleWindow()
        if show:
            if not hwnd:
                kernel32.AllocConsole()
                hwnd = kernel32.GetConsoleWindow()
                sys.stdout = open("CONOUT$", "w", encoding="utf-8")
                sys.stderr = open("CONOUT$", "w", encoding="utf-8")
            user32.ShowWindow(hwnd, 5)
            sys.stdout = open("CONOUT$", "w", encoding="utf-8")
            sys.stderr = open("CONOUT$", "w", encoding="utf-8")
        else:
            if hwnd:
                user32.ShowWindow(hwnd, 0)
                sys.stdout = open(os.devnull, "w", encoding="utf-8")
                sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass


def save_config():
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)

_tray_icon = None
_tray_pystray = None

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_SYSTRAY = True
except ImportError:
    HAS_SYSTRAY = False

_ARROW_PNG_B64 = None


_cnl_rsa_key = None
_cnl_rsa_pubkey_b64 = None

def _ensure_rsa_key():
    global _cnl_rsa_key, _cnl_rsa_pubkey_b64
    if _cnl_rsa_key is None:
        from Crypto.PublicKey import RSA as RSAKey
        _cnl_rsa_key = RSAKey.generate(1024)
        _cnl_rsa_pubkey_b64 = base64.b64encode(_cnl_rsa_key.publickey().export_key("DER")).decode()


_active_toasts = []

def notify(title, message, duration=None, package_name=None, urls_count=0, autostart=False):
    if not show_toast:
        return
    if duration is None:
        duration = toast_duration
    import threading
    threading.Thread(target=show_popup, args=(title, message),
                     kwargs={"duration": duration, "package_name": package_name,
                             "urls_count": urls_count, "autostart": autostart},
                     daemon=False).start()


def show_popup(title, message, duration=None, package_name=None, urls_count=0, autostart=False):
    if duration is None:
        duration = toast_duration
    import tkinter as tk
    import threading

    popup_root = tk.Tk()
    popup_root.overrideredirect(True)
    popup_root.attributes("-topmost", True)
    popup_root.configure(bg="#2d2d2d")

    screen_w = popup_root.winfo_screenwidth()
    screen_h = popup_root.winfo_screenheight()

    try:
        import ctypes
        from ctypes import wintypes
        SPI_GETWORKAREA = 0x0030
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        work_bottom = rect.bottom
        taskbar_h = screen_h - work_bottom
    except Exception:
        taskbar_h = 40

    popup_w = 380
    popup_h = 160
    x = screen_w - popup_w - 10

    global _active_toasts
    _active_toasts.append(popup_root)
    idx = len(_active_toasts) - 1
    y = screen_h - taskbar_h - popup_h - 10 - idx * (popup_h + 10)
    if y < 0:
        y = 10

    popup_root.geometry(f"{popup_w}x{popup_h}+{x}+{y}")
    popup_root.resizable(False, False)
    popup_root.attributes("-alpha", 0)

    colors = {
        "bg": bg_color,
        "fg": text_color,
        "accent": toast_color,
        "title_bg": bg_color,
        "text": "#cccccc",
    }

    title_frame = tk.Frame(popup_root, bg=colors["title_bg"], height=32)
    title_frame.pack(fill="x")
    title_frame.pack_propagate(False)

    tk.Label(title_frame, text="ClickNLoad Bridge", bg=colors["title_bg"],
             fg=colors["accent"], font=("Segoe UI", 10, "bold"), anchor="w",
             padx=12).pack(side="left", fill="both", expand=True)

    body = tk.Frame(popup_root, bg=colors["bg"])
    body.pack(fill="both", expand=True, padx=8, pady=(8, 8))

    if package_name and not message and not urls_count:
        display = package_name if len(package_name) <= 85 else package_name[:80] + " ..."
        tk.Label(body, text=display, bg=colors["bg"], fg=colors["fg"],
                 font=("Segoe UI", 11, "bold"), wraplength=350, anchor="w",
                 justify="left").pack(fill="x", pady=(0, 2))

    if urls_count:
        tk.Label(body, text=f"{urls_count} Link(s) \u00fcbertragen",
                 bg=colors["bg"], fg=colors["text"],
                 font=("Segoe UI", 10)).pack(fill="x", pady=(0, 2))

    is_general = bool(message and not package_name and not urls_count)

    for child in body.winfo_children():
        child.destroy()

    if is_general:
        center_frame = tk.Frame(body, bg=colors["bg"])
        center_frame.place(relx=0.5, rely=0.5, anchor="center")
        lines = message.split("\n")
        for i, line in enumerate(lines):
            is_first = i == 0
            fs = ("Segoe UI", 13, "bold") if is_first else ("Segoe UI", 10)
            fg = colors["fg"] if is_first else colors.get("text", "#cccccc")
            tk.Label(center_frame, text=line, bg=colors["bg"], fg=fg,
                     font=fs, justify="center").pack(pady=(0, 2))
    else:
        if package_name:
            display = package_name if len(package_name) <= 85 else package_name[:80] + " ..."
            lbl = tk.Label(body, text=display, bg=colors["bg"], fg=colors["fg"],
                           font=("Segoe UI", 11, "bold"), wraplength=340)
            lbl.pack(fill="x", pady=(0, 2), padx=5)
            lbl.config(anchor="w", justify="left")
        if urls_count:
            lbl = tk.Label(body, text=f"{urls_count} Link(s) \u00fcbertragen",
                           bg=colors["bg"], fg=colors["text"],
                           font=("Segoe UI", 10))
            lbl.pack(fill="x", pady=(0, 2), padx=5)
            lbl.config(anchor="w", justify="left")

        if urls_count:
            status_text = "Downloads werden automatisch gestartet." if autostart else "Links sind im Linkgrabber."
            lbl = tk.Label(body, text=status_text, bg=colors["bg"], fg="#888888",
                           font=("Segoe UI", 9))
            lbl.pack(fill="x", pady=(6, 0), padx=5)
            lbl.config(anchor="w", justify="left")

    popup_root.geometry(f"{popup_w}x{popup_h}+{x}+{y}")
    wait_ms = max(1000, int(duration) * 1000)

    acc_bar = tk.Frame(popup_root, bg=colors["accent"], height=3)

    def start_progress():
        step_ms = 50
        steps = max(1, wait_ms // step_ms)
        def tick(step=0):
            acc_bar.place(x=0, y=popup_h - 3, relwidth=step / steps, height=3)
            if step < steps:
                popup_root.after(step_ms, lambda: tick(step + 1))
            else:
                popup_root.after(20, fade_out)
        tick()

    def fade_in(step=0):
        steps = 10
        alpha = step / steps
        popup_root.attributes("-alpha", alpha)
        if step < steps:
            popup_root.after(20, lambda: fade_in(step + 1))
        else:
            popup_root.attributes("-alpha", 1)
            start_progress()

    def fade_out(step=0):
        steps = 15
        alpha = 1 - step / steps
        popup_root.attributes("-alpha", alpha)
        if step < steps:
            popup_root.after(20, lambda: fade_out(step + 1))
        else:
            global _active_toasts
            try:
                idx = _active_toasts.index(popup_root)
                _active_toasts.remove(popup_root)
                for i in range(idx, len(_active_toasts)):
                    t = _active_toasts[i]
                    cx = int(t.winfo_x())
                    cy = int(t.winfo_y())
                    target_y = cy + popup_h + 10
                    steps = 8
                    def slide(w, start_y, to_y, st=8):
                        def tick(step=0):
                            if step >= st:
                                w.geometry(f"+{cx}+{to_y}")
                                return
                            frac = (step + 1) / st
                            cur_y = int(start_y + (to_y - start_y) * frac)
                            w.geometry(f"+{cx}+{cur_y}")
                            w.after(20, lambda: tick(step + 1))
                        tick()
                    slide(t, cy, target_y, steps)
            except Exception:
                pass
            popup_root.destroy()

    acc_bar.place(x=0, y=popup_h - 3, relwidth=0, height=3)
    popup_root.after(20, fade_in)
    popup_root.mainloop()


def rsa_decrypt_jk(jk_b64):
    _ensure_rsa_key()
    from Crypto.Cipher import PKCS1_OAEP
    try:
        jk_raw = base64.b64decode(jk_b64)
        cipher = PKCS1_OAEP.new(_cnl_rsa_key)
        return cipher.decrypt(jk_raw)
    except Exception:
        return None


def extract_key_from_js(js_str):
    m = re.search(r"return\s*'([^']+)'", js_str)
    if m:
        return m.group(1)
    return js_str


def _aes_decrypt_nopad(data, key, iv):
    from Crypto.Cipher import AES
    cipher = AES.new(key, AES.MODE_CBC, iv[:16])
    return cipher.decrypt(data)


def _aes_decrypt_pad(data, key, iv):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    cipher = AES.new(key, AES.MODE_CBC, iv[:16])
    return unpad(cipher.decrypt(data), AES.block_size)


def _extract_links(text):
    m = text.lower().find("http")
    if m >= 0:
        text = text[m:]
    links = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        line = line.rstrip("\x00\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f")
        line = line.strip()
        if line.startswith("http://") or line.startswith("https://"):
            links.append(line)
    return links


def decode_crypted(crypted_b64, jk_raw):
    import re
    try:
        encrypted = base64.b64decode(crypted_b64)
    except Exception:
        encrypted = base64.b64decode(crypted_b64 + "==")

    if isinstance(jk_raw, str):
        jk_bytes = jk_raw.encode("ascii")
    else:
        jk_bytes = jk_raw

    log.debug(f"decode_crypted: key={jk_raw!r}, key_len={len(jk_bytes)}, data={len(encrypted)}")

    candidates = []

    # Hex-Key Varianten (wie Chrome-Extension: hex-decode -> AES-CBC NoPadding, IV=Key)
    if all(c in "0123456789abcdefABCDEF" for c in jk_raw):
        hex_key = bytes.fromhex(jk_raw)
        log.debug(f"Hex-Key: {hex_key[:16].hex()}... ({len(hex_key)} Bytes)")
        for desc, key, iv in [
            ("Hex AES-CBC NoPad IV=Key", hex_key[:16], hex_key[:16]),
            ("Hex AES-CBC NoPad IV=0", hex_key[:16], b"\x00" * 16),
        ]:
            if len(key) == 16:
                try:
                    dec = _aes_decrypt_nopad(encrypted, key, iv)
                    text = dec.decode("utf-8", errors="replace")
                    urls = _extract_links(text)
                    if urls:
                        log.info(f"{desc}: OK - {len(urls)} URL(s)")
                        return "\n".join(urls)
                except Exception as e:
                    log.debug(f"{desc}: {e}")

        # Gleiches mit PKCS7 Padding versuchen
        for desc, key, iv in [
            ("Hex AES-CBC PKCS7 IV=Key", hex_key[:16], hex_key[:16]),
            ("Hex AES-CBC PKCS7 IV=0", hex_key[:16], b"\x00" * 16),
        ]:
            if len(key) == 16:
                try:
                    dec = _aes_decrypt_pad(encrypted, key, iv)
                    text = dec.decode("utf-8", errors="replace")
                    urls = _extract_links(text)
                    if urls:
                        log.info(f"{desc}: OK - {len(urls)} URL(s)")
                        return "\n".join(urls)
                except Exception as e:
                    log.debug(f"{desc}: {e}")

    # ASCII Key Varianten
    for k_len in (16, 24, 32):
        if len(jk_bytes) >= k_len:
            k = jk_bytes[:k_len]
            for desc, key, iv in [
                (f"ASCII CBC NoPad IV=Key", k, k),
                (f"ASCII CBC NoPad IV=0", k, b"\x00" * 16),
                (f"ASCII CBC PKCS7 IV=Key", k, k),
                (f"ASCII CBC PKCS7 IV=0", k, b"\x00" * 16),
            ]:
                try:
                    if "NoPad" in desc:
                        dec = _aes_decrypt_nopad(encrypted, key, iv)
                    else:
                        dec = _aes_decrypt_pad(encrypted, key, iv)
                    text = dec.decode("utf-8", errors="replace")
                    urls = _extract_links(text)
                    if urls:
                        log.info(f"{desc}: OK - {len(urls)} URL(s)")
                        return "\n".join(urls)
                except Exception:
                    pass

    # XOR
    for name, key in [("XOR ASCII", jk_bytes), ("XOR digits", bytes(int(c) for c in jk_raw if c.isdigit()))]:
        try:
            dec = bytes(e ^ key[i % len(key)] for i, e in enumerate(encrypted))
            text = dec.decode("utf-8", errors="replace")
            urls = _extract_links(text)
            if urls:
                log.info(f"{name}: OK - {len(urls)} URL(s)")
                return "\n".join(urls)
        except Exception:
            pass

    log.debug(f"Erste 32 Bytes encrypted: {encrypted[:32].hex()}")
    raise Exception("Entschluesselung fehlgeschlagen")


def cnl2_decrypt(crypt_b64, jk_b64, iv_b64=None):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad

    encrypted = base64.b64decode(crypt_b64)

    jk = None
    if isinstance(jk_b64, str):
        jk = base64.b64decode(jk_b64)
    elif isinstance(jk_b64, list):
        jk = bytes(int(x, 16) if isinstance(x, str) and x.startswith("0x") else int(x) for x in jk_b64)

    if iv_b64:
        iv = base64.b64decode(iv_b64)
    elif jk:
        iv = jk[:16]
    else:
        iv = b"\x00" * 16

    if jk:
        for key_len in (16, 24, 32):
            try:
                k = jk[:key_len]
                cipher = AES.new(k, AES.MODE_CBC, iv[:16])
                decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
                return json.loads(decrypted.decode())
            except Exception:
                continue

    if isinstance(jk_b64, str):
        aes_key = rsa_decrypt_jk(jk_b64)
        if aes_key:
            for key_len in (16, 24, 32):
                try:
                    k = aes_key[:key_len]
                    cipher = AES.new(k, AES.MODE_CBC, aes_key[:16])
                    decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
                    return json.loads(decrypted.decode())
                except Exception:
                    continue

    raise Exception("CNL2-Entschluesselung fehlgeschlagen")


def extract_urls(data):
    urls = []
    package_name = None
    passwords = []

    if isinstance(data, list):
        for item in data:
            u, pkg, pws = extract_urls(item)
            urls.extend(u)
            if pkg and not package_name:
                package_name = pkg
            passwords.extend(pws)

    elif isinstance(data, dict):
        if "crypt" in data and data.get("jk"):
            decrypted = cnl2_decrypt(data["crypt"], data["jk"], data.get("iv"))
            return extract_urls(decrypted)

        for key in ("urls", "links"):
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    for v in val:
                        if isinstance(v, dict) and "url" in v:
                            urls.append(v["url"])
                        elif isinstance(v, str):
                            urls.append(v)
                elif isinstance(val, str):
                    urls.extend(val.replace("\r\n", "\n").split("\n"))

        if "url" in data and isinstance(data["url"], str):
            urls.append(data["url"])

        if "package" in data:
            package_name = data["package"]
        if "packageName" in data:
            package_name = data["packageName"]
        if "name" in data and not package_name:
            package_name = data["name"]

        if "passwords" in data:
            pw = data["passwords"]
            passwords = pw if isinstance(pw, list) else [pw]
        if "password" in data:
            passwords.append(data["password"])

        if "links" in data and isinstance(data["links"], list):
            for link in data["links"]:
                if isinstance(link, dict) and "url" in link:
                    urls.append(link["url"])

        if "url" in data and isinstance(data["url"], str) and not urls:
            urls.extend(u.strip() for u in data["url"].split(",") if u.strip())

        if "cnl" in data and isinstance(data["cnl"], dict):
            return extract_urls(data["cnl"])

    return urls, package_name, passwords


def handle_form_post(params, raw_body=None):
    crypted = params.get("crypted", [None])[0]
    jk_str = params.get("jk", [None])[0]
    package_name = params.get("package", [None])[0]
    passwords = params.get("passwords", [])
    source = params.get("source", [None])[0]

    log.info("1/4 CNL2-Daten empfangen – entschlüssele ...")
    log.debug(f"handle_form_post: crypted={crypted[:50] if crypted else None!r}, jk={jk_str[:80] if jk_str else None!r}")

    if isinstance(passwords, list):
        passwords = [p for p in passwords if p]

    try:
        if crypted and jk_str:
            log.info("2/4 CNL2 entschlüsselt – extrahiere URLs ...")
            key_str = extract_key_from_js(jk_str)
            log.info(f"Key aus JS: {key_str!r}")
            decrypted = decode_crypted(crypted, key_str)
            log.info(f"Entschluesselt ({len(decrypted)} Zeichen): {decrypted[:300]}")
            log.info("3/4 URLs extrahiert – sende an MyJDownloader ...")

            try:
                parsed = json.loads(decrypted)
                u, pkg, pws = extract_urls(parsed)
                if not pkg: pkg = package_name
                if not pws: pws = passwords
                log.info(f"JSON-Urls: {u}")
                return u, pkg, pws
            except json.JSONDecodeError:
                urls = []
                for line in decrypted.replace("\r\n", "\n").split("\n"):
                    line = line.strip()
                    if line.startswith("http://") or line.startswith("https://"):
                        urls.append(line)
                if urls:
                    log.info(f"Plaintext-URLs: {urls}")
                    return urls, package_name, passwords
                log.warning(f"Keine URLs im Plaintext: {decrypted[:200]}")
        else:
            log.warning(f"Fehlende Felder: crypted={bool(crypted)}, jk={bool(jk_str)}")
    except Exception as e:
        log.error(f"Form-POST Fehler: {e}", exc_info=True)

    return [], None, []


class CNLHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        ct = self.headers.get("Content-Type", "")
        log.info(f"CNL2-POST {self.path} empfangen ({len(body)} Bytes)")

        dump_path = os.path.join(CONFIG_DIR, "raw_requests.log")
        try:
            with open(dump_path, "a", encoding="utf-8") as f:
                f.write(f"\n--- {self.path} ---\n")
                f.write(f"Content-Type: {ct}\n")
                f.write(f"Body: {body.decode('utf-8', errors='replace')}\n")
        except Exception:
            pass

        log.debug(f"POST {self.path} ct={ct} body={body[:1000]}")

        urls = []
        package_name = None
        passwords = []

        try:
            if "application/x-www-form-urlencoded" in ct:
                params = urllib.parse.parse_qs(body.decode("utf-8"))
                urls, package_name, passwords = handle_form_post(params, body)
            else:
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    params = urllib.parse.parse_qs(body.decode("utf-8"))
                    if "crypted" in params or "jk" in params:
                        urls, package_name, passwords = handle_form_post(params, body)
                    else:
                        log.warning(f"Ungueltiges JSON: {body[:300]}")
                        self.send_error(400, "Ungueltiges JSON")
                        return

            if not urls and 'data' in dir():
                if "crypted" in data and "jk" in data:
                    decrypted = cnl2_decrypt(data["crypted"], data["jk"], data.get("iv"))
                    u, pkg, pws = extract_urls(decrypted)
                    urls.extend(u)
                    if pkg: package_name = pkg
                    if pws: passwords.extend(pws)
                elif "cnl" in data:
                    u, pkg, pws = extract_urls(data)
                    urls.extend(u)
                    if pkg: package_name = pkg
                    if pws: passwords.extend(pws)
                elif "crypt" in data and data.get("jk"):
                    u, pkg, pws = extract_urls(data)
                    urls.extend(u)
                    if pkg: package_name = pkg
                    if pws: passwords.extend(pws)
                else:
                    u, pkg, pws = extract_urls(data)
                    urls.extend(u)
                    if pkg: package_name = pkg
                    if pws: passwords.extend(pws)

            urls = [u.strip() for u in urls if u.strip()]

            if not urls:
                log.warning("Keine URLs gefunden")
                self.send_error(400, "Keine URLs gefunden")
                return

            log.info(f"Empfangen: {len(urls)} URL(s) | Package: {package_name or '-'}")

            def send_and_notify():
                try:
                    log.info("4/4 Sende URLs an MyJDownloader ...")
                    myjd.add_links(urls, package_name=package_name, passwords=passwords, autostart=autostart_downloads)
                    log.info(f"{len(urls)} Link(s) erfolgreich gesendet")
                    notify("ClickNLoad Bridge", f"{len(urls)} Link(s) an JDownloader gesendet",
                           package_name=package_name, urls_count=len(urls), autostart=autostart_downloads)
                except Exception as e:
                    log.error(f"Fehler beim Senden: {e}")
                    notify("ClickNLoad Bridge", f"Fehler: {e}", duration=8)

            threading.Thread(target=send_and_notify, daemon=True).start()

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "urls": len(urls)}).encode())

        except Exception as e:
            log.error(f"Fehler: {e}", exc_info=True)
            self.send_error(500, str(e))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        log.info(f"GET {self.path} von {self.client_address[0]}")

        if path == "/jdcheck.js":
            self.send_response(200)
            self.send_header("Content-Type", "application/javascript")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b"jdownloader=true;\nversion='43307';")
            return

        if path == "/jdcheckjson":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(b'{"jdownloader":true}')
            return

        if path == "/crossdomain.xml":
            self.send_response(200)
            self.send_header("Content-Type", "text/xml")
            self.end_headers()
            self.wfile.write(
                b'<?xml version="1.0"?>'
                b'<!DOCTYPE cross-domain-policy SYSTEM '
                b'"http://www.macromedia.com/xml/dtds/cross-domain-policy.dtd">'
                b'<cross-domain-policy><allow-http-request-headers-from domain="*" '
                b'headers="*"/></cross-domain-policy>'
            )
            return

        if path in ("/flash", "/flashgot", "/cnl2") or path.startswith("/flash/"):
            _ensure_rsa_key()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"publicKey": _cnl_rsa_pubkey_b64}).encode())
            return

        params = {}
        if "?" in self.path:
            query = self.path.split("?", 1)[1]
            for pair in query.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

        if params:
            try:
                urls, package_name, passwords = extract_urls(params)
                urls = [u.strip() for u in urls if u.strip()]
                if urls:
                    log.info(f"GET: {len(urls)} URL(s)")

                    def send_and_notify():
                        try:
                            myjd.add_links(urls, package_name=package_name, passwords=passwords, autostart=autostart_downloads)
                            log.info(f"{len(urls)} Link(s) erfolgreich gesendet")
                            notify("ClickNLoad Bridge", f"{len(urls)} Link(s) an JDownloader gesendet",
                                   package_name=package_name, urls_count=len(urls), autostart=autostart_downloads)
                        except Exception as e:
                            log.error(f"Fehler: {e}")
                            notify("ClickNLoad Bridge", f"Fehler: {e}", duration=8)

                    threading.Thread(target=send_and_notify, daemon=True).start()

                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(b"OK")
                return
            except Exception as e:
                log.error(f"GET-Fehler: {e}")
                self.send_error(500, str(e))
                return

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b"jdownloader=true")

    def log_message(self, fmt, *args):
        if len(args) >= 3:
            log.debug(f"{args[0]} {args[1]} {args[2]}")
        elif args:
            log.debug(fmt % args)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def _make_icon(bg, arrow):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, size - 2, size - 2], fill=bg)
    cx, cy = size // 2, size // 2
    draw.rectangle([cx - 4, size // 4, cx + 4, cy + 4], fill=arrow)
    draw.polygon([
        (cx - 14, cy + 4), (cx + 14, cy + 4), (cx, cy + 20)
    ], fill=arrow)
    return img

GREEN_TRAY_ICON = _make_icon("#2ecc71", "#000000")
RED_TRAY_ICON   = _make_icon("#e74c3c", "#ffffff")

def create_tray_icon():
    return GREEN_TRAY_ICON

def set_tray_icon_red():
    global _tray_pystray
    if _tray_pystray is not None:
        _tray_pystray.icon = RED_TRAY_ICON


def run_with_systray(server):
    global _tray_icon, _tray_pystray, autostart_downloads, show_toast, show_console
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    icon = None

    def on_exit(icon_item):
        icon.stop()

    def on_toggle_autostart(icon_item):
        global autostart_downloads
        autostart_downloads = not autostart_downloads
        config["autostart_downloads"] = autostart_downloads
        save_config()
        log.info(f"Autostart Downloads: {autostart_downloads}")

    device_label = f"Device: {config['myjd_device_name']}"

    def on_toggle_console(icon_item):
        global show_console
        show_console = not show_console
        config["show_console"] = show_console
        save_config()
        toggle_console(show_console)
        log.info(f"Konsole anzeigen: {show_console}")

    def on_toggle_toast(icon_item):
        global show_toast
        show_toast = not show_toast
        config["show_toast"] = show_toast
        save_config()
        log.info(f"Toast anzeigen: {show_toast}")

    def set_duration(sec):
        global toast_duration
        toast_duration = sec
        config["toast_duration"] = sec
        save_config()
        log.info(f"Toast-Dauer: {sec}s")

    def color_item(label, code, target_var, config_key):
        def on_click(*args):
            globals()[target_var] = code
            config[config_key] = code
            save_config()
        return pystray.MenuItem(label, on_click, checked=lambda *a, _c=code: globals().get(target_var) == _c)

    jd2_bg = "#193D43"
    jd2_fg = "#DDF1F6"
    jd2_accent = "#E6B002"

    bg_menu = pystray.Menu(
        color_item("JD2", jd2_bg, "bg_color", "bg_color"),
        color_item("Rot", "#FF0000", "bg_color", "bg_color"),
        color_item("Gr\u00fcn", "#00FF00", "bg_color", "bg_color"),
        color_item("Gelb", "#FFFF00", "bg_color", "bg_color"),
        color_item("Blau", "#0000FF", "bg_color", "bg_color"),
        color_item("Schwarz", "#000000", "bg_color", "bg_color"),
        color_item("Weiss", "#FFFFFF", "bg_color", "bg_color"),
    )
    fg_menu = pystray.Menu(
        color_item("JD2", jd2_fg, "text_color", "text_color"),
        color_item("Rot", "#FF0000", "text_color", "text_color"),
        color_item("Gr\u00fcn", "#00FF00", "text_color", "text_color"),
        color_item("Gelb", "#FFFF00", "text_color", "text_color"),
        color_item("Blau", "#0000FF", "text_color", "text_color"),
        color_item("Schwarz", "#000000", "text_color", "text_color"),
        color_item("Weiss", "#FFFFFF", "text_color", "text_color"),
    )
    accent_menu = pystray.Menu(
        color_item("JD2", jd2_accent, "toast_color", "toast_color"),
        color_item("Rot", "#FF0000", "toast_color", "toast_color"),
        color_item("Gr\u00fcn", "#00FF00", "toast_color", "toast_color"),
        color_item("Gelb", "#FFFF00", "toast_color", "toast_color"),
        color_item("Blau", "#0000FF", "toast_color", "toast_color"),
        color_item("Schwarz", "#000000", "toast_color", "toast_color"),
        color_item("Weiss", "#FFFFFF", "toast_color", "toast_color"),
    )

    duration_presets = sorted(set([3, 5, 10, 15, 20, 25, 30] + [toast_duration]))
    dur_items = []
    for s in duration_presets:
        def make_cb(sec):
            return lambda *args: set_duration(sec)
        dur_items.append(pystray.MenuItem(f"{s} s", make_cb(s),
                        checked=lambda *a, _s=s: toast_duration == _s))
    dur_menu = pystray.Menu(*dur_items)

    toast_sub = pystray.Menu(
        pystray.MenuItem("Ein / Aus", on_toggle_toast, checked=lambda x: show_toast),
        pystray.MenuItem("Anzeigedauer", dur_menu),
        pystray.MenuItem("Hintergrundfarbe", bg_menu),
        pystray.MenuItem("Schriftfarbe", fg_menu),
        pystray.MenuItem("Akzentfarbe", accent_menu),
    )

    menu = pystray.Menu(
        pystray.MenuItem(f"Port {config.get('cnl_port', 9666)} | {device_label}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Downloads direkt starten", on_toggle_autostart, checked=lambda x: autostart_downloads),
        pystray.MenuItem("Toasts", toast_sub),
        pystray.MenuItem("Konsole anzeigen", on_toggle_console, checked=lambda x: show_console),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Beenden", on_exit),
    )

    img = create_tray_icon()
    icon = pystray.Icon("clicknload_bridge", img, "ClickNLoad Bridge", menu)
    _tray_icon = icon
    _tray_pystray = icon
    email = config.get("myjd_email", "")
    device = config.get("myjd_device_name", "")
    notify("ClickNLoad Bridge", f"ClickNLoad Bridge aktiv\n{email}\n{device}", duration=5)
    icon.run()
    server.shutdown()
    log.info("Bridge beendet")


def main():
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        if not kernel32.GetConsoleWindow():
            kernel32.AllocConsole()
        hwnd_console = kernel32.GetConsoleWindow()
        if hwnd_console:
            kernel32.SetConsoleTitleW("ClickNLoad Bridge - Debug")
            STD_OUTPUT_HANDLE = -11
            console_handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            if console_handle and console_handle != -1:
                kernel32.WriteConsoleW(console_handle, "Console initialized\r\n", 21, None, None)
        sys.stdout = open("CONOUT$", "w", encoding="utf-8")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8")
        con_handler = logging.StreamHandler(sys.stdout)
        con_handler.setLevel(logging.DEBUG)
        con_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        log.addHandler(con_handler)
        log.info("Console-Handler aktiv")
        if not show_console and hwnd_console:
            user32.ShowWindow(hwnd_console, 0)

        host = config.get("listen_host", "127.0.0.1")
        port = config.get("cnl_port", 9666)

        log.info("=== ClickNLoad Bridge ===")
        log.info("Starte ...")
        log.info(f"Device: {config['myjd_device_name']}")

        myjd.connect()
        myjd.list_devices()
        log.info("MyJDownloader bereit")

        server = ThreadedHTTPServer((host, port), CNLHandler)
        log.info(f"HTTP-Server laeuft auf {host}:{port}")

        port80_server = None
        try:
            port80_server = ThreadedHTTPServer(("127.0.0.1", 80), CNLHandler)
            threading.Thread(target=port80_server.serve_forever, daemon=True).start()
            log.info("Zusaetzlicher Listener auf 127.0.0.1:80 (hide.cx u.a.)")
        except Exception as e:
            log.debug(f"Port 80 nicht verfuegbar: {e}")

        download_dir = os.path.join(os.environ["USERPROFILE"], "Downloads")
        def on_dlc_file(content, filename):
            try:
                _, pkgs = myjd.add_dlc(content, autostart=autostart_downloads)
                log.info(f"DLC erfolgreich gesendet: {filename}")
                if pkgs:
                    pkg_name = pkgs[0]["name"]
                    total = sum(p["link_count"] for p in pkgs)
                    notify("ClickNLoad Bridge", "",
                           package_name=pkg_name, urls_count=total, autostart=autostart_downloads)
                else:
                    notify("ClickNLoad Bridge", f"DLC: {filename} an JDownloader gesendet",
                           autostart=autostart_downloads)
            except Exception as e:
                log.error(f"DLC-Fehler beim Senden: {e}")
                notify("ClickNLoad Bridge", f"DLC-Fehler: {e}", duration=8)
        start_dlc_watcher(download_dir, on_dlc_file)

        if HAS_SYSTRAY:
            log.info("Systray-Icon aktiv")
            run_with_systray(server)
        else:
            log.info("Konsolen-Modus (pystray fehlt)")
            def shutdown(sig, frame):
                log.info("Server wird heruntergefahren...")
                server.shutdown()
                sys.exit(0)
            signal.signal(signal.SIGINT, shutdown)
            signal.signal(signal.SIGTERM, shutdown)
            server.serve_forever()
    except Exception as e:
        log.error(f"Fehler beim Start: {e}", exc_info=True)
        notify("ClickNLoad Bridge", f"Start fehlgeschlagen: {e}", duration=10)
        import time
        time.sleep(5)
        sys.exit(1)


if __name__ == "__main__":
    main()
