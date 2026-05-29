import os
import time
import logging
import threading

log = logging.getLogger("cnl")

POLL_INTERVAL = 3


def start_dlc_watcher(download_dir, on_dlc_file):
    processed = set()

    def watch():
        log.info(f"DLC-Überwachung gestartet: {download_dir}")
        while True:
            dlc_found = False
            try:
                if os.path.isdir(download_dir):
                    for entry in os.listdir(download_dir):
                        if not entry.lower().endswith(".dlc"):
                            continue
                        fpath = os.path.join(download_dir, entry)
                        if not os.path.isfile(fpath):
                            continue
                        if fpath in processed:
                            continue

                        mtime = os.path.getmtime(fpath)
                        age = time.time() - mtime
                        if age < 2:
                            continue

                        dlc_found = True
                        processed.add(fpath)
                        try:
                            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                                content = f.read()
                            log.info(f"DLC gefunden: {entry} ({len(content)} Bytes)")
                            on_dlc_file(content, entry)
                            os.remove(fpath)
                            processed.discard(fpath)
                            log.info(f"DLC gelöscht: {entry}")
                        except Exception as e:
                            log.error(f"DLC-Fehler bei {entry}: {e}", exc_info=True)
            except Exception:
                pass
            time.sleep(15 if dlc_found else POLL_INTERVAL)

    t = threading.Thread(target=watch, daemon=True, name="dlc-watcher")
    t.start()
    return t
