#!/bin/bash

# ==============================================================================
# Simulador del Sistema Domótico
# Lanza los actores en segundo plano y simula interacciones.
# ==============================================================================

# Variables de configuración
ACTORS_DIR="./actors"
PROJECT_DIR="./project"
BROKER="localhost"
PORT=1883
GRUPO="2303"   
PAREJA="02"    

echo "====================================================="
echo " [*] Iniciando Simulador del Sistema Domótico"
echo "====================================================="

# Función para limpiar y matar los procesos en segundo plano al salir
cleanup() {
    echo ""
    echo "[*] Limpiando y deteniendo todos los actores..."
    kill $CONTROLLER_PID $SWITCH_PID $SENSOR_PID 2>/dev/null
    echo "[*] Simulación terminada."
    exit 0
}

trap cleanup SIGINT SIGTERM

# 0. Registrar dispositivos y reglas usando el ORM de Django
echo "[+] Registrando dispositivos de prueba y reglas en la Base de Datos..."
python3 $PROJECT_DIR/manage.py shell -c "
from app.models import Device, Rule

# 1. Creamos o recuperamos los dispositivos
sw1, created_sw = Device.objects.get_or_create(
    uid='sw1', 
    defaults={'name': 'Interruptor Sim', 'device_type': 'switch', 'host': '$BROKER', 'port': $PORT}
)
sen1, created_sen = Device.objects.get_or_create(
    uid='sen1', 
    defaults={'name': 'Sensor Sim', 'device_type': 'sensor', 'host': '$BROKER', 'port': $PORT}
)

# 2. Creamos una regla automática de prueba
rule, created_rule = Rule.objects.get_or_create(
    name='Regla Simulador: Sen1 > 21 -> sw1 ON',
    trigger_device=sen1,
    operator='>',
    condition_type='numeric',
    condition_value=21.0,
    target_device=sw1,
    defaults={'action_command': 'ON'}
)

print(f'   -> Base de datos lista. Dispositivos sw1 y sen1 preparados.')
"

# 1. Iniciar el Controlador
echo "[+] Lanzando Controller..."
python3 $ACTORS_DIR/controller.py -H $BROKER -p $PORT &
CONTROLLER_PID=$!
sleep 2 

# 2. Iniciar el Interruptor (Switch) con probabilidad de fallo 0
echo "[+] Lanzando Dummy Switch (ID: sw1)..."
python3 $ACTORS_DIR/dummy-switch.py -H $BROKER -p $PORT -P 0.0 sw1 &
SWITCH_PID=$!
sleep 2

# 3. Iniciar el Sensor (Sensor) con intervalos cortos 
echo "[+] Lanzando Dummy Sensor (ID: sen1)..."
python3 $ACTORS_DIR/dummy-sensor.py -H $BROKER -p $PORT -i 2 -m 20 -M 23 --increment 1 sen1 &
SENSOR_PID=$!
sleep 2

echo "====================================================="
echo " Todos los actores están en ejecución."
echo " Observando la interacción automática del sensor..."
echo "====================================================="

# Dejamos que el sensor envíe mediciones. 
# Como hemos creado una regla que dice que si pasa de 21 manda "ON", lo verás en acción.
sleep 8

echo "====================================================="
echo " Simulando acción externa manual..."
echo "====================================================="
echo "[>] Enviando comando 'OFF' al interruptor sw1 usando mosquitto_pub..."

# Forzamos un OFF manual para ver si el dispositivo lo acata
TOPIC_SET="redes2/$GRUPO/$PAREJA/sw1/set"
mosquitto_pub -h $BROKER -p $PORT -t "$TOPIC_SET" -m "OFF" -q 1

sleep 5

echo "[>] Enviando comando 'ON' al interruptor sw1 usando mosquitto_pub..."
mosquitto_pub -h $BROKER -p $PORT -t "$TOPIC_SET" -m "ON" -q 1

echo "====================================================="
echo " Dejando correr el sistema 10 segundos más..."
echo "====================================================="
sleep 10

cleanup
