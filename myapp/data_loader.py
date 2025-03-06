import requests
import os
from django.conf import settings

URL = "https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt"
SAVE_PATH = os.path.join(settings.BASE_DIR, "data", "stations.txt")

def download_stations():
    print("Lade NOAA-Daten herunter...")
    try:
        response = requests.get(URL, timeout=10)
        response.raise_for_status()  # Löst eine Exception bei HTTP-Fehlern aus
        print(response.text[:100])
        with open(SAVE_PATH, "w", encoding="utf-8") as file:
            file.write(response.text)
        print("Daten erfolgreich heruntergeladen und gespeichert.")
    except requests.RequestException as e:
        print(f"Fehler beim Laden der Daten: {e}")
