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
from unittest.mock import patch, mock_open, MagicMock
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
    sort_by_dist,
    result,
    back,
    back_data,
    index
)

def test_docker_resource_limits():
    container_name = "test_django_wetter_app"
    image_name = "ghcr.io/silkiqw/django-wetter-app:latest"

    try:
         # Start the container with limits
        subprocess.run(
            [
                "docker", "run", "-d", "--name", container_name,
                "--memory", "1g", "--cpus", "2",
                image_name
            ],
            check=True
        )

        # Wait a few seconds for the container to stabilize
        time.sleep(10)

       # Run docker stats
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.MemUsage}} {{.CPUPerc}}", container_name],
            capture_output=True, text=True, check=False
        )

        output = result.stdout.strip()

       # If `output` is empty, raise an error
        if not output:
            raise RuntimeError("Fehler: `docker stats` hat keine Werte zurückgegeben!")

        values = output.split()

        if len(values) < 4:
            raise ValueError(f"Unerwartete `docker stats` Ausgabe: {output}")

        # Extract memory usage (always the first element)
        mem_usage = values[0]

       # CPU usage is the last element
        cpu_perc = values[-1]

        # Check if `cpu_perc` is actually a number
        if not cpu_perc.replace(".", "").replace("%", "").isdigit():
            raise ValueError(f"CPU-Wert ungültig: {cpu_perc} (Output: {output})")

        cpu_usage = float(cpu_perc.replace("%", ""))
        assert cpu_usage <= 200.0, f"CPU-Verbrauch überschreitet 2 vCPUs! (Aktuell: {cpu_usage}%)"

        # Extract RAM value with regex (e.g. "512MiB" or "1.2GiB")
        match = re.match(r"([\d.]+)(MiB|GiB)", mem_usage)
        if not match:
            raise ValueError(f"RAM-Wert ungültig: {mem_usage} (Output: {output})")

        mem_value, mem_unit = match.groups()
        mem_used = float(mem_value) * 1024 if mem_unit == "GiB" else float(mem_value)

        assert mem_used < 1024, f"RAM-Verbrauch überschreitet 1 GB! (Aktuell: {mem_used} MiB)"

    finally:
       # Stop and remove container
        subprocess.run(["docker", "stop", container_name], check=False)
        subprocess.run(["docker", "rm", container_name], check=False)
    


@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected", [
    (48.1351, 11.5820, 48.1351, 11.5820, 0.0),  # Same point → Distance = 0
    (48.1351, 11.5820, 48.1360, 11.5820, 0.1),  # Approx. 0.1 km north
    (48.1351, 11.5820, 49.0000, 12.0000, 100.0) # Distance approx. 100 km
])
def test_distance(lat1, lon1, lat2, lon2, expected):
    result = distance(lat1, lon1, lat2, lon2)
    assert pytest.approx(result, rel=1e-2) == expected # Tolerance ±1%

@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected", [
    (50.0000, 8.0000, 50.1000, 8.0000, True),  # About 11 km → within 50 km
    (50.0000, 8.0000, 55.0000, 13.0000, False)  # Several hundred km → outside 50 km
])
def test_is_within_rad(lat1, lon1, lat2, lon2, expected):
    # Test for is_within_rad within radius
    assert is_within_rad(lat1, lon1, lat2, lon2, 50) == expected

def test_is_within_radius():
    # Test for is_within_rad within radius
    assert is_within_rad(50.0, 10.0, 50.1, 10.1, 15) == True

def test_is_outside_radius():
    # Test for is_within_rad outside radius
    assert is_within_rad(50.0, 10.0, 60.0, 20.0, 100) == False

def test_filter_duplicates():
     # Test filter_duplicates with duplicates
    input_list = [1, 2, 2, 3, 4, 4, 4]
    expected_output = [2, 2, 4, 4, 4]
    assert filter_duplicates(input_list) == expected_output

def test_filter_no_duplicates():
    # Test filter_duplicates without duplicates
    input_list = [1, 2, 3]
    expected_output = []
    assert filter_duplicates(input_list) == expected_output


@patch("myapp.views.get_name", side_effect=lambda x: f"Station {x}")
def test_get_names(mock_get_name):
    # Test for get_names
    input_list = [["1"], ["2"], ["3"]]
    expected_output = [["1", "Station 1"], ["2", "Station 2"], ["3", "Station 3"]]
    assert get_names(input_list) == expected_output

@patch("builtins.open", new_callable=mock_open, read_data="ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021")
def test_read_stations(mock_file):
   # Test for read_stations
    expected_output = "ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021"
    assert read_stations() == expected_output

@patch("builtins.open", side_effect=Exception("Fehler beim Lesen der Datei"))
def test_read_stations_error(mock_file):
    # Test for read_stations with error
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
    # Test for check within radius
    factory = RequestFactory()
    request = factory.post("/check", {
        "lat": "50.0",
        "lon": "10.0",
        "searchRadius": "100",
        "dateFrom": "2000-01-01",
        "dateTo": "2020-01-01"
    })
    
    response = check(request)
    
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
    
    # Test for check outside radius
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
@patch("myapp.views.get_season", side_effect=lambda month: "Spring" if month in [3, 4, 5] else 
                                           "Summer" if month in [6, 7, 8] else
                                           "Fall" if month in [9, 10, 11] else "Winter")
