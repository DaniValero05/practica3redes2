import argparse
import time
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"

#pylint: disable=too-many-instance-attributes
class DummySensor:
    """Clase que representa un sensor IoT simulado."""

    def __init__(self, host, port, sensor_id, interval=1, send_min=20, send_max=30, incr=1):
        self.host = host
        self.port = port
        self.interval = interval
        self.send_min = send_min
        self.send_max = send_max
        self.incr = incr
        self.sensor_id = sensor_id
        self.current_value = send_min
        self.base_topic = f"redes2/{GRUPO}/{PAREJA}/{self.sensor_id}" # Topic base para publicar el estado actual del sensor

        # Configuración del cliente MQTT
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sensor_{GRUPO}_{PAREJA}_{self.sensor_id}")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, _userdata, _flags, rc, _properties):
        if rc == 0:
            # Al suscrbirnos el broker creará esos canales si no existen
            print("Conectado exitosamente al broker.")
            client.subscribe(self.base_topic, qos=1)
            print("Suscrito a los topics")
            client.publish(self.base_topic, str(self.current_value), qos=1, retain=True)
        else:
            print(f"Error al conectar. Código de resultado: {rc}")

    def on_disconnect(self, _client, _userdata, _flags,  rc, _properties):
        if rc != 0:
            print(f"Desconectado inesperadamente. Código de resultado: {rc}")
        else:
            print("Desconectado del broker de forma limpia.") 

    def on_message(self, client, _userdata, msg):
        payload = msg.payload.decode('utf-8').strip().upper()

        if payload == "GET" or payload == "":
            print("\n[>] Petición de estado recibida. Respondiendo...")
            client.publish(self.base_topic, str(self.current_value), qos=1, retain=True)

    def start(self):
        """Inicia la conexión y el bucle principal del sensor."""
        print(f"Iniciando Dummy Sensor [ID: {self.sensor_id}]")
        print(f"Broker: {self.host}:{self.port} | Intervalo: {self.interval}s | Rango: [{self.send_min}, {self.send_max}] | Incremento: {self.incr}")
        print("-" * 50)
        
        try:
            # Nos conectamos al broker y comenzamos el bucle de procesamiento de mensajes
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            
            direccion = 1
            
            while True:
                print(f"Publicando estado: {self.current_value}")
                self.client.publish(self.base_topic, str(self.current_value), qos=1, retain=True)
                
                self.current_value += self.incr * direccion
                
                if self.current_value >= self.send_max:
                    self.current_value = self.send_max
                    direccion = -1
                elif self.current_value <= self.send_min:
                    self.current_value = self.send_min
                    direccion = 1
                    
                time.sleep(self.interval)
                
        except ConnectionRefusedError:
            print(f"Error: Conexión rechazada. Asegura que el broker en {self.host} está en ejecución.")
        except KeyboardInterrupt:
            print("\n[*] Deteniendo dispositivo...")
            self.client.loop_stop()
            self.client.disconnect()


def main():
    """Función principal que procesa los argumentos e inicia el dispositivo."""
    parser = argparse.ArgumentParser(description="Dispositivo IoT Dummy Sensor")
    parser.add_argument("--host", "-H", type=str, default="localhost", help="Host del broker MQTT")
    parser.add_argument("--port", "-p", type=int, default=1883, help="Puerto del broker MQTT")
    parser.add_argument("--interval", "-i", type=float, default=1.0, help="Tiempo en segundos tras los que simula un cambio de estado")
    parser.add_argument("--min", "-m", type=int, default=20, help="Valor mínimo a enviar")
    parser.add_argument("--max", "-M", type=int, default=30, help="Valor máximo a enviar")
    parser.add_argument("--increment", type=int, default=1, help="Incremento entre min y max")
    parser.add_argument("id", type=str, help="Identificador único del dispositivo")
    
    args = parser.parse_args()
    
    # Instaciamos la la clase y arramcamos
    sensor = DummySensor(args.host, args.port, args.id, args.interval, args.min, args.max, args.increment)
    sensor.start()

if __name__ == "__main__":
    main()