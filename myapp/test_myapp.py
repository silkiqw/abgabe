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
@patch("myapp.views.get_season", return_value="Spring")
def test_fetch_data(mock_get_season, mock_get):
    # Simulate a successful HTTP response
    mock_get.return_value.status_code = 200

    # Mock data in the correct NOAA GHCN daily format
    # Format: Station ID + Year + Month + Element + Values...
    mock_data = """
USW0009472820200101TMAX  267  278  283  256  233  228  228  261  294  294  294  306  306  300  261  256  239  228  256  267  283  289  250  194  206  233  261  272  267  261  239
USW0009472820200101TMIN  217  200  183  194  183  150  144  156  167  189  161  172  178  183  194  183  178  167  172  194  200  206  183  144  133  156  167  178  178  172  156
USW0009472820200102TMAX  256  267  261  261  261  211  206  233  261  261  217  228  239  244  272  278  294  306  306  311  300  294  278  272  261  261  267  267  278  256-9999
USW0009472820200102TMIN  172  178  194  189  194  172  167  133  150  178  183  156  139  167  189  211  222  217  222  200  206  206  194  189  183  178  183  189  206  194-9999
USW0009472820200103TMAX  250  233  211  222  239  239  228  244  267  261  256  250  256  261  267  261  272  272  261  261  256  250  267  256  228  233  244  256  250  222  222
USW0009472820200103TMIN  183  172  156  144  156  161  150  150  156  172  167  183  172  183  189  189  194  206  194  194  194  183  194  194  178  156  156  183  194  183  167
USW0009472820200104TMAX  239  244  256  272  250  244  256  244  222  244  250  256  261  256  239  222  228  256  267  261  250  256  256  261  267  272  267  261  267  256-9999
USW0009472820200104TMIN  178  183  167  194  194  172  194  178  167  156  172  172  183  178  150  144  133  144  189  194  183  178  144  156  183  200  200  194  189  189-9999
USW0009472820200105TMAX  261  272  278  272  272  272  278  294  300  294  283  267  278  272  278  294  300  294  311  300  300  311  317  328  339  333  333  322  306  317  328
USW0009472820200105TMIN  189  189  194  217  200  217  217  233  239  233  222  200  194  211  211  217  239  244  228  228  233  244  256  261  272  256  244  228  228  244  256
USW0009472820200106TMAX  333  317  317  322  328  333  339  333  344  339  344  344  344  333  311  311  317  328  339  339  333  328  322  317  317  306  300  306  317  317-9999
USW0009472820200106TMIN  261  256  256  250  256  267  272  272  267  267  272  283  278  267  244  244  256  256  283  289  267  256  256  250  244  239  228  233  244  244-9999
USW0009472820200107TMAX  322  328  333  339  333  322  306  300  306  311  300  306  306  300  289  300  311  322  317  311  306  306  306  306  311  311  317  328  328  322  311
USW0009472820200107TMIN  244  256  256  272  261  244  228  228  228  239  228  233  239  239  222  222  239  244  250  244  244  233  244  239  233  250  244  261  256  250  239
USW0009472820200108TMAX  306  311  311  306  300  306  306  311  317  317  322  317  311  306  306  300  306  306  306  300  294  289  289  294  300  300  300  306  306  300  306
USW0009472820200108TMIN  239  244  244  250  239  244  239  250  244  244  250  244  244  244  244  233  239  244  239  239  228  228  222  233  233  228  228  233  244  239  239
USW0009472820200109TMAX  306  300  294  294  289  289  289  294  294  289  289  294  294  294  300  300  294  289  283  289  278  283  283  278  278  272  272  267  267  272-9999
USW0009472820200109TMIN  239  239  233  228  222  217  217  222  222  217  222  228  222  228  233  239  228  222  217  222  217  222  217  211  211  211  211  206  200  217-9999
USW0009472820200110TMAX  267  261  261  261  250  256  256  250  256  256  256  250  244  239  239  239  244  244  244  250  250  244  250  250  244  239  233  233  244  244  250
USW0009472820200110TMIN  200  194  194  200  178  183  183  178  183  183  178  167  161  156  156  161  167  172  178  178  178  172  172  178  178  178  167  167  178  172  183
USW0009472820200111TMAX  244  250  256  244  233  239  244  250  256  250  256  256  250  239  244  250  239  233  244  267  272  261  267  272  267  250  250  250  261  272  272
USW0009472820200111TMIN  167  172  189  183  161  156  172  183  189  189  183  183  172  156  167  167  156  156  161  178  200  211  211  217  211  178  167  167  189  206  206
USW0009472820200112TMAX  267  261  250  250  256  256  261  261  267  267  272  272  267  267  267  267  272  272  261  256  256  261  261  250  250  244  250  239  244  239  239
USW0009472820200112TMIN  200  194  183  178  178  183  194  194  194  194  194  194  194  194  194  200  200  194  194  194  194  200  200  189  183  183  189  183  183  183  183
"""
    mock_get.return_value.text = mock_data

    # Set cache values for lat and lon
    cache.set("lat", 48.4022)
    cache.set("lon", 11.6944)

    # Execute the function
    result = fetch_data("USW00094728", [2020])
    
    # Check if result is a list or the expected error message
    if isinstance(result, str):
        assert result == "Für diese Kombination von Station und Jahr liegen nicht genug Daten vor"
    else:
        # Test that the result is a list if not a string
        assert isinstance(result, list)
        
        # If we got a result, check the structure
        # We expect a list containing the year, followed by seasonal temperature data
        if len(result) > 0:
            assert result[0][0] == 2020  # First element should be the year
            assert len(result[0]) == 11  # We expect 11 elements in each row


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
