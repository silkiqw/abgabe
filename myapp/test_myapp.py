import pytest
import time
import subprocess
import re
import os
import requests
import django.core.cache as cache
from django.test import TestCase

from unittest.mock import patch, mock_open
from django.conf import settings
from django.test import RequestFactory
from myapp.views import (
    index,
    distance,
    is_within_rad,
    check,
    result,
    fetch_data,
    get_season
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
    (500000, 800000, 500000, 800000, 0.0),  # Gleicher Punkt → Distanz = 0
    (500000, 800000, 500100, 800000, 11.1), # Ca. 11 km nach Norden
    (500000, 800000, 505000, 805000, 785.6) # Ca. 785 km entfernt
])
def test_distance(lat1, lon1, lat2, lon2, expected):
    result = distance(lat1, lon1, lat2, lon2)
    assert pytest.approx(expected, rel=1e-2) == result

@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected", [
    (500000, 800000, 500100, 800000, True),   # 11 km → innerhalb 50 km
    (500000, 800000, 505000, 805000, False)   # 785 km → außerhalb 50 km
])


def mock_is_within_rad(lat1, lon1, lat2, lon2, r):
    # Test 1: Station innerhalb des Radius
    if int(r) == 50 and lat1 == "500000" and lon1 == "800000" and lat2 == "500000" and lon2 == "800000":
        return True
    # Test 2: Station außerhalb des Radius
    elif int(r) == 30 and lat1 == "500000" and lon1 == "800000" and lat2 == "500000" and lon2 == "800000":
        return False
    else:
        return True

@pytest.fixture
def mock_is_within_rad_function():
    with patch("myapp.views.is_within_rad", side_effect=mock_is_within_rad):
        yield

@patch("builtins.open", new_callable=mock_open, read_data="id,lat,lon,type,name\n1,500000,800000,X,TestStation\n")
@patch("os.path.join", return_value="dummy_path.csv")
@patch("django.core.cache.cache.set")
def test_check_inside_radius(mock_cache_set, mock_join, mock_file, mock_is_within_rad_function):
    """Test wenn die Station innerhalb des Radius liegt"""
    factory = RequestFactory()
    request = factory.post("/check", {
        "lat": "500000", 
        "lon": "800000",
        "searchRadius": "50",
        "dateFrom": "2020-01-01",
        "dateTo": "2022-01-01"
    })
    
    from myapp.views import check  # Importieren Sie die zu testende Funktion
    response = check(request)
    
    assert response.status_code == 200
    assert b"TestStation" in response.content
    
    mock_cache_set.assert_called_once()
    args, _ = mock_cache_set.call_args
    assert args[0] == "years"
    assert args[1] == [2020, 2021, 2022]

@patch("builtins.open", new_callable=mock_open, read_data="id,lat,lon,type,name\n1,500000,800000,X,TestStation\n")
@patch("os.path.join", return_value="dummy_path.csv")
@patch("django.core.cache.cache.set")
def test_check_outside_radius(mock_cache_set, mock_join, mock_file, mock_is_within_rad_function):
    """Test wenn die Station außerhalb des Radius liegt"""
    factory = RequestFactory()
    request = factory.post("/check", {
        "lat": "500000", 
        "lon": "800000",
        "searchRadius": "30",  # Kleinerer Radius, wird von mock_is_within_rad als außerhalb erkannt
        "dateFrom": "2020-01-01",
        "dateTo": "2022-01-01"
    })
    
    from myapp.views import check
    response = check(request)
    
    assert response.status_code == 200
    assert b"Keine Station gefunden" in response.content
    
    mock_cache_set.assert_called_once()

@patch("requests.get")
def test_fetch_data(mock_get):
    mock_get.return_value.status_code = 200
    mock_get.return_value.text = "TEST DATA"
    
    result = fetch_data("STATION123")
    
    assert result == "TEST DATA"
    mock_get.assert_called_with("https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/all/STATION123.dly")

@patch("requests.get")
def test_fetch_data_fail(mock_get):
    mock_get.return_value.status_code = 404
    
    with pytest.raises(Exception, match="Fehler beim Abrufen der Wetterdaten"):
        fetch_data("STATION123")

# Neue Tests für TDD

# 1. Test für variable Radiussuche
@pytest.mark.parametrize("lat1, lon1, lat2, lon2, radius, expected", [
    (500000, 800000, 500100, 800000, 10, False),   # 11 km ↛ innerhalb 10 km
    (500000, 800000, 500100, 800000, 20, True),    # 11 km → innerhalb 20 km
    (500000, 800000, 503000, 803000, 100, False),  # 470 km ↛ innerhalb 100 km
])
def test_is_within_radius(lat1, lon1, lat2, lon2, radius, expected):
    # Diese Funktion müssen wir noch implementieren
    from myapp.views import is_within_rad
    assert is_within_rad(lat1, lon1, lat2, lon2, radius) == expected

