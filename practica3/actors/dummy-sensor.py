"""
Dispositivo IoT Dummy Sensor
Este script implementa un dispositivo IoT simulado que actúa como un sensor.
El dispositivo se conecta a un broker MQTT, publica su estado actual en un topic específico y responde a peticiones de estado.
"""

import argparse
import time
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"


# pylint: disable=too-many-instance-attributes
class DummySensor:
    """
    Clase que representa un sensor IoT simulado.
    Este dispositivo se conecta a un broker MQTT, publica su estado actual en un topic específico y responde a peticiones de estado.

    Atributos:
        host (str): Host del broker MQTT.
        port (int): Puerto del broker MQTT.
        sensor_id (str): Identificador único del dispositivo.
        interval (float): Tiempo en segundos tras los que simula un cambio de estado.
        send_min (int): Valor mínimo a enviar.
        send_max (int): Valor máximo a enviar.
        incr (int): Incremento entre el valor mínimo y máximo para simular cambios de estado
        current_value (int): Valor actual del sensor.
        base_topic (str): Topic base para publicar el estado actual del sensor.
        client (mqtt.Client): Cliente MQTT para manejar la conexión y comunicación.
    """

    def __init__(
        self, host, port, sensor_id, interval=1, send_min=20, send_max=30, incr=1
    ):
        """
        Inicializa el dispositivo Dummy Sensor con la configuración proporcionada.

        Args:
            host (str): Host del broker MQTT.
            port (int): Puerto del broker MQTT.
            sensor_id (str): Identificador único del dispositivo.
            interval (float, optional): Tiempo en segundos tras los que simula un cambio de estado
            send_min (int, optional): Valor mínimo a enviar. Por defecto es 20.
            send_max (int, optional): Valor máximo a enviar. Por defecto es 30.
            incr (int, optional): Incremento entre el valor mínimo y máximo para simular cambios

        Returns:
            None
        """
        self.host = host
        self.port = port
        self.interval = interval
        self.send_min = send_min
        self.send_max = send_max
        self.incr = incr
        self.sensor_id = sensor_id
        self.current_value = send_min
        self.base_topic = f"redes2/{GRUPO}/{PAREJA}/{self.sensor_id}"

        # Inicializamos el cliente MQTT y configuramos los callbacks
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sensor_{GRUPO}_{PAREJA}_{self.sensor_id}",
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, _userdata, _flags, rc, _properties):
        """
        Callback que se ejecuta al conectar al broker MQTT.
        Se suscribe al topic base para recibir peticiones de estado.

        Args:
            client (mqtt.Client): El cliente MQTT que se ha conectado.
            _userdata: Datos de usuario (no utilizado).
            _flags: Flags de conexión (no utilizado).
            rc: Código de resultado de la conexión.
            _properties: Propiedades de la conexión (no utilizado).

        Returns:
            None
        """
        if rc == 0:
            client.subscribe(
                self.base_topic, qos=1
            )  # Suscribimos al topic para recibir peticiones de estado
            print(
                f"[SENSOR - {self.sensor_id}] Conectado exitosamente al broker y suscrito a los topics."
            )
            client.publish(
                self.base_topic, str(self.current_value), qos=1, retain=True
            )  # Publicamos el estado inicial del sensor al conectar
        else:
            print(
                f"[SENSOR - {self.sensor_id}] ERROR: Fallo al conectar. Código de resultado: {rc}"
            )

    def on_disconnect(self, _client, _userdata, _flags, rc, _properties):
        """
        Callback que se ejecuta al desconectar del broker MQTT.

        Args:
            _client: El cliente MQTT que se ha desconectado.
            _userdata: Datos de usuario (no utilizado).
            _flags: Flags de desconexión (no utilizado).
            rc: Código de resultado de la desconexión.
            _properties: Propiedades de la desconexión (no utilizado).

        Returns:
            None
        """
        if rc != 0:
            print(
                f"[SENSOR - {self.sensor_id}] ERROR: Desconectado inesperadamente. Código de resultado: {rc}"
            )
        else:
            print(
                f"[SENSOR - {self.sensor_id}] Desconectado del broker de forma limpia."
            )

    def on_message(self, client, _userdata, msg):
        payload = msg.payload.decode("utf-8").strip().upper()

        if payload == "GET" or payload == "":
            print(
                f"[SENSOR - {self.sensor_id}] Petición de estado recibida. Respondiendo..."
            )
            client.publish(
                self.base_topic, str(self.current_value), qos=1, retain=True
            )  # Respondemos con el estado actual del sensor

    def start(self):
        """
        Inicia el dispositivo Dummy Sensor, conectándose al broker MQTT y comenzando a publicar su estado actual periódicamente.

        Returns:
            None
        """
        print(f"[SENSOR - {self.sensor_id}] Iniciando Dummy Sensor")
        print(
            f"[SENSOR - {self.sensor_id}] Broker: {self.host}:{self.port} | Intervalo: {self.interval}s | Rango: [{self.send_min}, {self.send_max}] | Incremento: {self.incr}"
        )
        print("-" * 50)

        try:
            # Nos conectamos al broker y comenzamos el bucle de procesamiento de mensajes
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()

            direccion = 1

            while True:
                print(
                    f"[SENSOR - {self.sensor_id}] Publicando estado: {self.current_value}"
                )
                self.client.publish(
                    self.base_topic, str(self.current_value), qos=1, retain=True
                )  # Publicamos el estado actual del sensor

                self.current_value += self.incr * direccion

                # Si alcanzamos el valor máximo o mínimo, invertimos la dirección del cambio
                if self.current_value >= self.send_max:
                    self.current_value = self.send_max
                    direccion = -1
                elif self.current_value <= self.send_min:
                    self.current_value = self.send_min
                    direccion = 1

                time.sleep(self.interval)

        except ConnectionRefusedError:
            print(
                f"[SENSOR - {self.sensor_id}] ERROR: Conexión rechazada. Asegura que el broker en {self.host} está en ejecución."
            )
        except KeyboardInterrupt:
            print(f"[SENSOR - {self.sensor_id}] Deteniendo dispositivo...")
            self.client.loop_stop()
            self.client.disconnect()


def main():
    """
    Función principal que procesa los argumentos e inicia el dispositivo.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Dispositivo IoT Dummy Sensor")
    parser.add_argument(
        "--host", "-H", type=str, default="localhost", help="Host del broker MQTT"
    )  # Por defecto se conecta al broker local en localhost
    parser.add_argument(
        "--port", "-p", type=int, default=1883, help="Puerto del broker MQTT"
    )  # Por defecto se conecta al puerto estándar de MQTT 1883
    parser.add_argument(
        "--interval",
        "-i",
        type=float,
        default=1.0,
        help="Tiempo en segundos tras los que simula un cambio de estado",
    )
    parser.add_argument(
        "--min", "-m", type=int, default=20, help="Valor mínimo a enviar"
    )
    parser.add_argument(
        "--max", "-M", type=int, default=30, help="Valor máximo a enviar"
    )
    parser.add_argument(
        "--increment", type=int, default=1, help="Incremento entre min y max"
    )
    parser.add_argument("id", type=str, help="Identificador único del dispositivo")

    args = parser.parse_args()

    sensor = DummySensor(
        args.host, args.port, args.id, args.interval, args.min, args.max, args.increment
    )
    sensor.start()


if __name__ == "__main__":
    main()
