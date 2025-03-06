from django.shortcuts import render

# Create your views here.
import math
import csv as csv
import os
import pandas
import requests
from django.conf import settings
from django.core.cache import cache

def index(request):     #Startseite
    return render(request, "index.html", {"result": None})
    
#Distanzberechnung nahc Haversine
def distance(lat1, lon1, lat2, lon2):
    lat1 = float(lat1) #Daten kommen als String  
    lat2 = int(lat2)/10000 #Anpassung der CSV-Werte
    lon1 = float(lon1) 
    lon2 = int(lon2)/10000
    R = 6371  #mittlerer Erdradius km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def is_within_rad(lat1, lon1, lat2, lon2, r):
    r = int(r)
    d = distance(lat1, lon1, lat2, lon2)
    return d <= r

def check(request):
    if request.method == 'POST':
        lat = request.POST.get("lat") #Eingabe aus html-form
        lon = request.POST.get("lon")
        rad = request.POST.get("searchRadius")
        cache.set("lat",lat,timeout=3600)
        print(cache.get("lat",0))
        start_date = int(request.POST.get("dateFrom")[:4])
        end_date = int(request.POST.get("dateTo")[:4])
        years = []
        while start_date <= end_date:
            years.append(start_date)
            start_date = start_date + 1
        cache.set("years",years,timeout=3600)
        with open(os.path.join(settings.BASE_DIR, "data", "station.csv"), mode='r', encoding='utf-8') as file:#Zugriff stations.csv
            reader = csv.reader(file)
            data = list(reader)
            in50 = []   #Liste Stationen in Distanz
            for i in range(1, 128025):          #Distanzüberrüfung
                if(is_within_rad(lat, lon, data[i][1], data[i][2], rad)):
                    in50.append([data[i][0],data[i][4]])
            if(len(in50) == 0):#check ob leere Liste -> keine Treffer
                return render(request, 'index.html', {'result': "Keine Station gefunden"})
            else:
                return render(request, 'index.html', {'result': in50})
            

def result(request):    #Anzeigen der Stationsdaten
    if request.method == 'POST':
        id = request.POST.get("choice")
        name = get_name(id)
        years = cache.get("years",[2024])
        res = fetch_data(id, years)
        return render(request, 'result.html', {'result': res, 'name' : name}) #weiterleitung auf neue Seite

DATA_URL = "https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/all/"    #Url zu der Liste aller Stationen

def fetch_data(station_id, years):     #Zugriff auf die Daten der webseite
    station_id = str(station_id)
    url = f"{DATA_URL}{station_id}.dly"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Fehler beim Abrufen der Wetterdaten")
    records = []
    for year in years:
        lines = response.text.split("\n")
        
        for line in lines:
            if len(line) < 20:
                continue
            record_year = line[11:15].strip()
            if record_year == str(year):
                record_type = line[17:21].strip()
                if record_type == "TMIN" or record_type == "TMAX":
                    for i in range(21, len(line), 8):
                        day_value = line[i:i+5].strip()
                        if day_value.isdigit():
                            month = int(line[15:17].strip())
                            value = int(day_value) / 10.0
                            season = get_season(month)
                            records.append((record_year, record_type, season, value))
    
    df = pandas.DataFrame(records, columns=["Year", "Type","Season", "Value"])
    avg_values = df.groupby(["Type","Year"])["Value"].mean().unstack().to_dict()
    season_avg_values = df.groupby(["Season", "Type", "Year"])["Value"].mean().unstack().to_dict()
    avg_list = []
    for y in season_avg_values:
        year = []
        year.append(y)
        year.append(round(avg_values[y].get("TMIN"),1))
        year.append(round(avg_values[y].get("TMAX"),1))
        year.append(round(season_avg_values[y].get(('Spring', 'TMIN')),1))
        year.append(round(season_avg_values[y].get(('Spring', 'TMAX')),1))
        year.append(round(season_avg_values[y].get(('Summer', 'TMIN')),1))
        year.append(round(season_avg_values[y].get(('Summer', 'TMAX')),1))
        year.append(round(season_avg_values[y].get(('Fall', 'TMIN')),1))
        year.append(round(season_avg_values[y].get(('Fall', 'TMAX')),1))
        year.append(round(season_avg_values[y].get(('Winter', 'TMIN')),1))
        year.append(round(season_avg_values[y].get(('Winter', 'TMAX')),1))        
        avg_list.append(year)

    if len(avg_list) == 0:
        return "Für diese Kombination von Station und Jahr liegen nicht genug Daten vor"
    else:
        return avg_list
    
def get_season(month):
    lat = float(cache.get("lat",0))
    if lat >= 0:
        if month in [3, 4, 5]:
            return "Spring"
        elif month in [6, 7, 8]:
            return "Summer"
        elif month in [9, 10, 11]:
            return "Fall"
        else:
            return "Winter"
    else:
        if month in [3, 4, 5]:
            return "Fall"
        elif month in [6, 7, 8]:
            return "Winter"
        elif month in [9, 10, 11]:
            return "Spring"
        else:
            return "Summer"
        
def get_name(id):
    with open(os.path.join(settings.BASE_DIR, "data", "station.csv"), mode='r', encoding='utf-8') as file:#Zugriff stations.csv
            reader = csv.reader(file)
            data = list(reader)
            for i in range(1, 128025):
                if data[i][0] == str(id):
                    return data[i][4] 
