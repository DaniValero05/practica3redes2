"""
Dispositivo IoT Dummy Clock

Este script simula un dispositivo IoT que actúa como un reloj.
Publica la hora actual en un topic MQTT específico y responde a peticiones de estado.
"""

import argparse
import time
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"


# pylint: disable=too-many-instance-attributes
class DummyClock:
    """
    Clase que representa un dispositivo IoT Dummy Clock.
    Este dispositivo publica la hora actual en un topic MQTT específico y responde a peticiones de estado.

    Atributos:
        host (str): Host del broker MQTT.
        port (int): Puerto del broker MQTT.
        clock_id (str): Identificador único del dispositivo.
        increment (int): Incremento en segundos para avanzar el reloj virtual.
        rate (float): Frecuencia de envío en mensajes por segundo.
        current_time (datetime): Hora actual del reloj virtual.
        base_topic (str): Topic base para publicar el estado actual del reloj.
        client (mqtt.Client): Cliente MQTT para manejar la conexión y comunicación.
    """

    def __init__(self, host, port, clock_id, start_time_str=None, increment=1, rate=1):
        """
        Inicializa el dispositivo Dummy Clock con la configuración proporcionada.

        Args:
            host (str): Host del broker MQTT.
            port (int): Puerto del broker MQTT.
            clock_id (str): Identificador único del dispositivo.
            start_time_str (str, optional): Hora de inicio en formato HH:MM:SS
            increment (int, optional): Incremento en segundos para avanzar el reloj virtual. Por defecto es 1 segundo.
            rate (float, optional): Frecuencia de envío en mensajes por segundo. Por defecto es 1 msg/s.

        Returns:
            None
        """
        self.host = host
        self.port = port
        self.clock_id = clock_id
        self.increment = increment
        self.rate = rate

        # Inicializamos el reloj virtual con la hora de inicio proporcionada o con la hora actual del sistema
        if start_time_str is not None:
            self.current_time = datetime.strptime(start_time_str, "%H:%M:%S")
        else:
            self.current_time = datetime.now()

        self.base_topic = f"redes2/{GRUPO}/{PAREJA}/{self.clock_id}"

        # Configuración del cliente MQTT con la versión de API 2.0 y un client_id único basado en el grupo, pareja e ID del dispositivo
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"clock_{GRUPO}_{PAREJA}_{self.clock_id}",
        )
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, _userdata, _flags, rc, _properties):
        """
        Manejador de eventos para la conexión al broker MQTT.

        Args:
            client (mqtt.Client): El cliente MQTT que se ha conectado.
            _userdata: Datos de usuario (no utilizado).
            _flags: Flags de conexión (no utilizado).
            rc (int): Código de resultado de la conexión.
            _properties: Propiedades de la conexión (no utilizado).

        Returns:
            None
        """
        if rc == 0:
            client.subscribe(
                self.base_topic, qos=1
            )  # Suscribimos al topic para recibir peticiones de estado
            print(
                f"[CLOCK - {self.clock_id}] Conectado al broker MQTT y suscrito al topic de estado."
            )
        else:
            print(
                f"[CLOCK - {self.clock_id}] ERROR: Fallo al conectar. Código de resultado: {rc}"
            )

    def on_disconnect(self, _client, _userdata, _flags, rc, _properties):
        """
        Manejador de eventos para la desconexión del broker MQTT.

        Args:
            _client: El cliente MQTT que se ha desconectado.
            _userdata: Datos de usuario (no utilizado).
            _flags: Flags de desconexión (no utilizado).
            rc (int): Código de resultado de la desconexión.
            _properties: Propiedades de la desconexión (no utilizado).

        Returns:
            None
        """
        if rc != 0:
            print(
                f"[CLOCK - {self.clock_id}] ERROR: Desconectado inesperadamente. Código de resultado: {rc}"
            )
        else:
            print(f"[CLOCK - {self.clock_id}] Desconectado del broker de forma limpia.")

    def on_message(self, client, _userdata, msg):
        """
        Manejador de eventos para la recepción de mensajes en el topic suscrito.

        Args:
            client (mqtt.Client): El cliente MQTT que ha recibido el mensaje.
            _userdata: Datos de usuario (no utilizado).
            msg: El mensaje recibido, con atributos topic, payload, qos, retain, etc.

        Returns:
            None
        """
        payload = msg.payload.decode("utf-8").strip().upper()

        if payload == "GET" or payload == "":
            time_str = self.current_time.strftime("%H:%M:%S")
            print(
                f"[CLOCK - {self.clock_id}] Petición de estado recibida. Respondiendo..."
            )
            client.publish(
                self.base_topic, time_str, qos=1, retain=True
            )  # Respondemos con la hora actual del reloj virtual

    def start(self):
        """
        Inicia el dispositivo Dummy Clock, conectándose al broker MQTT y comenzando a publicar la hora actual.

        Returns:
            None
        """
        print(f"[CLOCK - {self.clock_id}] Iniciando Dummy Clock")
        print(
            f"Broker: {self.host}:{self.port} | Incremento: {self.increment}s | Tasa: {self.rate} msg/s"
        )
        print("-" * 50)

        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()

            # Calculamos el tiempo real de espera entre envíos
            sleep_time = 1.0 / self.rate

            while True:
                time_str = self.current_time.strftime("%H:%M:%S")
                print(f"[CLOCK - {self.clock_id}] Publicando hora: {time_str}")
                self.client.publish(self.base_topic, time_str, qos=1, retain=True)

                # Avanzamos el reloj virtual según el incremento configurado
                self.current_time += timedelta(seconds=self.increment)

                # Esperamos el tiempo real según la frecuencia configurada
                time.sleep(sleep_time)

        except ConnectionRefusedError:
            print(
                f"[CLOCK - {self.clock_id}] ERROR: Conexión rechazada. Asegura que el broker en {self.host} está en ejecución."
            )
        except KeyboardInterrupt:
            print(f"\n[CLOCK - {self.clock_id}] Deteniendo dispositivo...")
            self.client.loop_stop()
            self.client.disconnect()


def main():
    """
    Función principal que procesa los argumentos e inicia el dispositivo.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Dispositivo IoT Dummy Clock")
    parser.add_argument(
        "--host", "-H", type=str, default="localhost", help="Host del broker MQTT"
    )  # Por defecto se conecta al broker local en localhost
    parser.add_argument(
        "--port", "-p", type=int, default=1883, help="Puerto del broker MQTT"
    )  # Por defecto se conecta al puerto estándar de MQTT 1883
    parser.add_argument(
        "--time", type=str, default=None, help="Hora de inicio en formato HH:MM:SS"
    )
    parser.add_argument(
        "--increment",
        type=int,
        default=1,
        help="Incremento entre envíos en segundos del reloj virtual",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=1.0,
        help="Frecuencia de envío en mensajes por segundo",
    )
    parser.add_argument("id", type=str, help="Identificador único del dispositivo")

    args = parser.parse_args()

    if args.rate <= 0:
        print(
            "La tasa de envío debe ser un número positivo. Usando valor por defecto de 1 msg/s."
        )
        args.rate = 1.0

    clock = DummyClock(
        args.host, args.port, args.id, args.time, args.increment, args.rate
    )
    clock.start()


if __name__ == "__main__":
    main()
