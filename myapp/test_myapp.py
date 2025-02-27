import pytest
import os
import requests
from django.test import TestCase
from unittest.mock import patch, mock_open
from django.conf import settings
from django.test import RequestFactory
from myapp.views import distance, is_within_50km, check, fetch_data

@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected", [
    (500000, 800000, 500000, 800000, 0.0),  # Gleicher Punkt → Distanz = 0
    (500000, 800000, 500100, 800000, 11.1), # Ca. 11 km nach Norden
    (500000, 800000, 505000, 805000, 785.6) # Ca. 785 km entfernt
])
def test_distance(lat1, lon1, lat2, lon2, expected):
    result = distance(lat1, lon1, lat2, lon2)
    assert pytest.approx(result, rel=1e-2) == expected  # Toleranz ±1%

@pytest.mark.parametrize("lat1, lon1, lat2, lon2, expected", [
    (500000, 800000, 500100, 800000, True),   # 11 km → innerhalb 50 km
    (500000, 800000, 505000, 805000, False)   # 785 km → außerhalb 50 km
])
def test_is_within_50km(lat1, lon1, lat2, lon2, expected):
    assert is_within_50km(lat1, lon1, lat2, lon2) == expected

@patch("builtins.open", new_callable=mock_open, read_data="id,lat,lon,name\n1,500000,800000,TestStation\n")
@patch("os.path.join", return_value="dummy_path.csv")
def test_check(mock_join, mock_file):
    factory = RequestFactory()
    request = factory.post("/check", {"lat": "500000", "lon": "800000"})
    
    response = check(request)
    
    assert response.status_code == 200
    assert b"TestStation" in response.content  # Die Station sollte in der Antwort sein

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
    from myapp.views import is_within_radius
    assert is_within_radius(lat1, lon1, lat2, lon2, radius) == expected

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

