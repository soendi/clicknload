import myjdapi
import logging

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
        if not self._api.is_connected():
            log.info("Token abgelaufen, verbinde neu...")
            self._api.connect(self.email, self.password)
            self._device = None
        if not self._device:
            self.list_devices()

    def _call(self, func, *args, **kwargs):
        self._ensure_connected()
        try:
            return func(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "token" in err_str or "bad" in err_str or "unauthorized" in err_str:
                log.info(f"API-Fehler ({e}), versuche Neuverbindung...")
                self._api.connect(self.email, self.password)
                self._device = None
                self.list_devices()
                return func(*args, **kwargs)
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
        result = self._call(self._device.linkgrabber.add_links, [params])
        log.info(f"Linkgrabber Job-ID: {result.get('id')}")
        return result

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