# 2. Test für Datenextraktion aus dem GHCN-Format
@pytest.fixture
def sample_ghcn_data():
    # Beispiel für GHCN-Dateiformat mit Temperaturdaten für ein Jahr
    return """
    USW000947282015TMAX  78  6  89  6 100  6 156  6 200  6 256  6 278  6 267  6 245  6 189  6 122  6  89  6
    USW000947282015TMIN -33  6 -22  6  11  6  67  6 111  6 167  6 189  6 183  6 150  6  89  6  33  6   0  6
    USW000947282016TMAX  83  6  94  6 106  6 161  6 206  6 261  6 283  6 272  6 250  6 194  6 128  6  94  6
    USW000947282016TMIN -28  6 -17  6  17  6  72  6 117  6 172  6 194  6 189  6 156  6  94  6  39  6   6  6
    """

def test_parse_ghcn_data(sample_ghcn_data):
    # Diese Funktion müssen wir noch implementieren
    from myapp.views import parse_ghcn_data
    parsed_data = parse_ghcn_data(sample_ghcn_data)
    
    # Prüfen der Jahre
    assert 2015 in parsed_data
    assert 2016 in parsed_data
    
    # Prüfen der Temperaturdaten für 2015
    assert parsed_data[2015]['TMAX'][0] == 7.8  # Januar (Wert geteilt durch 10)
    assert parsed_data[2015]['TMIN'][0] == -3.3  # Januar
    assert parsed_data[2015]['TMAX'][6] == 27.8  # Juli
    assert parsed_data[2015]['TMIN'][6] == 18.9  # Juli

# 3. Test für Berechnung der Jahresdurchschnittstemperaturen
def test_calculate_yearly_averages(sample_ghcn_data):
    # Diese Funktion müssen wir noch implementieren
    from myapp.views import parse_ghcn_data, calculate_yearly_averages
    parsed_data = parse_ghcn_data(sample_ghcn_data)
    yearly_averages = calculate_yearly_averages(parsed_data)
    
    # Prüfen der Jahreswerte für 2015
    assert 2015 in yearly_averages
    assert pytest.approx(yearly_averages[2015]['avg_tmax'], rel=1e-2) == 17.24  # Durchschnitt aller TMAX
    assert pytest.approx(yearly_averages[2015]['avg_tmin'], rel=1e-2) == 7.88   # Durchschnitt aller TMIN

# 4. Test für Berechnung der saisonalen Durchschnittstemperaturen
def test_calculate_seasonal_averages(sample_ghcn_data):
    # Diese Funktion müssen wir noch implementieren
    from myapp.views import parse_ghcn_data, calculate_seasonal_averages
    parsed_data = parse_ghcn_data(sample_ghcn_data)
    seasonal_averages = calculate_seasonal_averages(parsed_data)
    
    # Prüfen der Jahreszeitenwerte für 2015
    assert 2015 in seasonal_averages
    
    # Frühling (März-Mai)
    assert pytest.approx(seasonal_averages[2015]['spring_tmax'], rel=1e-2) == 15.2  # Durchschnitt März-Mai
    assert pytest.approx(seasonal_averages[2015]['spring_tmin'], rel=1e-2) == 6.3
    
    # Sommer (Juni-August)
    assert pytest.approx(seasonal_averages[2015]['summer_tmax'], rel=1e-2) == 26.7  # Durchschnitt Juni-August
    assert pytest.approx(seasonal_averages[2015]['summer_tmin'], rel=1e-2) == 17.97
    
    # Herbst (September-November)
    assert pytest.approx(seasonal_averages[2015]['autumn_tmax'], rel=1e-2) == 18.53
    assert pytest.approx(seasonal_averages[2015]['autumn_tmin'], rel=1e-2) == 9.07
    
    # Winter (Dezember-Februar)
    assert pytest.approx(seasonal_averages[2015]['winter_tmax'], rel=1e-2) == 8.53
    assert pytest.approx(seasonal_averages[2015]['winter_tmin'], rel=1e-2) == -1.83

# 5. Integration Test: Gesamter Prozess mit einer Station
@patch("myapp.views.fetch_data")
def test_result_view(mock_fetch_data, sample_ghcn_data):
    # Mock der fetch_data Funktion
    mock_fetch_data.return_value = sample_ghcn_data
    
    # Request simulieren
    factory = RequestFactory()
    request = factory.post("/result", {"station_id": "USW00094728"})
    
    # Antwort der View-Funktion erhalten
    response = result(request)
    
    # Prüfen, ob die Antwort korrekt ist
    assert response.status_code == 200
    
    # Wir erwarten, dass die Durchschnittstemperaturen in der Antwort enthalten sind
    # (Diese Prüfung hängt von der tatsächlichen Implementierung der result-Funktion ab)
    content = str(response.content)
    assert "2015" in content
    assert "2016" in content

