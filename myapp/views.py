from django.shortcuts import render

# Create your views here.
import math
import csv as csv
import os
import requests
from django.conf import settings

def index(request):     #Startseite
    return render(request, "index.html", {"result": None})
    
#Distanzberechnung nahc Haversine
def distance(lat1, lon1, lat2, lon2):
    lat1 = int(lat1)/10000 #Daten kommen als String deswegen Umwandlung 
    lat2 = int(lat2)/10000
    lon1 = int(lon1)/10000 #Anpassung der CSV-Werte
    lon2 = int(lon2)/10000
    R = 6371  #mittlerer Erdradius km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def is_within_50km(lat1, lon1, lat2, lon2):
    d = distance(lat1, lon1, lat2, lon2)
    return d <= 50


def check(request):
    if request.method == 'POST':
        lat = request.POST.get("lat") #Eingabe aus html-form
        lon = request.POST.get("lon")
        with open(os.path.join(settings.BASE_DIR, "data", "station.csv"), mode='r', encoding='utf-8') as file:#Zugriff stations.csv
            reader = csv.reader(file)
            data = list(reader)
            in50 = []   #Liste Stationen in Distanz
            for i in range(1, 128025):          #Distanzüberrüfung
                if(is_within_50km(lat, lon, data[i][1], data[i][2])):
                    in50.append([data[i][0],data[i][4]])
            if(len(in50) == 0):#check ob leere Liste -> keine Treffer
                return render(request, 'index.html', {'result': "Keine Station gefunden"})
            else:
                return render(request, 'index.html', {'result': str(in50)})
            

def result(request):    #Anzeigen der Stationsdaten
    if request.method == 'POST':
        id = request.POST.get("station_id")
        res = fetch_data(id)
        return render(request, 'result.html', {'result': str(res)}) #weiterleitung auf neue Seite

DATA_URL = "https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/all/"    #Url zu der Liste aller Stationen

def fetch_data(station_id):     #Zugriff auf die Daten der webseite
    station_id = str(station_id)
    url = f"{DATA_URL}{station_id}.dly"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Fehler beim Abrufen der Wetterdaten")
    return response.text[:500]