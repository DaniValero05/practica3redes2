from django.apps import AppConfig
import sys
import os
import subprocess
from pathlib import Path

class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        # 1. Evitar ejecución durante comandos de migración
        if any(cmd in sys.argv for cmd in ("migrate", "makemigrations")):
            return

        # 2. Evitar la doble ejecución por el reloader de Django
        if os.environ.get('RUN_MAIN') != 'true':
            return

        # Rutas relativas usando Pathlib
        base = Path(__file__).resolve().parent
        actors = base.parent.parent / "actors"
        db = base.parent / "db.sqlite3"

        # 3. Iniciar el Controlador
        subprocess.Popen([
            sys.executable, 
            str(actors / "controller.py"), 
            "--database", 
            str(db)
        ])

        # 4. Iniciar Dispositivos ya registrados en la BD
        try:
            from app.models import Device
            
            for device in Device.objects.all():
                if device.device_type == "sensor":
                    cmd = [
                        sys.executable, str(actors / "dummy-sensor.py"),
                        "--host", device.host or "localhost",
                        "--port", str(device.port or 1883),
                        "--min", str(device.min_value or 20),
                        "--max", str(device.max_value or 30),
                        "--increment", str(device.sensor_increment or 1),
                        "--interval", str(device.interval or 1),
                        device.uid
                    ]
                elif device.device_type == "switch":
                    cmd = [
                        sys.executable, str(actors / "dummy-switch.py"),
                        "--host", device.host or "localhost",
                        "--port", str(device.port or 1883),
                        "--probability", str(device.probability or 0.0),
                        device.uid
                    ]
                elif device.device_type == "clock":
                    cmd = [
                        sys.executable, str(actors / "dummy-clock.py"),
                        "--host", device.host or "localhost",
                        "--port", str(device.port or 1883),
                        "--increment", str(device.clock_increment or 1),
                        "--rate", str(device.rate or 1.0),
                        device.uid
                    ]
                    if device.start_time:
                        cmd += ["--time", str(device.start_time)]
                else:
                    continue

                # Ejecutamos el script del actor en segundo plano
                subprocess.Popen(cmd)
                
        except Exception as e:
            # Si la base de datos no está lista, lo notificamos sin tirar el servidor
            print(f"[DJANGO] No se pudieron arrancar los actores: {e}")