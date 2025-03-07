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
    lat2 = float(lat2)
    lon1 = float(lon1) 
    lon2 = float(lon2)
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

def filter_duplicates(lst):
    return [x for x in lst if lst.count(x) > 1]

def remove_duplicates(lst):
    l_new = []
    for l in range(len(lst)):
        if l % 2 == 0:
            l_new.append(lst[l])
    return l_new

def get_names(lst):
    for item in lst:
        station_id = item[0]
        name = get_name(station_id)
        if name:  # Nur anhängen, wenn ein Name gefunden wurde
            item.append(name)
    return lst

def read_stations():
    try:
        with open(os.path.join(settings.BASE_DIR, "data", "stations.txt"), mode='r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print("Fehler beim Lesen der Datei:", e)
        return []
    


def check(request):
    if request.method == 'POST':
        lat = request.POST.get("lat") #Eingabe aus html-form
        lon = request.POST.get("lon")
        rad = request.POST.get("searchRadius")
        cache.set("lat",lat,timeout=3600)
        start_date = int(request.POST.get("dateFrom")[:4])
        end_date = int(request.POST.get("dateTo")[:4])
        years = []
        date = start_date
        while date <= end_date:
            years.append(date)
            date = date + 1
        cache.set("years",years,timeout=3600)

        
        response = read_stations()
        stations = []
        for line in response.split("\n"):
            if line.strip():
                station_id = line[:11].strip()
                station_lat = float(line[12:20].strip())
                station_lon = float(line[21:30].strip())
                element = line[31:35].strip()
                start = int(line[36:40].strip())
                end = int(line[41:45].strip())
                if element in ("TMIN", "TMAX") and start <= int(start_date) and end >= int(end_date):
                    if (is_within_rad(lat, lon, station_lat, station_lon, rad)):
                        stations.append([station_id])
        stations = filter_duplicates(stations)
        stations = remove_duplicates(stations)
        stations = get_names(stations)
        cache.set("stations", stations, timeout=3600)

        if(len(stations) == 0):#check ob leere Liste -> keine Treffer
            return render(request, 'index.html', {'result2': "Für diese Kombination von Koordinaten und Zeitraum gibt es nicht genügend Daten."})
        else:
            return render(request, 'index.html', {'result': stations})
            

def result(request):    #Anzeigen der Stationsdaten
    if request.method == 'POST':
        id = request.POST.get("choice")
        name = get_name(id)
        years = cache.get("years",[2024])
        res = fetch_data(id, years)
        cache.set("station_data", res, timeout=3600)
        cache.set("name",name, timeout=3600)
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

        print("Lines from response:")
        print(lines)  # Zeigt alle Zeilen, die aus der Antwort gesplittet wurden
        
        for line in lines:
            if len(line) < 20:
                continue
            record_year = line[11:15].strip()
            print(f"Extracted year: {record_year}")
            if record_year == str(year):
                record_type = line[17:21].strip()
                print(f"Extracted record type: {record_type}")
                if record_type == "TMIN" or record_type == "TMAX":
                    for i in range(21, len(line), 8):
                        day_value = line[i:i+5].strip()
                        print(f"Extracted day value: {day_value}")
                        if day_value.lstrip("-").isdigit():
                            if int(day_value) != -9999:
                                month = int(line[15:17].strip())
                                print(f"Extracted month: {month}")
                                value = int(day_value) / 10
                                season = get_season(month)
                                print(f"Season: {season}, Value: {value}")
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

def back(request):
    if request.method == "POST":
        stations = cache.get("stations",[])
        if(len(stations) == 0):
            return render(request, 'index.html', {'no': ""})
        else:
            return render(request, 'index.html', {'result': stations})

def back_data(request):
    if request.method == "POST":
        station_data = cache.get("station_data", [])
        name = cache.get("name", "Bitte Station auswählen")
        if len(station_data) == 0:
            return render(request, "result.html", {"name": name})
        else:
            return render(request, "result.html", {"result": station_data, "name": name})
