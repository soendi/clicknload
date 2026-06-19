import myjdapi
import logging
import time

log = logging.getLogger("cnl")

class MyJDownloader:
    def __init__(self, email, password, device_name):
        self.email = email
        self.password = password
        self.device_name = device_name
        self._api = myjdapi.Myjdapi()
        self._api.set_app_key("clicknload_bridge")
        self._device = None

    def connect(self):
        log.info("Verbinde mit MyJDownloader...")
        self._api.connect(self.email, self.password)
        log.info("Verbunden")
        self._start_keepalive()

    def _start_keepalive(self):
        import threading

        def ping():
            while True:
                time.sleep(4 * 3600)
                try:
                    if self._api.is_connected():
                        self._api.list_devices()
                        log.debug("Keepalive: Session aktiv")
                except Exception:
                    log.warning("Keepalive: Session abgelaufen, wird bei nächstem Aufruf erneuert")

        t = threading.Thread(target=ping, daemon=True, name="myjd-keepalive")
        t.start()

    def list_devices(self):
        devices = self._api.list_devices()
        for dev in devices:
            if dev.get("name") == self.device_name:
                self._device = self._api.get_device(self.device_name)
                log.info(f"Device '{self.device_name}' gefunden")
                return devices
        names = [d.get("name", "?") for d in devices]
        raise Exception(f"Device '{self.device_name}' nicht gefunden. Verfügbar: {names}")

    def _ensure_connected(self):
        now = time.time()
        if now - getattr(self, "_last_call", 0) > 1200:
            log.info("Token altert (20min), erneuere vorbeugend ...")
            try:
                self._api.connect(self.email, self.password)
            except Exception:
                pass
            self._device = None
        if not self._api.is_connected():
            log.info("Token abgelaufen, verbinde neu...")
            self._api.connect(self.email, self.password)
            self._device = None
        if not self._device:
            self.list_devices()

    def _call(self, func, *args, **kwargs):
        self._ensure_connected()
        try:
            result = func(*args, **kwargs)
            self._last_call = time.time()
            return result
        except Exception as e:
            err_str = str(e).lower()
            log.info(f"API-Fehler, versuche Neuverbindung: {e}")
            for attempt in range(3):
                try:
                    self._api.connect(self.email, self.password)
                    self._device = None
                    self.list_devices()
                    return func(*args, **kwargs)
                except Exception as e2:
                    log.warning(f"Neuverbindung {attempt+1}/3 fehlgeschlagen: {e2}")
                    time.sleep(2)
            log.error(f"MyJDownloader-Verbindung verloren – wechsle auf rotes Icon")
            try:
                from main import set_tray_icon_red
                set_tray_icon_red()
            except Exception:
                pass
            raise

    def add_links(self, urls, package_name=None, passwords=None, autostart=False):
        if isinstance(urls, str):
            urls = [urls]

        params = {
            "links": "\n".join(urls),
            "autostart": autostart,
            "packageName": package_name or "",
            "extractPassword": "",
            "downloadPassword": "",
            "destinationFolder": "",
            "priority": "DEFAULT",
            "overwritePackagizerRules": False
        }

        if passwords:
            if isinstance(passwords, str):
                passwords = [passwords]
            params["extractPassword"] = passwords[0] if passwords else ""
            params["downloadPassword"] = passwords[0] if passwords else ""

        log.info(f"Sende {len(urls)} Links an '{self.device_name}'")
        self._ensure_connected()
        result = self._call(self._device.linkgrabber.add_links, [params])
        log.info(f"Linkgrabber Job-ID: {result.get('id')}")
        return result

    def remove_offline_packages(self, package_name=None):
        self._ensure_connected()
        lg = self._device.linkgrabber
        pkgs = self._call(lg.query_packages)
        if not pkgs:
            log.debug("remove_offline: keine Pakete im Linkgrabber")
            return []
        removed = []
        log.debug(f"remove_offline: {len(pkgs)} Pakete gefunden")
        for p in pkgs:
            name = p.get("name", "?")
            online = p.get("onlineCount", 0)
            offline = p.get("offlineCount", 0)
            unknown = p.get("unknownCount", 0)
            temp_unk = p.get("tempUnknownCount", 0)
            total = p.get("childCount", 1)
            log.debug(f"  Paket '{name}': online={online} offline={offline} unknown={unknown} temp_unk={temp_unk} total={total}")
            if temp_unk == 0 and offline > 0 and online + offline + unknown == total:
                log.info(f"Offline erkannt: {offline}/{total} offline – lösche Paket '{name}'")
                self._call(lg.remove_links, [], [str(p.get("uuid"))])
                log.info(f"Paket gelöscht: {name} ({offline}/{total} offline)")
                removed.append({"name": name, "offline": offline, "total": total})
        return removed

    def add_dlc(self, dlc_content, autostart=False):
        self._ensure_connected()
        import base64
        import time
        lg = self._device.linkgrabber

        content_b64 = base64.b64encode(dlc_content.encode("utf-8")).decode()
        log.info(f"Sende DLC ({len(dlc_content)} Bytes) an '{self.device_name}'")
        result = self._call(lg.add_container, "dlc", content_b64)
        log.info(f"DLC Job-ID: {result.get('id')}")

        pkgs = None
        for attempt in range(10 if autostart else 1):
            time.sleep(3)
            pkgs = self._call(lg.query_packages)
            if pkgs:
                total_links = sum(p.get("childCount", 0) for p in pkgs)
                log.info(f"Paket(e) gefunden nach {(attempt+1)*3}s: {len(pkgs)} Paket(e), {total_links} Link(s)")
                for p in pkgs:
                    log.info(f"  - {p.get('name', '?')}: {p.get('childCount', 0)} Link(s)")
                break
            log.info(f"Warte auf Pakete... ({attempt+1}/10)")

        package_info = []
        if pkgs:
            for p in pkgs:
                package_info.append({
                    "name": p.get("name", "?"),
                    "link_count": p.get("childCount", 0),
                })
            if autostart:
                try:
                    puids = [p["uuid"] for p in pkgs]
                    self._call(lg.move_to_downloadlist, [], puids)
                    log.info("Paket(e) in Download-Liste verschoben")
                except Exception as e:
                    log.error(f"move_to_downloadlist fehlgeschlagen: {e}")
                try:
                    self._call(self._device.downloadcontroller.start_downloads)
                    log.info("Downloads gestartet (autostart)")
                except Exception as e:
                    log.error(f"start_downloads fehlgeschlagen: {e}")
        else:
            log.warning("Keine Pakete nach DLC-Zugabe gefunden")

        return result, package_info