def test_fetch_data_aggregation(mock_get_season, mock_get):
    # Set up cache values
    cache.set("lat", 40.0)
    cache.set("lon", 10.0)
    
    # Create mock response with controlled test data
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    # Create sample data with known values for one year (2020)
    # Format matches NOAA GHCN daily format
    mock_data = """
STATION12020001TMAX  100  110  120  130  140  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370  380  390  400
STATION12020001TMIN   50   60   70   80   90  100  110  120  130  140  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350
STATION12020003TMAX  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370  380  390  400  410  420  430  440-9999
STATION12020003TMIN   80   90  100  110  120  130  140  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370-9999
STATION12020006TMAX  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370  380  390  400  410  420  430  440  450  460  470  480  490-9999
STATION12020006TMIN  100  110  120  130  140  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370  380  390-9999
STATION12020009TMAX  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370  380  390  400  410  420  430  440  450  460  470-9999
STATION12020009TMIN   90  100  110  120  130  140  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370  380-9999
STATION12020012TMAX  120  130  140  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360  370  380  390  400  410  420
STATION12020012TMIN   60   70   80   90  100  110  120  130  140  150  160  170  180  190  200  210  220  230  240  250  260  270  280  290  300  310  320  330  340  350  360
"""
    mock_response.text = mock_data
    mock_get.return_value = mock_response
    
    # Call the function with our test data
    result = fetch_data("STATION1", [2020])
    
    # Check that result is a list
    assert isinstance(result, list)
    assert len(result) == 1  # Should have one year of data
    
    # First element should be the year
    assert result[0][0] == 2020
    
    # Check that we have all 11 expected elements in the year data
    # [year, TMIN_avg, TMAX_avg, Spring_TMIN, Spring_TMAX, Summer_TMIN, Summer_TMAX, 
    #  Fall_TMIN, Fall_TMAX, Winter_TMIN, Winter_TMAX]
    assert len(result[0]) == 11
    
    # Verify the computed averages match expected values
    # You'll need to calculate these expected values based on your test data
    # For example (using approximate expected values):
    assert pytest.approx(result[0][1], 0.1) == 20.0  # Avg TMIN
    assert pytest.approx(result[0][2], 0.1) == 25.0  # Avg TMAX
    
    # Spring averages (month 3)
    assert pytest.approx(result[0][3], 0.1) == 15.0  # Spring TMIN
    assert pytest.approx(result[0][4], 0.1) == 22.0  # Spring TMAX
    
    # Summer averages (month 6)
    assert pytest.approx(result[0][5], 0.1) == 25.0  # Summer TMIN
    assert pytest.approx(result[0][6], 0.1) == 35.0  # Summer TMAX
    
    # Fall averages (month 9)
    assert pytest.approx(result[0][7], 0.1) == 22.0  # Fall TMIN
    assert pytest.approx(result[0][8], 0.1) == 32.0  # Fall TMAX
    
    # Winter averages (month 12 and month 1)
    assert pytest.approx(result[0][9], 0.1) == 17.0  # Winter TMIN
    assert pytest.approx(result[0][10], 0.1) == 27.0  # Winter TMAX


@patch("requests.get")
def test_fetch_data_error(mock_get):
    # Test für fetch_data with errors
    mock_get.return_value.status_code = 404
    try:
        fetch_data("ID1", [2020])
        assert False, "Sollte eine Exception werfen"
    except Exception:
        assert True

def test_get_season_northern_hemisphere():
    # Test for get_season (Nordhalbkugel)
    assert get_season(3) == "Spring"
    assert get_season(6) == "Summer"
    assert get_season(9) == "Fall"
    assert get_season(12) == "Winter"

@patch("django.core.cache.cache.get", return_value=-50.0)
def test_get_season_southern_hemisphere(mock_cache_get):
    # Test for get_season (Südhalbkugel)
    assert get_season(3) == "Fall"
    assert get_season(6) == "Winter"
    assert get_season(9) == "Spring"
    assert get_season(12) == "Summer"

@patch("builtins.open", new_callable=mock_open, read_data="ID1,Field1,Field2,Field3,Field4,Name1")
@patch("myapp.views.range", return_value=[1])
@patch("csv.reader")
def test_get_name(mock_reader, mock_range, mock_file):
    # Configuring the CSV-Reader-Mock
    mock_reader.return_value = [
        ["ID", "Field1", "Field2", "Field3", "Field4", "Name"],
        ["ID1", "Field1", "Field2", "Field3", "Field4", "Name1"]
    ]
    
    assert get_name("ID1") == "Name1"

@patch("builtins.open", side_effect=Exception("Fehler beim Lesen der Datei"))
def test_get_name_error(mock_file):
    # Test for get_name mit Fehler
    with pytest.raises(Exception):
        get_name("ID1")

