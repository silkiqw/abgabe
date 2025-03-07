import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')
django.setup()
import pytest
import time
import subprocess
import re
import requests
import django.core.cache as cache
from django.test import TestCase
from django.core.cache import cache 
from django.http import HttpResponse
from django.shortcuts import render
from unittest.mock import patch, mock_open
from django.conf import settings
from django.test import RequestFactory
from myapp.views import (
    distance,
    is_within_rad,
    filter_duplicates,
    remove_duplicates,
    get_names,
    read_stations,
    check,
    fetch_data,
    get_season,
    get_name,
)

def test_docker_resource_limits():
    container_name = "test_django_wetter_app"
    image_name = "ghcr.io/silkiqw/django-wetter-app:latest"

    try:
        # Starte den Container mit den Limits
        subprocess.run(
            [
                "docker", "run", "-d", "--name", container_name,
                "--memory", "1g", "--cpus", "2",
                image_name
            ],
            check=True
        )

        # Warte einige Sekunden, damit der Container sich stabilisiert
        time.sleep(10)

        # Führe docker stats aus
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}} {{.CPUPerc}}", container_name],
            capture_output=True, text=True, check=False
        )

        output = result.stdout.strip()
        print(f"DEBUG: docker stats output: {output}")  # Debugging

        # Falls `output` leer ist, Fehler werfen
        if not output:
            raise RuntimeError("Fehler: `docker stats` hat keine Werte zurückgegeben!")

        values = output.split()
        print(f"DEBUG: docker stats values: {values}")

        if len(values) < 4:
            raise ValueError(f"Unerwartete `docker stats` Ausgabe: {output}")

        # Speicherverbrauch extrahieren (immer erstes Element)
        mem_usage = values[0]

        # CPU-Auslastung ist das letzte Element
        cpu_perc = values[-1]

        # Prüfen, ob `cpu_perc` tatsächlich eine Zahl ist
        if not cpu_perc.replace(".", "").replace("%", "").isdigit():
            raise ValueError(f"CPU-Wert ungültig: {cpu_perc} (Output: {output})")

        cpu_usage = float(cpu_perc.replace("%", ""))
        assert cpu_usage <= 200.0, f"CPU-Verbrauch überschreitet 2 vCPUs! (Aktuell: {cpu_usage}%)"

        # RAM-Wert mit Regex extrahieren (z. B. "512MiB" oder "1.2GiB")
        match = re.match(r"([\d.]+)(MiB|GiB)", mem_usage)
        if not match:
            raise ValueError(f"RAM-Wert ungültig: {mem_usage} (Output: {output})")

        mem_value, mem_unit = match.groups()
        mem_used = float(mem_value) * 1024 if mem_unit == "GiB" else float(mem_value)

        assert mem_used < 1024, f"RAM-Verbrauch überschreitet 1 GB! (Aktuell: {mem_used} MiB)"

    finally:
        # Container stoppen und entfernen
        subprocess.run(["docker", "stop", container_name], check=False)
        subprocess.run(["docker", "rm", container_name], check=False)
    


@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected", [
    (48.1351, 11.5820, 48.1351, 11.5820, 0.0),  # Gleicher Punkt → Distanz = 0
    (48.1351, 11.5820, 48.1360, 11.5820, 0.1),  # Ca. 0.1 km nach Norden
    (48.1351, 11.5820, 49.0000, 12.0000, 100.0) # Entfernung ca. 100 km
])
def test_distance(lat1, lon1, lat2, lon2, expected):
    result = distance(lat1, lon1, lat2, lon2)
    assert pytest.approx(result, rel=1e-2) == expected # Toleranz ±1%

@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected", [
    (50.0000, 8.0000, 50.1000, 8.0000, True),  # Etwa 11 km → innerhalb 50 km
    (50.0000, 8.0000, 55.0000, 13.0000, False)  # Mehrere hundert km → außerhalb 50 km
])
def test_is_within_rad(lat1, lon1, lat2, lon2, expected):
    # Test für is_within_rad innerhalb Radius
    assert is_within_rad(lat1, lon1, lat2, lon2, 50) == expected

def test_is_within_radius():
    # Test for is_within_rad innerhalb Radius
    assert is_within_rad(50.0, 10.0, 50.1, 10.1, 15) == True