# Beispiel-GHCN-Daten für die Südhalbkugel (z.B. Buenos Aires, Argentinien)
@pytest.fixture
def sample_ghcn_data_southern():
    # Gleiche Daten wie im vorhandenen Test, aber für eine südliche Station
    return """
    ARW000874082015TMAX  89  6 122  6 189  6 245  6 267  6 278  6 256  6 200  6 156  6 100  6  89  6  78  6
    ARW000874082015TMIN   0  6  33  6  89  6 150  6 183  6 189  6 167  6 111  6  67  6  11  6 -22  6 -33  6
    ARW000874082016TMAX  94  6 128  6 194  6 250  6 272  6 283  6 261  6 206  6 161  6 106  6  94  6  83  6
    ARW000874082016TMIN   6  6  39  6  94  6 156  6 189  6 194  6 172  6 117  6  72  6  17  6 -17  6 -28  6
    """

# Test für die Erkennung der Südhalbkugel basierend auf Koordinaten
@pytest.mark.parametrize("lat, lon, expected", [
    (40.7128, -74.0060, False),  # New York, Nordhalbkugel
    (-34.6037, -58.3816, True),  # Buenos Aires, Südhalbkugel
    (0.0, 0.0, False),           # Äquator, gilt als Nordhalbkugel
    (-0.0001, 0.0, True)         # Knapp südlich des Äquators
])
def test_is_southern_hemisphere(lat, lon, expected):
    # Diese Funktion müssen wir noch implementieren
    from myapp.views import is_southern_hemisphere
    assert is_southern_hemisphere(lat, lon) == expected

# Test für die Berechnung der Jahreszeiten auf der Südhalbkugel
def test_calculate_seasonal_averages_southern(sample_ghcn_data_southern):
    # Diese Funktion müssen wir noch implementieren
    from myapp.views import parse_ghcn_data, calculate_seasonal_averages
    
    # Latitude für Buenos Aires (Südhalbkugel)
    station_latitude = -34.6037
    
    parsed_data = parse_ghcn_data(sample_ghcn_data_southern)
    seasonal_averages = calculate_seasonal_averages(parsed_data, station_latitude)
    
    # Prüfen der Jahreszeitenwerte für 2015
    assert 2015 in seasonal_averages
    
    # Südhalbkugel Jahreszeiten:
    # Frühling (September-November)
    assert pytest.approx(seasonal_averages[2015]['spring_tmax'], rel=1e-2) == 18.53
    assert pytest.approx(seasonal_averages[2015]['spring_tmin'], rel=1e-2) == 9.07
    
    # Sommer (Dezember-Februar)
    assert pytest.approx(seasonal_averages[2015]['summer_tmax'], rel=1e-2) == 8.53
    assert pytest.approx(seasonal_averages[2015]['summer_tmin'], rel=1e-2) == -1.83
    
    # Herbst (März-Mai)
    assert pytest.approx(seasonal_averages[2015]['autumn_tmax'], rel=1e-2) == 15.2
    assert pytest.approx(seasonal_averages[2015]['autumn_tmin'], rel=1e-2) == 6.3
    
    # Winter (Juni-August)
    assert pytest.approx(seasonal_averages[2015]['winter_tmax'], rel=1e-2) == 26.7
    assert pytest.approx(seasonal_averages[2015]['winter_tmin'], rel=1e-2) == 17.97

# Integration Test: Test der verbesserten result-Funktion mit Berücksichtigung der Hemisphäre
@patch("myapp.views.fetch_data")
@patch("myapp.views.get_station_coordinates")
def test_result_view_with_hemisphere(mock_get_coords, mock_fetch_data, sample_ghcn_data_southern):
    # Mock-Daten für eine südliche Station
    mock_fetch_data.return_value = sample_ghcn_data_southern
    
    # Buenos Aires Koordinaten
    mock_get_coords.return_value = (-34.6037, -58.3816)
    
    # Request simulieren
    factory = RequestFactory()
    request = factory.post("/result", {"station_id": "ARW00087408"})
    
    # Antwort der View-Funktion erhalten
    from myapp.views import result
    response = result(request)
    
    # Prüfen, ob die Antwort korrekt ist
    assert response.status_code == 200
    
    content = str(response.content)
    
    # Prüfen ob die richtigen Jahreszeiten für die Südhalbkugel verwendet wurden
    assert "Südhalbkugel" in content
    
    # Hier könnten weitere spezifische Prüfungen für die Ausgabe erfolgen
    # z.B. ob der Sommer in Buenos Aires tatsächlich im Dezember-Februar liegt