def test_sort_by_dist():
    # Test sorting stations by distance
    test_data = [
        ["STATION1", 50.5],
        ["STATION2", 10.3],
        ["STATION3", 75.8],
        ["STATION4", 5.2]
    ]
    
    sorted_data = sort_by_dist(test_data)
    
    # Check if the data is sorted by the distance (second element)
    assert sorted_data[0][0] == "STATION4"
    assert sorted_data[1][0] == "STATION2"
    assert sorted_data[2][0] == "STATION1"
    assert sorted_data[3][0] == "STATION3"
    
    # Check that all elements are still present
    assert len(sorted_data) == 4
    
    # Check that the original list items are unchanged except for order
    stations = [item[0] for item in sorted_data]
    assert "STATION1" in stations
    assert "STATION2" in stations
    assert "STATION3" in stations
    assert "STATION4" in stations

@patch("myapp.views.render", return_value=HttpResponse())
@patch("myapp.views.get_name", return_value="Test Station")
@patch("myapp.views.fetch_data", return_value=[["2020", 10.5, 20.3, 8.1, 18.7, 15.2, 25.6, 12.3, 22.1, 5.4, 15.8]])
def test_result(mock_fetch_data, mock_get_name, mock_render):
    # Set up request
    factory = RequestFactory()
    request = factory.post("/result", {"choice": "TEST123"})
    
    # Set up cache.get to return test data
    with patch("django.core.cache.cache.get", side_effect=lambda key, default: [2020] if key == "years" else default):
        response = result(request)
    
    # Check if the function processed the request correctly
    mock_get_name.assert_called_once_with("TEST123")
    mock_fetch_data.assert_called_once()
    
    # Check if the cache was set correctly
    mock_render.assert_called_once()
    context = mock_render.call_args[0][2]
    assert 'result' in context
    assert 'name' in context
    assert context['name'] == "Test Station"
    assert context['result'] == [["2020", 10.5, 20.3, 8.1, 18.7, 15.2, 25.6, 12.3, 22.1, 5.4, 15.8]]

@patch("myapp.views.render", return_value=HttpResponse())
def test_back_with_stations(mock_render):
    # Test back function when stations are in cache
    factory = RequestFactory()
    request = factory.post("/back")
    
    # Set up test data
    test_stations = [["STATION1", 10.2, "Station Name 1"], ["STATION2", 25.7, "Station Name 2"]]
    test_inputs = [50.1, 10.5, 2000, 2020, 50]
    
    # Mock cache.get to return test data
    with patch("django.core.cache.cache.get", side_effect=lambda key, default: 
              test_stations if key == "stations" else 
              test_inputs if key == "inputs" else default):
        response = back(request)
    
    # Check if render was called with correct context
    mock_render.assert_called_once()
    context = mock_render.call_args[0][2]
    assert 'result' in context
    assert 'inputs' in context
    assert context['result'] == test_stations
    assert context['inputs'] == test_inputs

@patch("myapp.views.render", return_value=HttpResponse())
def test_back_without_stations(mock_render):
    # Test back function when no stations are in cache
    factory = RequestFactory()
    request = factory.post("/back")
    
    # Mock cache.get to return empty list
    with patch("django.core.cache.cache.get", return_value=[]):
        response = back(request)
    
    # Check if render was called with correct context
    mock_render.assert_called_once()
    context = mock_render.call_args[0][2]
    assert 'nothing' in context
    assert context['nothing'] == ""

@patch("myapp.views.render", return_value=HttpResponse())
def test_back_data_with_data(mock_render):
    # Test back_data function when station data is in cache
    factory = RequestFactory()
    request = factory.post("/back_data")
    
    # Set up test data
    test_data = [["2020", 10.5, 20.3, 8.1, 18.7, 15.2, 25.6, 12.3, 22.1, 5.4, 15.8]]
    test_name = "Test Station"
    
    # Mock cache.get to return test data
    with patch("django.core.cache.cache.get", side_effect=lambda key, default: 
              test_data if key == "station_data" else 
              test_name if key == "name" else default):
        response = back_data(request)
    
    # Check if render was called with correct context
    mock_render.assert_called_once()
    context = mock_render.call_args[0][2]
    assert 'result' in context
    assert 'name' in context
    assert context['result'] == test_data
    assert context['name'] == test_name

@patch("myapp.views.render", return_value=HttpResponse())
def test_back_data_without_data(mock_render):
    # Test back_data function when no station data is in cache
    factory = RequestFactory()
    request = factory.post("/back_data")
    
    # Mock cache.get for empty station data but with a name
    with patch("django.core.cache.cache.get", side_effect=lambda key, default: 
              [] if key == "station_data" else 
              "Test Station" if key == "name" else default):
        response = back_data(request)
    
    # Check if render was called with correct context
    mock_render.assert_called_once()
    context = mock_render.call_args[0][2]
    assert 'name' in context
    assert context['name'] == "Test Station"
    assert 'result' not in context

def test_index():
    # Test index function
    factory = RequestFactory()
    request = factory.get("/")
    
    with patch("myapp.views.render", return_value=HttpResponse()) as mock_render:
        response = index(request)
        
        # Check if render was called with correct template and context
        mock_render.assert_called_once_with(request, "index.html", {"result": None})
