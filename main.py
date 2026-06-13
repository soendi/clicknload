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

_ARROW_PNG_B64 = "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"


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


import base64, io

def _colorize_arrow(color):
    src = Image.open(io.BytesIO(base64.b64decode(_ARROW_PNG_B64))).convert("RGBA")
    out = Image.new("RGBA", src.size)
    for y in range(src.height):
        for x in range(src.width):
            _, _, _, a = src.getpixel((x, y))
            if a > 0:
                out.putpixel((x, y), (*color, a))
    return out

GREEN_ICON = _colorize_arrow((46, 204, 113))
RED_ICON   = _colorize_arrow((231, 76, 60))

def create_tray_icon():
    return GREEN_ICON.resize((64, 64), Image.LANCZOS)

def set_tray_icon_red():
    global _tray_pystray
    if _tray_pystray is not None:
        _tray_pystray.icon = RED_ICON.resize((64, 64), Image.LANCZOS)


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
