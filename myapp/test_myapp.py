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
from django.test import TestCase



