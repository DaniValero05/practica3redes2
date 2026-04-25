import argparse
import random
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"

#pylint: disable=too-many-instance-attributes
class DummySwitch:
    """Clase que representa un interruptor IoT simulado."""

    def __init__(self, host, port, probability, switch_id):
        self.host = host
        self.port = port
        self.probability = probability
        self.switch_id = switch_id
        self.current_state = "OFF"      
        self.base_topic = f"redes2/{GRUPO}/{PAREJA}/{self.switch_id}" # Topic base para publicar el estado actual del interruptor
        self.command_topic = f"{self.base_topic}/set" # Topic para recibir comandos de cambio de estado (ON/OFF)

        # Configuración del cliente MQTT
        self.client = mqtt.Client(client_id=f"switch_{GRUPO}_{PAREJA}_{self.switch_id}")
        self.client.on_connect = self.on_connect # Callback para conexión
        self.client.on_disconnect = self.on_disconnect # Callback para desconexión
        self.client.on_message = self.on_message # Callback para mensajes recibidos

    def on_connect(self, client, _userdata, _flags, rc):
        """Callback que se ejecuta al conectar con el broker.

        Args:
            client: El cliente MQTT.
            _userdata: Datos de usuario (no usados).
            _flags: Flags de conexión (no usados).
            rc: Código de resultado de la conexión (0 si es exitosa).
        """
        # Coomprobamos el return code enviado por el borker para verificar si la conexión fue exitosa
        if rc == 0:
            print("Conectado exitosamente al broker.")
            client.subscribe(self.command_topic, qos=1)
            client.subscribe(self.base_topic, qos=1)
            print("Suscrito a los topics")
            client.publish(self.base_topic, self.current_state,qos=1, retain=True) # retain: lo guarda en memoria 
        else:
            print(f"Error al conectar. Código de resultado: {rc}")

    def on_message(self, client, _userdata, msg):
        """Callback que se ejecuta al recibir un mensaje en un topic suscrito."""
        payload = msg.payload.decode('utf-8').strip().upper()
        topic = msg.topic
        
        # Recibimos una orden para cambiar el estado
        if topic == self.command_topic:
            if random.random() < self.probability:
                print(f"Fallo: El dispositivo ignoró la orden '{payload}'.")
                return
                
            if payload in ["ON", "OFF"]:
                if payload != self.current_state:
                    self.current_state = payload
                    print(f"Estado cambiado a {self.current_state}. Publicando nuevo estado...")
                    # Publicamos el nuevo estado en el topic base
                    client.publish(self.base_topic, self.current_state, retain=True)
                else:
                    print(f"El interruptor ya estaba en {self.current_state}.")
            else:
                print(f"Comando no reconocido: '{payload}'. Usa ON u OFF.")
                
        # Recibimos una consulta de estado en el topic principal
        elif topic == self.base_topic:
            if payload == "GET" or payload == "":
                print("\n[>] Petición de estado recibida. Respondiendo...")
                client.publish(self.base_topic, self.current_state, retain=True)

    def on_disconnect(self, _client, _userdata, rc):
        """Callback que se ejecuta al desconectar del broker."""
        if rc != 0:
            print(f"[!] Desconectado inesperadamente. Código de resultado: {rc}")
        else:
            print("[*] Desconectado del broker.")

    def start(self):
        """Inicia la conexión y el bucle principal del interruptor."""
        print(f"Iniciando Dummy Switch [ID: {self.switch_id}]")
        print(f"Broker: {self.host}:{self.port} | Probabilidad de fallo: {self.probability * 100}%")
        print("-" * 50)
        
        try:
            self.client.connect(self.host, self.port, 60)
            # Bucle infinito para mantener la conexión y procesar mensajes
            self.client.loop_forever()
        except ConnectionRefusedError:
            print(f"Error: Conexión rechazada. Asegura que el broker en {self.host} está en ejecución.")
        except KeyboardInterrupt:
            print("\n[*] Deteniendo dispositivo...")
            self.client.disconnect()


def main():
    """Función principal que procesa los argumentos e inicia el dispositivo."""
    # Lectura de argumentos por línea de comandos
    parser = argparse.ArgumentParser(description="Dispositivo IoT Dummy Switch")
    parser.add_argument("--host", "-H", type=str, default="redes2.ii.uam.es", help="Host del broker MQTT")
    parser.add_argument("--port", "-p", type=int, default=1883, help="Puerto del broker MQTT")
    parser.add_argument("--probability", "-P", type=float, default=0.3, help="Probabilidad de fallo (0.0 a 1.0)")
    parser.add_argument("id", type=str, help="Identificador único del dispositivo")
    
    args = parser.parse_args()
    
    # Instanciamos la clase y la arrancamos
    switch = DummySwitch(args.host, args.port, args.probability, args.id)
    switch.start()

if __name__ == "__main__":
    main()