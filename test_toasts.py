"""Test: 3 Toasts im Abstand von 2 Sekunden - prüft Stacking + Sliding."""
import sys, os, time, threading, json

# Config für main.py bereitstellen
os.environ["APPDATA"] = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_config")
cfg_dir = os.path.join(os.environ["APPDATA"], "ClickNLoad Bridge")
os.makedirs(cfg_dir, exist_ok=True)
with open(os.path.join(cfg_dir, "config.json"), "w") as f:
    json.dump({"myjd_email":"x","myjd_password":"x","myjd_device_name":"x","cnl_port":9666}, f)

# main importieren (startet KEINE Server/MyJD bei gui_mode)
sys.argv.append("--gui-mode")  # wird von main ignoriert, aber verhindert nichts
import main as m

# Globale Einstellungen setzen
m.show_toast = True
m.toast_duration = 6
m.bg_color = "#193D43"
m.text_color = "#DDF1F6"
m.toast_color = "#E6B002"

def fire(msg, pkg=None, count=0):
    m.notify("Test", msg, package_name=pkg, urls_count=count, autostart=True)

fire("Toast 1", "Erster Test-Paketname", 3)
time.sleep(2)
fire("Toast 2", "Zweiter Test-Paketname", 5)
time.sleep(2)
fire("Toast 3", "Dritter Test-Paketname", 7)

print("3 Toasts gesendet. Schliessen sich automatisch nach 6s.")
print("Warte auf Toasts...")
time.sleep(8)
print("Fertig.")
