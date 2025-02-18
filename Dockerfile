# Basis-Image mit Python 3.9
FROM python:3.11

# Arbeitsverzeichnis im Container setzen
WORKDIR /app

# Abhängigkeiten kopieren und installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Den gesamten Code in den Container kopieren
COPY . .

# Port für Django freigeben (Standard für Django: 8000)
EXPOSE 8000

# Startbefehl für Django-Server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
