"""Test: Sendet einen Offline-Link und testet den Offline-Dialog."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myjd import MyJDownloader
import main as m

# Globale Toast-Einstellungen
m.show_toast = True
m.toast_duration = 8
m.bg_color = "#193D43"
m.text_color = "#DDF1F6"
m.toast_color = "#E6B002"

url = "https://ddownload.com/roe44zabj3oh"
myjd = MyJDownloader("sondereggerlukas@gmail.com", "jdownloaderbalgach", "JDownloader@SYNOLOGY")
myjd.connect()
myjd.list_devices()

print("Sende Offline-Link...")
myjd.add_links([url], package_name="Offline-Test", autostart=False)
print("✅ Gesendet – warte 12s auf Link-Check...")
time.sleep(12)

removed = myjd.remove_offline_packages()
if removed:
    for r in removed:
        print(f"🔴 Offline-Paket gefunden: {r['name']} ({r['offline']}/{r['total']})")
        decision = m.show_offline_choice(r["name"], r["offline"], r["total"])
        print(f"Entscheidung: {decision}")
        if decision == "delete":
            myjd._call(myjd._device.linkgrabber.remove_links, [], [str(r["uuid"])])
            print("Paket gelöscht")
        elif decision == "show":
            import webbrowser
            webbrowser.open("https://my.jdownloader.org")
        else:
            print("Paket behalten")
else:
    print("✅ Keine Offline-Pakete gefunden (Links sind online)")
