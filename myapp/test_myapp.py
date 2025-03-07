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
from django.http import HttpResponse
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
    (500000, 800000, 500100, 800000, True),   # 11 km → innerhalb 50 km
    (500000, 800000, 505000, 805000, False)   # 785 km → außerhalb 50 km
])


# Tests für is_within_rad
class IsWithinRadTest(TestCase):
    def test_is_within_radius(self):
        self.assertTrue(is_within_rad(50.0, 10.0, 50.1, 10.1, 15))

    def test_is_outside_radius(self):
        self.assertFalse(is_within_rad(50.0, 10.0, 60.0, 20.0, 100))

# Tests für filter_duplicates
class FilterDuplicatesTest(TestCase):
    def test_filter_duplicates(self):
        input_list = [1, 2, 2, 3, 4, 4, 4]
        expected_output = [2, 2, 4, 4, 4]
        self.assertEqual(filter_duplicates(input_list), expected_output)

    def test_no_duplicates(self):
        input_list = [1, 2, 3]
        expected_output = []
        self.assertEqual(filter_duplicates(input_list), expected_output)

# Tests für remove_duplicates
class RemoveDuplicatesTest(TestCase):
    def test_remove_duplicates(self):
        input_list = [1, 2, 2, 3, 4, 4, 4]
        expected_output = [1, 2, 4]
        self.assertEqual(remove_duplicates(input_list), expected_output)

    def test_no_duplicates(self):
        input_list = [1, 2, 3]
        expected_output = [1, 2, 3]
        self.assertEqual(remove_duplicates(input_list), expected_output)

# Tests für get_names
class GetNamesTest(TestCase):
    @patch("myapp.views.get_name", side_effect=lambda x: f"Station {x}")
    def test_get_names(self, mock_get_name):
        input_list = [["1"], ["2"], ["3"]]
        expected_output = [["1", "Station 1"], ["2", "Station 2"], ["3", "Station 3"]]
        self.assertEqual(get_names(input_list), expected_output)

# Tests für read_stations
class ReadStationsTest(TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021")
    def test_read_stations(self, mock_file):
        expected_output = "ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021"
        self.assertEqual(read_stations(), expected_output)

    @patch("builtins.open", side_effect=Exception("Fehler beim Lesen der Datei"))
    def test_read_stations_error(self, mock_file):
        self.assertEqual(read_stations(), [])

# Tests für check
class CheckTest(TestCase):
    @patch("myapp.views.read_stations", return_value="ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021")
    @patch("myapp.views.is_within_rad", return_value=True)
    @patch("myapp.views.get_name", return_value="TestStation")
    def test_check_within_radius(self, mock_get_name, mock_is_within_rad, mock_read_stations):
        factory = RequestFactory()
        request = factory.post("/check", {
            "lat": "50.0",
            "lon": "10.0",
            "searchRadius": "100",
            "dateFrom": "2000-01-01",
            "dateTo": "2020-01-01"
        })
        response = check(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('result', response.context)
        self.assertEqual(response.context['result'], [["ID1", "TestStation"]])

    @patch("myapp.views.read_stations", return_value="ID1 50.0 10.0 TMAX 2000 2020\nID2 60.0 20.0 TMIN 2001 2021")
    @patch("myapp.views.is_within_rad", return_value=False)
    def test_check_outside_radius(self, mock_is_within_rad, mock_read_stations):
        factory = RequestFactory()
        request = factory.post("/check", {
            "lat": "50.0",
            "lon": "10.0",
            "searchRadius": "10",
            "dateFrom": "2000-01-01",
            "dateTo": "2020-01-01"
        })
        response = check(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn('result2', response.context)
        self.assertEqual(response.context['result2'], "Für diese Kombination von Koordinaten und Zeitraum gibt es nicht genügend Daten.")

# Tests für fetch_data
class FetchDataTest(TestCase):
    @patch("requests.get")
    def test_fetch_data(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.text = "2020 01 01 TMAX 100\n2020 01 02 TMIN 200"
        expected_output = [[2020, 10.0, 20.0, None, None, None, None, None, None, None, None]]
        self.assertEqual(fetch_data("ID1", [2020]), expected_output)

    @patch("requests.get")
    def test_fetch_data_error(self, mock_get):
        mock_get.return_value.status_code = 404
        with self.assertRaises(Exception):
            fetch_data("ID1", [2020])

# Tests für get_season
class GetSeasonTest(TestCase):
    def test_get_season_northern_hemisphere(self):
        self.assertEqual(get_season(3), "Spring")
        self.assertEqual(get_season(6), "Summer")
        self.assertEqual(get_season(9), "Fall")
        self.assertEqual(get_season(12), "Winter")

    def test_get_season_southern_hemisphere(self):
        with patch("myapp.views.cache.get", return_value=-50.0):
            self.assertEqual(get_season(3), "Fall")
            self.assertEqual(get_season(6), "Winter")
            self.assertEqual(get_season(9), "Spring")
            self.assertEqual(get_season(12), "Summer")

# Tests für get_name
class GetNameTest(TestCase):
    @patch("builtins.open", new_callable=mock_open, read_data="ID1,Name1\nID2,Name2")
    def test_get_name(self, mock_file):
        self.assertEqual(get_name("ID1"), "Name1")
        self.assertEqual(get_name("ID2"), "Name2")

    @patch("builtins.open", side_effect=Exception("Fehler beim Lesen der Datei"))
    def test_get_name_error(self, mock_file):
        self.assertIsNone(get_name("ID1"))
