# controller.py
# El RuleEngine está integrado en este mismo fichero para evitar problemas
# de importación cuando se ejecuta el script desde directorios distintos.

import argparse
import os
import sqlite3
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"
BASE_TOPIC = f"redes2/{GRUPO}/{PAREJA}"


# ══════════════════════════════════════════════════════════════════════════════
# Motor de reglas
# ══════════════════════════════════════════════════════════════════════════════

def _time_to_seconds(time_str):
    """Convierte HH:MM:SS a segundos totales desde medianoche."""
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M:%S")
        return t.hour * 3600 + t.minute * 60 + t.second
    except ValueError:
        return None


class RuleEngine:
    """
    Evalúa los eventos recibidos contra las reglas almacenadas en la BD de Django.
    Soporta condiciones numéricas y de hora (HH:MM:SS).

    Operadores soportados: ==, >, <
    """

    def __init__(self, db_path):
        self.db_path = db_path

    def process_event(self, device_id, payload):
        """
        Comprueba todas las reglas cuyo trigger_device coincide con device_id.
        Retorna una lista de dicts: [{"target": uid, "command": cmd}, ...]
        """
        print(f"[RuleEngine] Evaluando evento de '{device_id}': {payload}")
        acciones = []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            query = """
                SELECT r.operator, r.condition_type, r.condition_value, r.condition_time,
                       d_target.uid, r.action_command
                FROM app_rule r
                JOIN app_device d_trigger ON r.trigger_device_id = d_trigger.id
                JOIN app_device d_target  ON r.target_device_id  = d_target.id
                WHERE d_trigger.uid = ?
            """
            cursor.execute(query, (device_id,))
            reglas = cursor.fetchall()
            conn.close()
        except sqlite3.Error as e:
            print(f"[RuleEngine] Error accediendo a la BD: {e}")
            return acciones

        for operador, cond_type, cond_value, cond_time, target_uid, command in reglas:
            cumplida = False

            if cond_type == "time":
                payload_secs = _time_to_seconds(payload)
                cond_secs = _time_to_seconds(cond_time) if cond_time else None

                if payload_secs is None or cond_secs is None:
                    print(f"[RuleEngine] Payload '{payload}' o condición '{cond_time}' no son horas válidas, ignorado.")
                    continue

                cumplida = (
                    (operador == "==" and payload_secs == cond_secs) or
                    (operador == ">"  and payload_secs >  cond_secs) or
                    (operador == "<"  and payload_secs <  cond_secs)
                )
                cond_display = cond_time

            else:
                try:
                    valor_recibido = float(payload)
                except ValueError:
                    print(f"[RuleEngine] Payload '{payload}' no es numérico, ignorado.")
                    continue

                if cond_value is None:
                    print(f"[RuleEngine] Regla numérica sin condition_value. Ignorando.")
                    continue

                cumplida = (
                    (operador == "==" and valor_recibido == cond_value) or
                    (operador == ">"  and valor_recibido >  cond_value) or
                    (operador == "<"  and valor_recibido <  cond_value)
                )
                cond_display = cond_value

            if cumplida:
                print(
                    f"[RuleEngine] Regla cumplida: "
                    f"si {device_id} {operador} {cond_display} → {target_uid} = {command}"
                )
                acciones.append({"target": target_uid, "command": command})

        return acciones


# ══════════════════════════════════════════════════════════════════════════════
# Controlador principal
# ══════════════════════════════════════════════════════════════════════════════