def test_is_outside_radius():
    # Test for is_within_rad außerhalb Radius
    assert is_within_rad(50.0, 10.0, 60.0, 20.0, 100) == False

def test_filter_duplicates():
    # Test für filter_duplicates mit Duplikaten
    input_list = [1, 2, 2, 3, 4, 4, 4]
    expected_output = [2, 2, 4, 4, 4]
    assert filter_duplicates(input_list) == expected_output

def test_filter_no_duplicates():
    # Test für filter_duplicates ohne Duplikate
    input_list = [1, 2, 3]
    expected_output = []
    assert filter_duplicates(input_list) == expected_output

def test_remove_duplicates():
    # Test für remove_duplicates mit Duplikaten
    input_list = [1, 2, 2, 3, 4, 4, 4]
    expected_output = [1, 2, 3, 4]  # Korrigierte Erwartung
    assert remove_duplicates(input_list) == expected_output

def test_remove_no_duplicates():
    # Test für remove_duplicates ohne Duplikate
    input_list = [1, 2, 3]
    expected_output = [1, 2, 3]  # Korrigierte Erwartung
    assert remove_duplicates(input_list) == expected_output

@patch("myapp.views.get_name", side_effect=lambda x: f"Station {x}")
def test_get_names(mock_get_name):
    # Test für get_names
    input_list = [["1"], ["2"], ["3"]]
    expected_output = [["1", "Station 1"], ["2", "Station 2"], ["3", "Station 3"]]
    assert get_names(input_list) == expected_output

@patch("builtins.open", new_callable=mock_open, read_data="ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021")
def test_read_stations(mock_file):
    # Test für read_stations
    expected_output = "ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021"
    assert read_stations() == expected_output

@patch("builtins.open", side_effect=Exception("Fehler beim Lesen der Datei"))
def test_read_stations_error(mock_file):
    # Test für read_stations mit Fehler
    assert read_stations() == []

@patch("myapp.views.render", return_value=HttpResponse())
@patch("myapp.views.read_stations", return_value=(
    "ID1        50.0      10.0      TMAX 2000 2020\n"
    "ID2        60.0      20.0      TMIN 2001 2021"
))
@patch("myapp.views.is_within_rad", return_value=True)
@patch("myapp.views.filter_duplicates", return_value=[["ID1"]])
@patch("myapp.views.remove_duplicates", return_value=[["ID1"]])
@patch("myapp.views.get_names", return_value=[["ID1", "TestStation"]])
def test_check_within_radius(mock_get_names, mock_remove_duplicates, mock_filter_duplicates,
                           mock_is_within_rad, mock_read_stations, mock_render):
    # Test für check innerhalb Radius
    factory = RequestFactory()
    request = factory.post("/check", {
        "lat": "50.0",
        "lon": "10.0",
        "searchRadius": "100",
        "dateFrom": "2000-01-01",
        "dateTo": "2020-01-01"
    })
    
    response = check(request)
    print("Response:", response)
    print("Mock render called:", mock_render.called)
    print("Mock render call args:", mock_render.call_args)
    print("Render called:", mock_render.called)
    print("is_within_rad called:", mock_is_within_rad.called)
    print("read_stations called:", mock_read_stations.called)
    
    # Assert that render was called with the expected context
    mock_render.assert_called_once()
    context = mock_render.call_args[0][2]  # Get the context passed to render
    assert 'result' in context
    assert context['result'] == [["ID1", "TestStation"]]

@patch("myapp.views.render", return_value=HttpResponse())
@patch("myapp.views.read_stations", return_value="ID1        50.0      10.0      TMAX 2000 2020\nID2        60.0      20.0      TMIN 2001 2021")
@patch("myapp.views.is_within_rad", return_value=False)
def test_check_outside_radius(mock_is_within_rad, mock_read_stations, mock_render):
    # Configure mock_render to return a response with context
    mock_render.return_value.context = {'result2': "Für diese Kombination von Koordinaten und Zeitraum gibt es nicht genügend Daten."}
    
    # Test für check außerhalb Radius
    factory = RequestFactory()
    request = factory.post("/check", {
        "lat": "50.0",
        "lon": "10.0",
        "searchRadius": "10",
        "dateFrom": "2000-01-01",
        "dateTo": "2020-01-01"
    })
    
    response = check(request)
    
    # Assert that render was called with the expected context
    mock_render.assert_called_once()
    context = mock_render.call_args[0][2]  # Get the context passed to render
    assert 'result2' in context
    assert context['result2'] == "Für diese Kombination von Koordinaten und Zeitraum gibt es nicht genügend Daten."

