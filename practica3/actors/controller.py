# controller.py
# El RuleEngine está integrado en este mismo fichero para evitar problemas
# de importación cuando se ejecuta el script desde directorios distintos.
# Si en el futuro se quiere separar, basta con mover la clase RuleEngine
# a rule_engine.py y sustituir la clase aquí por: from rule_engine import RuleEngine

import argparse
import sqlite3
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"
BASE_TOPIC = f"redes2/{GRUPO}/{PAREJA}"


# ══════════════════════════════════════════════════════════════════════════════
# Motor de reglas
# ══════════════════════════════════════════════════════════════════════════════

class RuleEngine:
    """
    Evalúa los eventos recibidos contra las reglas almacenadas en la BD de Django.
    Devuelve la lista de acciones a ejecutar sobre los actuadores.

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
            valor_recibido = float(payload)
        except ValueError:
            print(f"[RuleEngine] Payload '{payload}' no es numérico, ignorado.")
            return acciones

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            query = """
                SELECT r.operator, r.condition_value, d_target.uid, r.action_command
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

        for operador, cond_value, target_uid, command in reglas:
            cumplida = (
                (operador == "==" and valor_recibido == cond_value) or
                (operador == ">"  and valor_recibido >  cond_value) or
                (operador == "<"  and valor_recibido <  cond_value)
            )
            if cumplida:
                print(
                    f"[RuleEngine] Regla cumplida: "
                    f"si {device_id} {operador} {cond_value} → {target_uid} = {command}"
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

        self.client = mqtt.Client(client_id=f"controller_{GRUPO}_{PAREJA}")
        self.client.on_connect    = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message    = self.on_message

    # ── Persistencia ──────────────────────────────────────────────────────────

    def is_device_registered(self, device_id):
        """Devuelve True si el device_id existe en la tabla app_device de Django."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM app_device WHERE uid = ?", (device_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except sqlite3.Error:
            # BD no accesible → rechazamos por seguridad
            return False

    def log_event(self, device_id, event_type, description):
        """
        Inserta un evento en app_event.
        Usamos UTC explícito para ser coherentes con USE_TZ=True de Django.
        """
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

    def on_connect(self, client, _userdata, _flags, rc):
        if rc == 0:
            print("Controlador conectado al broker.")
            client.subscribe(self.general_topic, qos=1)
            print(f"Suscrito a: {self.general_topic}")
        else:
            print(f"Error al conectar. Código: {rc}")

    def on_disconnect(self, _client, _userdata, rc):
        if rc != 0:
            print(f"[!] Desconectado inesperadamente (código {rc}). Reconectando...")

    def on_message(self, client, _userdata, msg):
        topic   = msg.topic
        payload = msg.payload.decode("utf-8").strip()

        parts = topic.split("/")
        if len(parts) < 4:
            return

        device_id = parts[3]
        subtopic  = parts[4] if len(parts) > 4 else ""

        # Ignoramos los /set que nosotros mismos publicamos para evitar bucles
        if subtopic == "set":
            return

        # Seguridad: solo procesamos dispositivos registrados en Django
        if not self.is_device_registered(device_id):
            print(f"[!] Rechazado: '{device_id}' no está registrado.")
            return

        print(f"[+] '{device_id}' → {payload}")

        # 1. Persistir telemetría
        self.log_event(device_id, "TELEMETRÍA", f"Valor recibido: {payload}")

        # 2. Evaluar reglas
        actions = self.rule_engine.process_event(device_id, payload)

        # 3. Ejecutar acciones sobre actuadores
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
            # reconnect_delay_set permite reconexión automática ante caídas del broker
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
    parser = argparse.ArgumentParser(description="Controller del sistema domótico")
    parser.add_argument("--host", "-H", type=str, default="redes2.ii.uam.es",
                        help="Host del broker MQTT")
    parser.add_argument("--port", "-p", type=int, default=1883,
                        help="Puerto del broker MQTT")
    parser.add_argument("--database", "-d", type=str, default="db.sqlite3",
                        help="Ruta al fichero SQLite de Django")
    args = parser.parse_args()

    controller = Controller(args.host, args.port, args.database)
    controller.start()


if __name__ == "__main__":
    main()
