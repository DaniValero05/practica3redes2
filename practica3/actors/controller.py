"""
Archivo que implementa el controlador central del sistema y la gestión de reglas.

Esta archivo gestiona dos clases principales:
- RuleEngine: Evalúa las reglas almacenadas en la base de datos de Django contra los eventos recibidos 
              de los dispositivos. Soporta condiciones numéricas y de tiempo.
- Controller: Se suscribe a los mensajes MQTT de los dispositivos, persiste los eventos en la base de datos y delega
              en el RuleEngine para determinar si se deben enviar comandos a otros dispositivos. También maneja la conexión
              al broker MQTT y la persistencia de eventos en la base de datos.
"""

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
    """
    Convierte una cadena de tiempo "HH:MM:SS" a segundos desde medianoche.

    Args:
        time_str (str): Cadena de tiempo en formato "HH:MM:SS"

    Returns:
        int: Hora pasada en segundos, o None si el formato es inválido.
    """
    try:
        t = datetime.strptime(time_str.strip(), "%H:%M:%S")
        return t.hour * 3600 + t.minute * 60 + t.second
    except ValueError:
        return None


class RuleEngine:
    """
    Procesa eventos de dispositivos y evalúa las reglas definidas en la base de datos de Django.

    Atributos:
        db_path (str): Ruta al fichero SQLite de Django para acceder a las tablas de reglas
    """

    def __init__(self, db_path):
        """
        Inicializa el motor de reglas con la ruta a la base de datos.

        Args:
            db_path (str): Ruta al fichero SQLite de Django
        """
        self.db_path = db_path

    def process_event(self, device_id, payload):
        """
        Comprueba todas las reglas cuyo dispositivo detonante coincide con device_id.

        Args:
            device_id (str): El UID del dispositivo que generó el evento
            payload (str): El valor recibido del dispositivo
        """
        print(f"[RULE_ENGINE] Evaluando evento de '{device_id}': {payload}")
        acciones = []

        try:
            conn = sqlite3.connect(self.db_path) # Conexión a la base de datos de Django
            cursor = conn.cursor() # Cursor para ejecutar consultas SQL
            query = """
                SELECT r.operator, r.condition_type, r.condition_value, r.condition_time,
                       d_target.uid, r.action_command
                FROM app_rule r
                JOIN app_device d_trigger ON r.trigger_device_id = d_trigger.id
                JOIN app_device d_target  ON r.target_device_id  = d_target.id
                WHERE d_trigger.uid = ?
            """
            cursor.execute(query, (device_id,)) # Ejecuta la consulta para obtener las reglas que se disparan con el device_id
            reglas = cursor.fetchall()# Obtiene todas las reglas que coinciden con el dispositivo detonante
            conn.close()
        except sqlite3.Error as e:
            print(f"[RULE_ENGINE] Error accediendo a la BD: {e}")
            return acciones

        for operador, cond_type, cond_value, cond_time, target_uid, command in reglas:
            cumplida = False

            # Evaluación de la condición según el tipo de regla
            if cond_type == "time":
                # Convertimos el payload y la condición a segundos para compararlos
                payload_secs = _time_to_seconds(payload)
                cond_secs = _time_to_seconds(cond_time) if cond_time else None
                
                # Si alguna de las conversiones falla, ignoramos esta regla
                if payload_secs is None or cond_secs is None:
                    print(f"[RULE_ENGINE] Payload '{payload}' o condición '{cond_time}' no son horas válidas, ignorado.")
                    continue

                cumplida = (
                    (operador == "==" and payload_secs == cond_secs) or
                    (operador == ">"  and payload_secs >  cond_secs) or
                    (operador == "<"  and payload_secs <  cond_secs)
                )
                # Para mostrar en el log, usamos la forma original de la condición de tiempo
                cond_display = cond_time

            else:
                try:
                    valor_recibido = float(payload)
                except ValueError:
                    print(f"[RULE_ENGINE] Payload '{payload}' no es numérico, ignorado.")
                    continue

                if cond_value is None:
                    print(f"[RULE_ENGINE] Regla numérica sin condition_value. Ignorando.")
                    continue

                cumplida = (
                    (operador == "==" and valor_recibido == cond_value) or
                    (operador == ">"  and valor_recibido >  cond_value) or
                    (operador == "<"  and valor_recibido <  cond_value)
                )
                cond_display = cond_value

            if cumplida:
                print(
                    f"[RULE_ENGINE] Regla cumplida: si {device_id} {operador} {cond_display} --> {target_uid} = {command}"
                )
                # Si la regla se cumple, añadimos la acción a la lista de acciones a ejecutar
                acciones.append({"target": target_uid, "command": command})

        return acciones


# ═════════════════════════════════════════════════════════════════════════════
# Controlador principal
# ═════════════════════════════════════════════════════════════════════════════

