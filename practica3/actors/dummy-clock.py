import argparse
import time
from datetime import datetime, timedelta
import paho.mqtt.client as mqtt

GRUPO = "2303"
PAREJA = "02"

#pylint: disable=too-many-instance-attributes
class DummyClock:
    """Clase que representa un reloj IoT simulado."""

    def __init__(self, host, port, clock_id, start_time_str=None, increment=1, rate=1):
        self.host = host
        self.port = port
        self.clock_id = clock_id
        self.increment = increment
        self.rate = rate 
        
        if start_time_str is not None:
            self.current_time = datetime.strptime(start_time_str, "%H:%M:%S")
        else:
            self.current_time = datetime.now()
            
        self.base_topic = f"redes2/{GRUPO}/{PAREJA}/{self.clock_id}" # Topic base para publicar el estado actual del reloj
    
        # Configuración del cliente MQTT
        self.client = mqtt.Client(client_id=f"clock_{GRUPO}_{PAREJA}_{self.clock_id}")
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message

    def on_connect(self, client, _userdata, _flags, rc):
        if rc == 0:
            print("Conectado exitosamente al broker.")
            client.subscribe(self.base_topic, qos=1)
            print("Suscrito a los topics")
        else:
            print(f"Error al conectar. Código de resultado: {rc}")

    def on_disconnect(self, _client, _userdata, rc):
        if rc != 0:
            print(f"Desconectado inesperadamente. Código de resultado: {rc}")
        else:
            print("Desconectado del broker de forma limpia.") 

    def on_message(self, client, _userdata, msg):
        payload = msg.payload.decode('utf-8').strip().upper()
        
        if payload == "GET" or payload == "":
            time_str = self.current_time.strftime("%H:%M:%S")
            print("\n[>] Petición de estado recibida. Respondiendo...")
            client.publish(self.base_topic, time_str, qos=1, retain=True)

    def start(self):
        """Inicia la conexión y el bucle principal del reloj."""
        print(f"Iniciando Dummy Clock [ID: {self.clock_id}]")
        print(f"Broker: {self.host}:{self.port} | Incremento: {self.increment}s | Tasa: {self.rate} msg/s")
        print("-" * 50)
        
        try:
            self.client.connect(self.host, self.port, 60)
            self.client.loop_start()
            
            # Calculamos el tiempo real de espera entre envíos
            sleep_time = 1.0 / self.rate
            
            while True:
                time_str = self.current_time.strftime("%H:%M:%S")
                print(f"Publicando hora: {time_str}")
                self.client.publish(self.base_topic, time_str, qos=1, retain=True)
                
                # Avanzamos el reloj virtual según el incremento configurado
                self.current_time += timedelta(seconds=self.increment)
                
                # Esperamos el tiempo real según la frecuencia configurada
                time.sleep(sleep_time)
                
        except ConnectionRefusedError:
            print(f"Error: Conexión rechazada. Asegura que el broker en {self.host} está en ejecución.")
        except KeyboardInterrupt:
            print("\n[*] Deteniendo dispositivo...")
            self.client.loop_stop()
            self.client.disconnect()


def main():
    """Función principal que procesa los argumentos e inicia el dispositivo."""
    parser = argparse.ArgumentParser(description="Dispositivo IoT Dummy Clock")
    parser.add_argument("--host", "-H", type=str, default="redes2.ii.uam.es", help="Host del broker MQTT")
    parser.add_argument("--port", "-p", type=int, default=1883, help="Puerto del broker MQTT")
    parser.add_argument("--time", type=str, default=None, help="Hora de inicio en formato HH:MM:SS")
    parser.add_argument("--increment", type=int, default=1, help="Incremento entre envíos en segundos del reloj virtual")
    parser.add_argument("--rate", type=float, default=1.0, help="Frecuencia de envío en mensajes por segundo")
    parser.add_argument("id", type=str, help="Identificador único del dispositivo")
    
    args = parser.parse_args()

    if args.rate <= 0:
        print("La tasa de envío debe ser un número positivo. Usando valor por defecto de 1 msg/s.")
        args.rate = 1.0
    
    clock = DummyClock(args.host, args.port, args.id, args.time, args.increment, args.rate)
    clock.start()

if __name__ == "__main__":
    main()