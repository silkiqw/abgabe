# Weather Data Analysis App

Eine Django-basierte Webanwendung zum Abrufen und Analysieren historischer Wetterdaten von Wetterstationen weltweit. Diese Anwendung wurde im Rahmen eines Hochschulprojekts entwickelt und ermöglicht es Benutzern, Wetterstationen in der Nähe eines bestimmten Standorts zu finden sowie Temperaturstatistiken für gewählte Zeiträume zu analysieren.

## Funktionen

- Suche nach Wetterstationen basierend auf geografischen Koordinaten
- Filterung der Stationen nach Entfernung und verfügbaren Daten für einen bestimmten Zeitraum
- Anzeige der durchschnittlichen Minimal- und Maximaltemperaturen nach Jahr und Jahreszeit

## Technologien

- Django 5.1
- Python 3.11
- Pandas für Datenanalyse
- Requests für HTTP-Anfragen
- Docker für Container-Deployment

## Installation

### Option 1: Installation mit Docker (empfohlen)

Die einfachste Möglichkeit, die Anwendung zu starten, ist über Docker:

#### Automatische Installation mit PowerShell (Windows)

1. Speichern Sie das Script `install-weather-app.ps1` aus diesem Repository
2. Öffnen Sie PowerShell
3. Führen Sie einen der folgenden Befehle aus:

   **Temporäre Bypass-Methode (empfohlen):**
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\install-weather-app.ps1
   ```
   
   **Alternative (falls Sie die Execution Policy dauerhaft ändern möchten):**
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   .\install-weather-app.ps1
   ```

#### Manuelle Docker-Installation

1. Ziehe das Docker-Image:
   ```bash
   docker pull ghcr.io/silkiqw/django-wetter-app:latest
   ```

2. Starte den Container:
   ```bash
   docker run -d -p 8000:8000 ghcr.io/silkiqw/django-wetter-app:latest
   ```

3. Öffne die Anwendung im Browser unter `http://localhost:8000/`



Führen Sie dann folgende Befehle aus:

```bash
docker build -t meine-wetter-app .
docker run -d -p 8000:8000 meine-wetter-app
```

### Option 2: Manuelle Installation

1. Klone das Repository:
   ```
   git clone https://github.com/your-username/weather-data-analysis-app.git
   cd weather-data-analysis-app
   ```

2. Erstelle eine virtuelle Umgebung und aktiviere sie:
   ```
   python -m venv venv
   source venv/bin/activate  # Unter Windows: venv\Scripts\activate
   ```

3. Installiere die Abhängigkeiten:
   ```
   pip install -r requirements.txt
   ```

4. Lade die Daten herunter:
   - Erstelle einen Ordner `data` im Projektverzeichnis
   - Lade die Dateien `ghcnd-stations.csv` und `stations.txt` herunter und speichere sie im `data`-Ordner
   - Die Dateien sind auf der NOAA-Website verfügbar: https://www1.ncdc.noaa.gov/pub/data/ghcn/daily/

5. Führe die Migrationen aus:
   ```
   python manage.py migrate
   ```

6. Starte den Entwicklungsserver:
   ```
   python manage.py runserver
   ```

7. Öffne die Anwendung im Browser unter `http://127.0.0.1:8000/`

## Nutzung

1. Gib die geografischen Koordinaten (Breitengrad und Längengrad) eines Ortes ein
2. Wähle den gewünschten Zeitraum und den Suchradius
3. Die Anwendung zeigt eine Liste von Wetterstationen in der Nähe
4. Wähle eine Station aus, um detaillierte Temperaturanalysen anzuzeigen
5. Die Ergebnisse enthalten durchschnittliche Minimal- und Maximaltemperaturen, aufgeschlüsselt nach Jahr und Jahreszeit

## Datenquellen

Die Anwendung verwendet Daten des Global Historical Climatology Network - Daily (GHCN-Daily) der National Oceanic and Atmospheric Administration (NOAA).

## Algorithmen

- **Haversine-Formel**: Zur Berechnung der Entfernung zwischen Koordinaten auf einer Kugel
- **Jahreszeitenbestimmung**: Dynamische Anpassung der Jahreszeitendefinition basierend auf der Halbkugel
- **Datenfilterung**: Entfernung unvollständiger Datensätze und Duplikate für präzise Analysen

## Dateien und Ordnerstruktur

- `project/` - Django-Projektordner
  - `settings.py` - Projekteinstellungen
  - `urls.py` - URL-Konfiguration
- `myapp/` - Hauptanwendungsordner
  - `views.py` - Enthält die Hauptlogik der Anwendung
  - `models.py` - Datenmodelle (nicht genutzt in dieser Version)
  - `templates/` - HTML-Vorlagen (index.html, result.html)
- `data/` - Speicherort für die heruntergeladenen Wetterdaten
- `manage.py` - Django-Verwaltungsskript
- `Dockerfile` - Konfiguration für Docker-Deployment
- `install-weather-app.ps1` - PowerShell-Script für automatische Docker-Installation unter Windows

## Mitwirkende

- Philipp Ott, Silas Kiehne
