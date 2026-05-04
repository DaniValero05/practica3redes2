from django.apps import AppConfig
import sys
import os
import signal
import subprocess
from pathlib import Path


class AppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "app"

    def ready(self):
        if any(cmd in sys.argv for cmd in ("migrate", "makemigrations")):
            return

        if os.environ.get('RUN_MAIN') != 'true':
            return

        base = Path(__file__).resolve().parent
        actors = base.parent.parent / "actors"
        db = base.parent / "db.sqlite3"

        # Arrancamos el controlador
        subprocess.Popen([sys.executable, str(actors / "controller.py"), "--database", str(db)])

        try:
            from app.models import Device

            for device in Device.objects.all():
                # Matar el proceso anterior si sigue vivo
                if device.pid:
                    try:
                        os.kill(device.pid, signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):
                        pass
                    device.pid = None

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

                proc = subprocess.Popen(cmd)
                device.pid = proc.pid
                device.save(update_fields=['pid'])

        except Exception as e:
            print(f"[DJANGO] No se pudieron arrancar los actores: {e}")
