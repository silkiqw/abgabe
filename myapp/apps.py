from django.apps import AppConfig
import os

class MyappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'myapp'

    def ready(self):
        
        if os.environ.get("RUN_MAIN") != "true":
            return  #prevent multiple downloads during start
        #automatic download during app start
        from .data_loader import download_stations
        download_stations()