class Controller:
    """
    Recibe mensajes MQTT de los dispositivos registrados, los persiste como
    eventos y delega en el RuleEngine para determinar si hay que actuar.

    Atributos:
        host (str): Host del broker MQTT
        port (int): Puerto del broker MQTT
        db_path (str): Ruta al fichero SQLite de Django para acceder a las tablas de dispositivos y eventos
        rule_engine (RuleEngine): Instancia del motor de reglas para evaluar las reglas
        general_topic (str): Tema MQTT general para suscribirse a todos los mensajes de dispositivos
        client (mqtt.Client): Cliente MQTT para manejar la conexión y mensajes
    """

    def __init__(self, host, port, db_path):
        """
        Inicializa el controlador con los parámetros de conexión y la ruta a la base de datos.

        Args:
            host (str): Host del broker MQTT
            port (int): Puerto del broker MQTT
            db_path (str): Ruta al fichero SQLite de Django
        """
        self.host = host
        self.port = port
        self.db_path = db_path
        self.rule_engine = RuleEngine(db_path)
        self.general_topic = f"{BASE_TOPIC}/#"

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"controller_{GRUPO}_{PAREJA}")
        self.client.on_connect    = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message    = self.on_message

    # Persistencia

    def is_device_registered(self, device_id):
        """
        Funcion encargada de verificar si un dispositivo con el UID dado está registrado en la base de datos de Django.

        Args:
            device_id (str): El UID del dispositivo a verificar

        Returns:
            bool: True si el dispositivo está registrado, False en caso contrario
        """
        try:
            # Establecemos conexión y el cursor de la base de datos SQLite de Django
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM app_device WHERE uid = ?", (device_id,))
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except sqlite3.Error as e:
            print(f"[CONTROLADOR] Error de base de datos: {e}")
            return False

    def log_event(self, device_id, event_type, description):
        """
        Inserta un evento en app_event.

        Args:
                device_id (str): El UID del dispositivo que generó el evento
                event_type (str): El tipo de evento:"MEDICIÓN", "ACCIÓN"
                description (str): Descripción del evento
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
            print(f"[CONTROLADOR] Error al guardar evento: {e}")

    # Callbacks MQTT 

    def on_connect(self, client, _userdata, _flags, rc, _properties):
        # Comprobamos el código de retorno para verificar si la conexión fue exitosa
        if rc == 0:
            print(f"[CONTROLADOR] Conectado al broker.")
            client.subscribe(self.general_topic, qos=1)
            print(f"[CONTROLADOR] Suscrito a: {self.general_topic}")
        else:
            print(f"[CONTROLADOR] Error al conectar. Código: {rc}")

    def on_disconnect(self, _client, _userdata, _flags, rc, _properties):
        if rc != 0:
            print(f"[CONTROLADOR] Desconectado inesperadamente (código {rc})")

    def on_message(self, client, _userdata, msg):
        # Extraemos el topic y el payload del mensaje MQTT recibido
        topic   = msg.topic
        payload = msg.payload.decode("utf-8").strip()

        print(f"[CONTROLADOR] Mensaje recibido en '{topic}': {payload}")

        # Separamos el topic para extraer el device_id y el subtopic
        parts = topic.split("/")
        if len(parts) < 4:
            print(f"[CONTROLADOR] Topic inválido: {topic}")
            return

        device_id = parts[3]
        subtopic  = parts[4] if len(parts) > 4 else ""

        # El cotrolador no debe procesar lo mensajes que el mismo ha mandado para cambiar el estado de un dispositivo
        if subtopic == "set":
            return

        # Comprobamos si el dispositivo que envío el mensaje está en la base de datos
        if not self.is_device_registered(device_id):
            print(f"[CONTROLADOR] Rechazado: '{device_id}' no está registrado.")
            return

        # Guardamos el evento en la base de datos
        self.log_event(device_id, "MEDICIÓN", payload)

        # Pricesamos el evento y vemos que acciones se deben ejecutar en función de las reglas definidas
        actions = self.rule_engine.process_event(device_id, payload)

        # Ejecutamos las acciones
        for act in actions:
            target  = act.get("target")
            command = act.get("command")
            if target and command:
                topic = f"{BASE_TOPIC}/{target}/set"
                print(f"[CONTROLADOR] Acción: publicando '{command}' en {topic}")
                # Guardamos el evento en la base de datos
                self.log_event(target, "ACCIÓN", command)
                # Mandamos la petición por el topic correspondiente
                client.publish(topic, command, qos=1)

    # Arranque

    def start(self):
        print(f"[CONTROLADOR] Iniciando Controller [Grupo: {GRUPO}  Pareja: {PAREJA}]")
        print(f"Broker: {self.host}:{self.port}  |  BD: {self.db_path}")
        print("-" * 50)
        try:
            # Nos conectamos al servidor MQTT
            self.client.connect(self.host, self.port, keepalive=60)
            self.client.reconnect_delay_set(min_delay=1, max_delay=30)
            # Mantemos al controlador escuchando eventos
            self.client.loop_forever(retry_first_connection=False)
        except ConnectionRefusedError:
            print(f"[CONTROLADOR] Error: el broker en {self.host}:{self.port} rechazó la conexión.")
        except KeyboardInterrupt:
            print(f"[CONTROLADOR] Deteniendo controlador...")
            self.client.disconnect()



# Inicio 

def main():
    # Tomamos la ruta actual para establecer la ruta de la BD correctamente
    dir = os.path.dirname(os.path.abspath(__file__))
    default_db_path = os.path.abspath(os.path.join(dir, "..", "project", "db.sqlite3"))

    # Parseamos los argumentos
    parser = argparse.ArgumentParser(description="Controlador del sistema domótico")
    parser.add_argument("--host", "-H", type=str, default="localhost",
                        help="Host del broker MQTT")
    parser.add_argument("--port", "-p", type=int, default=1883,
                        help="Puerto del broker MQTT")
    parser.add_argument("--database", "-d", type=str, default=default_db_path,
                        help="Ruta al fichero SQLite de Django")
    args = parser.parse_args()

    # Creamos una instancia del controller y lo inicializamos
    controller = Controller(args.host, args.port, args.database)
    controller.start()


if __name__ == "__main__":
    main()
