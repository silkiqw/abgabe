import requests
import os
from django.conf import settings

URL_inventory = "https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt"
URL_stations = "https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.csv"
save_path_inventory = os.path.join(settings.BASE_DIR, "data", "stations.txt")
save_path_csv = URL_STATIONS = os.path.join(settings.BASE_DIR, "data", "ghcnd-stations.csv")

def download_stations():
    #Lädt die ghcnd-inventory.txt für die Angabe der Zeiträume für TMIN und TMAX sowie due ghcnd-stations.csv für die Namen der Stationen herunter und speichert diese
    try:
        print("Lade Inventory")
        response = requests.get(URL_inventory, timeout=10)
        response.raise_for_status()  # Löst eine Exception bei HTTP-Fehlern aus
        with open(save_path_inventory, "w", encoding="utf-8") as file:
            file.write(response.text)

        print("Daten erfolgreich heruntergeladen und gespeichert.")
    except requests.RequestException as e:
        print(f"Fehler beim Laden der Daten: {e}")
    
    try:
        print("Lade CSV")
        response2 = requests.get(URL_stations, timeout=10)
        response2.raise_for_status()  # Fehler werfen, falls Request fehlschlägt

        with open(save_path_csv, "w", encoding="utf-8") as file:
            file.write(response2.text)

        print(f"Datei gespeichert unter: {save_path_csv}")
    except requests.RequestException as e:
        print(f"Fehler beim Laden von {URL_stations}: {e}")
