from django.apps import AppConfig


class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    def ready(self):
        #Verhindert doppeltes Ausführen beim Start
        if os.environ.get("RUN_MAIN") != "true":
            return  # Beendet die Funktion beim zweiten Aufruf
        #Lädt Startet Download der NOOA-DAten beim Start
        from .data_loader import download_stations
        download_stations()
