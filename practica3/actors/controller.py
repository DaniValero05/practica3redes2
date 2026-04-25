# controller.py
import argparse
import sqlite3
import paho.mqtt.client as mqtt
from rule_engine import RuleEngine

GRUPO = "2303"
PAREJA = "02"
BASE_TOPIC = f"redes2/{GRUPO}/{PAREJA}"


# pylint: disable=too-many-instance-attributes
class Controller:
    """Controlador que gestiona la comunicación MQTT, verifica persistencia y aplica reglas."""

    def __init__(self, host, port, db_path):
        self.host = host
        self.port = port
        self.db_path = db_path
        self.rule_engine = RuleEngine(db_path)
        self.general_topic = f"{BASE_TOPIC}/#"

        self.client = mqtt.Client(client_id=f"controller_{GRUPO}_{PAREJA}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def is_device_registered(self, device_id):
        """Verifica si el dispositivo está registrado en la base de datos de Django."""
        try:
            # Establecemos conexión y tomamos el cursor para poder ejecutar la consulta SQL
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM app_device WHERE uid = ?", (device_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except sqlite3.Error:
            # Si la base de datos o tabla no existe, o hay un error, rechazamos por seguridad
            return False

    def log_event(self, device_id, event_type, description):
        """Guarda un evento en la tabla de Django usando SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # Nota: La tabla se llamará app_event (nombre_app + nombre_modelo)
            query = "INSERT INTO app_event (device_uid, event_type, description, timestamp) VALUES (?, ?, ?, datetime('now'))"
            cursor.execute(query, (device_id, event_type, description))
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"[!] Error al guardar evento: {e}")

    def on_connect(self, client, _userdata, _flags, rc):
        if rc == 0:
            print("Controlador conectado exitosamente al broker.")
            client.subscribe(self.general_topic, qos=1)
            print(f"Suscrito a: {self.general_topic}")
        else:
            print(f"Error al conectar. Código de resultado: {rc}")

    def on_message(self, client, _userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode("utf-8").strip()

        # Parseo del topic esperado (redes2/GRUPO/PAREJA/device_id[/subtopic])
        parts = topic.split("/")
        if len(parts) >= 4:
            device_id = parts[3]
            subtopic = parts[4] if len(parts) > 4 else ""

            # Evitar bucles: ignorar los mensajes de comandos (set) que nosotros publicamos
            if subtopic == "set":
                return

            # Verificación de seguridad: ¿Está dado de alta en Django?
            if not self.is_device_registered(device_id):
                print(
                    f"[!] Mensaje rechazado: Dispositivo '{device_id}' no registrado en persistencia."
                )
                # Opcionalmente puedes loguear el intento fallido
                # self.log_event(device_id, "ERROR", "Mensaje rechazado. Dispositivo no registrado.")
                return

            print(f"[+] Mensaje aceptado de '{device_id}' en {topic}: {payload}")

            # 1. Guardar evento de telemetría (historial de Django)
            self.log_event(device_id, "TELEMETRÍA", f"Valor recibido: {payload}")

            # 2. Desencadenar el motor de reglas para ver si este dato activa algo
            actions = self.rule_engine.process_event(device_id, payload)

            # 3. Ejecutar las acciones devueltas sobre los actuadores
            for act in actions:
                target_device = act.get("target")
                command = act.get("command")

                if target_device and command:
                    cmd_topic = f"{BASE_TOPIC}/{target_device}/set"
                    print(
                        f"[*] Ejecutando acción: publicando '{command}' en {cmd_topic}"
                    )

                    # Guardar el evento de la acción disparada
                    self.log_event(
                        target_device,
                        "ACCIÓN",
                        f"Orden '{command}' enviada por regla de {device_id}",
                    )

                    # Publicar el mensaje MQTT real para que el dummy-switch lo reciba
                    self.client.publish(cmd_topic, command, qos=1)

    def start(self):
        """Inicia el controlador."""
        print(f"Iniciando Controller MQTT [Grupo: {GRUPO} Pareja: {PAREJA}]")
        print(f"Broker: {self.host}:{self.port} | Database: {self.db_path}")
        print("-" * 50)

        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_forever()
        except ConnectionRefusedError:
            print(
                f"Error: Conexión rechazada. Asegura que el broker en {self.host} está en ejecución."
            )
        except KeyboardInterrupt:
            print("\n[*] Deteniendo controlador...")
            self.client.disconnect()


def main():
    """Punto de entrada de la aplicación de terminal."""
    parser = argparse.ArgumentParser(description="Aplicación Controller")
    parser.add_argument(
        "--host",
        "-H",
        type=str,
        default="redes2.ii.uam.es",
        help="Host del broker MQTT",
    )
    parser.add_argument(
        "--port", "-p", type=int, default=1883, help="Puerto del broker MQTT"
    )
    parser.add_argument(
        "--database",
        "-d",
        type=str,
        default="db.sqlite3",
        help="Nombre del fichero de la BD SQLite de Django",
    )

    args = parser.parse_args()

    controller = Controller(args.host, args.port, args.database)
    controller.start()


if __name__ == "__main__":
    main()
