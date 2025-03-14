from django.shortcuts import render

# Create your views here.
import math
import csv as csv
import os
import pandas
import requests
from django.conf import settings
from django.core.cache import cache

def index(request):   
    if read_stations():
        return render(request, "index.html", {"result": None})
    else:
        return render(request, "index.html", {"result": None, "err": "Keine Verbindung zum Server. Anwendung beenden und später neu starten"})

    

def distance(lat1, lon1, lat2, lon2):
    #calculates the distance of 2 sets of coordinates (lat1, lon1 and lat2, lon2) using Haversine
    lat1 = float(lat1) #Change Type from string to float  
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
    #checks 2 sets of coordinats in specific distance
    r = int(r)
    d = distance(lat1, lon1, lat2, lon2)
    return d <= r

def filter_duplicates(lst):
    #removes every non-duplicate lst-item 
    return [x for x in lst if lst.count(x) > 1]

def remove_duplicates(lst):
    #returns new list without duplicates
    l_new = []
    for l in range(len(lst)):
        if l % 2 == 0:
            l_new.append(lst[l])
    return l_new

def get_names(lst):
    #Adds station names for every sub list in lst
    #returns lst with station-names
    for l in lst:
        station_id = l[0]
        name = get_name(station_id)
        if name:  
            l.append(name)
    return lst

def read_stations():
    #Loads the data of ghcnd-inventory(station.txt)
    try:
        with open(os.path.join(settings.BASE_DIR, "data", "stations.txt"), mode='r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        print("Fehler beim Lesen der Datei:", e)
        return []
    
def sort_by_dist(lst):
    #sorts a given list of lists by the distance-entry 
    return sorted(lst, key=lambda l: l[1])


def check(request):
    #gets inputs (lat, lon, start_date, end_date, rad) from html-form and generating list of years.
    #saving inputs in cache for other functions
    #searches ghcnd-inventory for station in range and existing TMIN + TMAX values in years-interval. Saves station-id and distance in stations-list
    #2 lines for TMIN and TMAX -> every station needs 2 entrys in stations list -> removing of non-duplicates
    #Adds station-names to station list and sorts entries by distance
    #returns stations list (and saves in cache) 
    if request.method == 'POST':
        lat = request.POST.get("lat") #Eingabe aus html-form
        lon = request.POST.get("lon")
        rad = request.POST.get("searchRadius")
        cache.set("lat",lat,timeout=3600)
        start_date = int(request.POST.get("dateFrom")[:4])
        end_date = int(request.POST.get("dateTo")[:4])
        inputs = [lat, lon, start_date, end_date, rad]
        cache.set("inputs",inputs,timeout=3600)
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
                        stations.append([station_id, round(distance(lat, lon, station_lat, station_lon),1)])
        stations = filter_duplicates(stations)
        stations = remove_duplicates(stations)
        stations = get_names(stations)
        stations = sort_by_dist(stations)
        cache.set("stations", stations, timeout=3600)

        if(len(stations) == 0):#check empty list -> no findings
            return render(request, 'index.html', {'result2': "Für diese Kombination von Koordinaten und Zeitraum gibt es nicht genügend Daten."})
        else:
            return render(request, 'index.html', {'result': stations, "inputs": inputs})
            

def result(request):
    #gets the station-choice from html form
    #gets station-data from fetch_data()
    #returns name and data to result.html
    if request.method == 'POST':
        id = request.POST.get("choice")
        name = get_name(id)
        years = cache.get("years",[2024])
        res = fetch_data(id, years)
        if res == "error":
            return render(request, 'result.html', {'err': 'Keine Verbindung zum Server. Später noch einmal versuchen.'})
        cache.set("station_data", res, timeout=3600)
        cache.set("name",name, timeout=3600)
        return render(request, 'result.html', {'result': res, 'name' : name})

DATA_URL = "https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/all/"    #URL to station-data of all noaa-stations

def fetch_data(station_id, years):
    #Downloads weather data from noaa using the id (station_id) to identify the correct staion
    #years: list of years
    #Extracts year, month, datatype, day-values of every lines
    #if year and datatype matches the values get added. Values of december get added to the following year.
    #-9999-values get removed (-9999 means day has no value)
    #calculates means using dictionaries, saves means into avg_list in specific order
    #returns avg_list
    station_id = str(station_id)
    try:
        url = f"{DATA_URL}{station_id}.dly"
        response = requests.get(url)
    except:
        return "error"
    records = []
    for year in years:
        lines = response.text.split("\n")

        print("Lines from response:")
        print(lines)  # Zeigt alle Zeilen, die aus der Antwort gesplittet wurden
        
        for line in lines:
            if len(line) < 20:
                continue
            record_year = line[11:15].strip()
            if int(record_year) + 1 == year:
                record_type = line[17:21].strip()
                if record_type == "TMIN" or record_type == "TMAX":
                    if int(line[15:17].strip()) == 12:
                        for i in range(21, len(line), 8):
                            day_value = line[i:i+5].strip()
                            if day_value.lstrip("-").isdigit():
                                if int(day_value) != -9999:
                                    month = int(line[15:17].strip())
                                    value = int(day_value) / 10 #Daten sind als Zehntel Grad Celsius gespeichert deshalb muss durch 10 geteilt werden
                                    season = get_season(month)
                                    records.append((str(int(record_year)+1), record_type, season, value))

            elif record_year == str(year):
                record_type = line[17:21].strip()
                if record_type == "TMIN" or record_type == "TMAX":
                    if int(line[15:17].strip()) != 12:
                        for i in range(21, len(line), 8):
                            day_value = line[i:i+5].strip()
                            if day_value.lstrip("-").isdigit():
                                if int(day_value) != -9999:
                                    month = int(line[15:17].strip())
                                    value = int(day_value) / 10 #Daten sind als Zehntel Grad Celsius gespeichert deshalb muss durch 10 geteilt werden
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
    #returns the season of the month
    #different season depending on the latitude (lat) of the station
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
    #searches ghcnd-stations.csv and returns the name of station using the station-id(id)
    with open(os.path.join(settings.BASE_DIR, "data", "ghcnd-stations.csv"), mode='r', encoding='utf-8') as file:#Zugriff stations.csv
            reader = csv.reader(file)
            data = list(reader)
            for i in data:
                if i[0] == str(id):
                    return i[5] 

def back(request):
    #Button "Dateninput"
    #Loads and return inputs and list of stations in range from cache
    if request.method == "POST":
        stations = cache.get("stations",[])
        inputs = cache.get("inputs", [])
        if(len(stations) == 0):
            return render(request, 'index.html', {'nothing': ""})
        else:
            if len(inputs) == 0:
                return render(request, 'index.html', {'result': stations})
            else:
                return render(request, 'index.html', {'result': stations, 'inputs': inputs})

def back_data(request):
   #Button "Wetterstationsdetails"
    #Loads stations-name and data, if station-data has previously been loaded, from cache 
    if request.method == "POST":
        station_data = cache.get("station_data", [])
        name = cache.get("name", "Bitte Station auswählen")
        if len(station_data) == 0:
            return render(request, "result.html", {"name": name})
        else:
            return render(request, "result.html", {"result": station_data, "name": name})

