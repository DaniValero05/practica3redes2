"""
Dispositivo IoT simulado que actúa como un interruptor (switch) controlable a través de MQTT.
Este dispositivo se conecta a un broker MQTT, publica su estado actual en un topic específico y responde a comandos para cambiar su estado (ON/OFF).
El dispositivo también tiene una probabilidad de fallo configurada, lo que significa que puede ignorar comandos de cambio de estado para simular un comportamiento no confiable.
"""

import argparse
import random
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"


# pylint: disable=too-many-instance-attributes
class DummySwitch:
    """
    Clase que representa un interruptor IoT simulado.
    Este dispositivo se conecta a un broker MQTT, publica su estado actual en un topic específico y responde a comandos para cambiar su estado (ON/OFF).
    El dispositivo también tiene una probabilidad de fallo configurada, lo que significa que puede ignorar comandos de cambio de estado para simular un comportamiento no confiable.
    """

    def __init__(self, host, port, probability, switch_id):
        """
        Inicializa el dispositivo Dummy Switch con la configuración proporcionada.

        Args:
            host (str): Host del broker MQTT.
            port (int): Puerto del broker MQTT.
            probability (float): Probabilidad de fallo (0.0 a 1.0) para ignorar comandos de cambio de estado.
            switch_id (str): Identificador único del dispositivo.

        Returns:
            None
        """
        self.host = host
        self.port = port
        self.probability = probability
        self.switch_id = switch_id
        self.current_state = "OFF"
        self.base_topic = f"redes2/{GRUPO}/{PAREJA}/{self.switch_id}"
        self.command_topic = f"{self.base_topic}/set"

        # Configuración del cliente MQTT con un client_id único basado en el grupo, pareja e ID del dispositivo
        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"switch_{GRUPO}_{PAREJA}_{self.switch_id}",
        )
        self.client.on_connect = self.on_connect  # Callback para conexión
        self.client.on_disconnect = self.on_disconnect  # Callback para desconexión
        self.client.on_message = self.on_message  # Callback para mensajes recibidos

    def on_connect(self, client, _userdata, _flags, rc, _properties):
        """
        Callback que se ejecuta al conectar con el broker.

        Args:
            client: El cliente MQTT.
            _userdata: Datos de usuario (no usados).
            _flags: Flags de conexión (no usados).
            rc: Código de resultado de la conexión (0 si es exitosa).

        Returns:
            None
        """
        if rc == 0:
            client.subscribe(
                self.command_topic, qos=1
            )  # Suscribimos al topic de comandos para recibir órdenes de cambio de estado
            client.subscribe(
                self.base_topic, qos=1
            )  # Suscribimos al topic principal para recibir peticiones de estado
            print(
                f"[SWITCH - {self.switch_id}] Conectado al broker MQTT y suscrito a los topics de comandos y estado."
            )
            client.publish(
                self.base_topic, self.current_state, qos=1, retain=True
            )  # Publicamos el estado inicial del interruptor al conectar
            print(
                f"[SWITCH - {self.switch_id}] ERROR: Fallo al conectar. Código de resultado: {rc}"
            )

    def on_disconnect(self, _client, _userdata, _flags, rc, _properties):
        """
        Callback que se ejecuta al desconectar del broker.

        Args:
            _client: El cliente MQTT.
            _userdata: Datos de usuario (no usados).
            _flags: Flags de desconexión (no usados).
            rc: Código de resultado de la desconexión (0 si es una desconexión limpia).
            _properties: Propiedades de la desconexión (no usadas).

        Returns:
            None
        """
        if rc != 0:
            print(
                f"[SWITCH - {self.switch_id}] ERROR: Desconectado inesperadamente. Código de resultado: {rc}"
            )
        else:
            print(f"[SWITCH - {self.switch_id}] Desconectado del broker.")

    def on_message(self, client, _userdata, msg):
        """
        Callback que se ejecuta al recibir un mensaje en un topic suscrito.

        Args:
            client: El cliente MQTT.
            _userdata: Datos de usuario (no usados).
            msg: El mensaje recibido, con atributos topic, payload, qos, retain, etc.

        Returns:
            None
        """
        payload = msg.payload.decode("utf-8").strip().upper()
        topic = msg.topic

        # Recibimos una orden para cambiar el estado
        if topic == self.command_topic:
            if random.random() < self.probability:
                print(
                    f"[SWITCH - {self.switch_id}] Fallo: El dispositivo ignoró la orden '{payload}'."
                )
                return

            if payload in ["ON", "OFF"]:
                if payload != self.current_state:
                    self.current_state = payload
                    print(
                        f"[SWITCH - {self.switch_id}] Estado cambiado a {self.current_state}. Publicando nuevo estado..."
                    )
                    client.publish(
                        self.base_topic, self.current_state, retain=True
                    )  # Publicamos el nuevo estado del interruptor
                else:
                    print(
                        f"[SWITCH - {self.switch_id}] El interruptor ya estaba en {self.current_state}."
                    )
            else:
                print(
                    f"[SWITCH - {self.switch_id}] Comando no reconocido: '{payload}'. Usa ON u OFF."
                )

        # Recibimos una consulta de estado en el topic principal
        elif topic == self.base_topic:
            if payload == "GET" or payload == "":
                print(
                    f"[SWITCH - {self.switch_id}] Petición de estado recibida. Respondiendo..."
                )
                client.publish(
                    self.base_topic, self.current_state, retain=True
                )  # Respondemos con el estado actual del interruptor

    def start(self):
        """
        Inicia la conexión y el bucle principal del interruptor.

        Returns:
            None
        """
        print(f"[SWITCH - {self.switch_id}] Iniciando Dummy Switch")
        print(
            f"[SWITCH - {self.switch_id}] Broker: {self.host}:{self.port} | Probabilidad de fallo: {self.probability * 100}%"
        )
        print("-" * 50)

        try:
            self.client.connect(self.host, self.port, 60)
            # Bucle infinito para mantener la conexión y procesar mensajes
            self.client.loop_forever()
        except ConnectionRefusedError:
            print(
                f"[SWITCH - {self.switch_id}] ERROR: Conexión rechazada. Asegura que el broker en {self.host} está en ejecución."
            )
        except KeyboardInterrupt:
            print(f"[SWITCH - {self.switch_id}] Deteniendo dispositivo...")
            self.client.disconnect()


def main():
    """Función principal que procesa los argumentos e inicia el dispositivo."""
    parser = argparse.ArgumentParser(description="Dispositivo IoT Dummy Switch")
    parser.add_argument(
        "--host", "-H", type=str, default="localhost", help="Host del broker MQTT"
    )  # Por defecto se conecta al broker local en localhost
    parser.add_argument(
        "--port", "-p", type=int, default=1883, help="Puerto del broker MQTT"
    )  # Por defecto se conecta al puerto estándar de MQTT 1883
    parser.add_argument(
        "--probability",
        "-P",
        type=float,
        default=0.3,
        help="Probabilidad de fallo (0.0 a 1.0)",
    )
    parser.add_argument("id", type=str, help="Identificador único del dispositivo")

    args = parser.parse_args()

    switch = DummySwitch(args.host, args.port, args.probability, args.id)
    switch.start()


if __name__ == "__main__":
    main()