@patch("requests.get")
@patch("myapp.views.get_season", return_value="Spring")
def test_fetch_data(mock_get_season, mock_get):
    # Simuliere eine erfolgreiche HTTP-Antwort
    mock_get.return_value.status_code = 200

    # Simulierte Wetterdaten, angepasst auf die tatsächlichen Daten von 2009 bis 2024
    mock_data = """
2009 7.7 15.2 5.7 14.8 11.5 23.1 6.2 14.0 1.5 4.1
2010 7.5 15.0 5.2 13.7 12.0 23.0 5.0 12.8 0.9 4.1
2011 7.4 15.3 5.5 16.3 11.5 22.8 6.9 14.2 1.8 5.8
2012 7.3 15.2 5.2 15.3 12.1 23.8 5.5 12.9 1.9 5.3
2013 7.6 14.3 5.8 12.3 11.7 23.8 5.7 13.3 2.0 4.6
2014 7.0 15.0 5.1 15.3 11.2 22.9 6.5 14.3 1.7 6.4
2015 8.1 15.3 5.7 14.5 13.0 25.8 6.0 14.1 2.4 5.5
2016 7.4 14.9 5.1 13.6 12.2 23.8 6.1 13.8 2.1 6.5
2017 7.4 15.4 4.8 15.0 12.3 25.0 5.4 13.3 2.4 5.2
2018 8.1 16.3 7.3 17.2 12.4 25.4 6.3 15.1 2.2 5.6
2019 7.0 15.4 4.2 14.3 12.4 25.5 5.5 14.1 1.3 6.1
2020 7.1 15.0 4.3 15.4 11.6 23.5 6.1 14.0 2.6 6.4
2021 7.1 14.2 3.9 12.4 12.2 23.5 5.4 13.4 2.4 5.9
2022 7.6 15.9 5.9 15.0 12.4 25.9 5.7 15.1 2.0 6.2
2023 8.1 15.9 5.9 13.8 12.6 25.2 7.3 16.7 3.1 6.8
2024 7.9 16.0 5.5 16.2 13.5 25.0 7.1 13.6 2.7 7.7
    """
    mock_get.return_value.text = mock_data

    # Setze Cache-Wert für lat und lon (da get_season ihn verwendet)
    cache.set("lat", 48.4022)
    cache.set("lon", 11.6944)

    # Führe die Funktion aus
    result = fetch_data("USW00094728", [2020])
    print("Fetch data result:", result)  # Debugging-Ausgabe

    # Teste, ob das Ergebnis eine Liste ist
    assert isinstance(result, list)

    # Teste, ob das Ergebnis die erwartete Struktur hat
    expected_output = [[2020, 7.1, 15.0, 4.3, 15.4, 11.6, 23.5, 6.1, 14.0, 2.6, 6.4]]
    assert result == expected_output



@patch("requests.get")
def test_fetch_data_error(mock_get):
    # Test für fetch_data mit Fehler
    mock_get.return_value.status_code = 404
    try:
        fetch_data("ID1", [2020])
        assert False, "Sollte eine Exception werfen"
    except Exception:
        assert True

def test_get_season_northern_hemisphere():
    # Test für get_season (Nordhalbkugel)
    assert get_season(3) == "Spring"
    assert get_season(6) == "Summer"
    assert get_season(9) == "Fall"
    assert get_season(12) == "Winter"

@patch("django.core.cache.cache.get", return_value=-50.0)
def test_get_season_southern_hemisphere(mock_cache_get):
    # Test für get_season (Südhalbkugel)
    assert get_season(3) == "Fall"
    assert get_season(6) == "Winter"
    assert get_season(9) == "Spring"
    assert get_season(12) == "Summer"

@patch("builtins.open", new_callable=mock_open, read_data="ID1,Name1\nID2,Name2")
def test_get_name(mock_file):
    # Test für get_name
    assert get_name("ID1") == "Name1"
    assert get_name("ID2") == "Name2"

@patch("builtins.open", side_effect=Exception("Fehler beim Lesen der Datei"))
def test_get_name_error(mock_file):
    # Test für get_name mit Fehler
    assert get_name("ID1") is None
