"""Test: Sendet einen einzelnen Link an MyJDownloader via Bridge-API."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from myjd import MyJDownloader

url = "https://ddownload.com/roe44zabj3oh"
m = MyJDownloader("sondereggerlukas@gmail.com", "jdownloaderbalgach", "JDownloader@SYNOLOGY")
m.connect()
m.list_devices()
m.add_links([url], package_name="Test-Link", autostart=True)
print(f"✅ Gesendet: {url}")