class Controller:
    """
    Recibe mensajes MQTT de los dispositivos registrados, los persiste como
    eventos y delega en el RuleEngine para determinar si hay que actuar.
    """

    def __init__(self, host, port, db_path):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.rule_engine = RuleEngine(db_path)
        self.general_topic = f"{BASE_TOPIC}/#"

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"controller_{GRUPO}_{PAREJA}")
        self.client.on_connect    = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message    = self.on_message

    # ── Persistencia ──────────────────────────────────────────────────────────

    def is_device_registered(self, device_id):
        """Devuelve True si el device_id existe en la tabla app_device de Django."""
        try:
            print(f"\n[DEBUG] Comprobando DB en ruta: {self.db_path}")

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM app_device")
            todos = cursor.fetchall()
            print(f"[DEBUG] Contenido total de app_device: {todos}")

            cursor.execute("SELECT id FROM app_device WHERE uid = ?", (device_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except sqlite3.Error as e:
            print(f"[DEBUG] Error de base de datos: {e}")
            return False

    def log_event(self, device_id, event_type, description):
        """Inserta un evento en app_event."""
        try:
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO app_event (device_uid, event_type, description, timestamp) "
                "VALUES (?, ?, ?, ?)",
                (device_id, event_type, description, now_utc),
            )
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"[!] Error al guardar evento: {e}")

    # ── Callbacks MQTT ────────────────────────────────────────────────────────

    def on_connect(self, client, _userdata, _flags, rc, _properties):
        if rc == 0:
            print("Controlador conectado al broker.")
            client.subscribe(self.general_topic, qos=1)
            print(f"Suscrito a: {self.general_topic}")
        else:
            print(f"Error al conectar. Código: {rc}")

    def on_disconnect(self, _client, _userdata, _flags, rc, _properties):
        if rc != 0:
            print(f"[!] Desconectado inesperadamente (código {rc}). Reconectando...")

    def on_message(self, client, _userdata, msg):
        topic   = msg.topic
        payload = msg.payload.decode("utf-8").strip()

        print(f"\n[MQTT] Mensaje recibido en '{topic}': {payload}")

        parts = topic.split("/")
        if len(parts) < 4:
            return

        device_id = parts[3]
        subtopic  = parts[4] if len(parts) > 4 else ""

        if subtopic == "set":
            return

        if not self.is_device_registered(device_id):
            print(f"[!] Rechazado: '{device_id}' no está registrado.")
            return

        print(f"[+] '{device_id}' → {payload}")

        self.log_event(device_id, "TELEMETRÍA", f"Valor recibido: {payload}")

        actions = self.rule_engine.process_event(device_id, payload)

        for act in actions:
            target  = act.get("target")
            command = act.get("command")
            if target and command:
                cmd_topic = f"{BASE_TOPIC}/{target}/set"
                print(f"[*] Acción: publicando '{command}' en {cmd_topic}")
                self.log_event(
                    target, "ACCIÓN",
                    f"Orden '{command}' enviada por regla disparada por {device_id}",
                )
                client.publish(cmd_topic, command, qos=1)

    # ── Arranque ──────────────────────────────────────────────────────────────

    def start(self):
        print(f"Iniciando Controller [Grupo: {GRUPO}  Pareja: {PAREJA}]")
        print(f"Broker: {self.host}:{self.port}  |  BD: {self.db_path}")
        print("-" * 50)
        try:
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.reconnect_delay_set(min_delay=1, max_delay=30)
            self.client.loop_forever(retry_first_connection=False)
        except ConnectionRefusedError:
            print(f"Error: el broker en {self.host}:{self.port} rechazó la conexión.")
        except KeyboardInterrupt:
            print("\n[*] Deteniendo controlador...")
            self.client.disconnect()


# ══════════════════════════════════════════════════════════════════════════════
# Punto de entrada
# ══════════════════════════════════════════════════════════════════════════════

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_db_path = os.path.abspath(os.path.join(script_dir, "..", "project", "db.sqlite3"))

    parser = argparse.ArgumentParser(description="Controller del sistema domótico")
    parser.add_argument("--host", "-H", type=str, default="localhost",
                        help="Host del broker MQTT")
    parser.add_argument("--port", "-p", type=int, default=1883,
                        help="Puerto del broker MQTT")
    parser.add_argument("--database", "-d", type=str, default=default_db_path,
                        help="Ruta al fichero SQLite de Django")
    args = parser.parse_args()

    controller = Controller(args.host, args.port, args.database)
    controller.start()


if __name__ == "__main__":
    main()
