#!/bin/bash
# simulator.sh
# Script de integración que lanza todos los actores del sistema domótico.
#
# Uso (ejecutar desde el directorio practica3/):
#   chmod +x simulator.sh
#   ./simulator.sh [--host HOST] [--port PORT] [--db DB_PATH]

set -e

# ── Configuración por defecto ──────────────────────────────────────────────────
BROKER_HOST="${BROKER_HOST:-localhost}"
BROKER_PORT="${BROKER_PORT:-1883}"
DB_PATH="${DB_PATH:-project/db.sqlite3}"

# Directorio donde está este script (raíz de practica3/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Los actores Python están en el subdirectorio actors/
ACTORS_DIR="$SCRIPT_DIR/actors"

# Parseo de argumentos opcionales
while [[ $# -gt 0 ]]; do
  case $1 in
    --host) BROKER_HOST="$2"; shift 2 ;;
    --port) BROKER_PORT="$2"; shift 2 ;;
    --db)   DB_PATH="$2";     shift 2 ;;
    *) echo "Argumento desconocido: $1"; exit 1 ;;
  esac
done

# Convertir DB_PATH a ruta absoluta si se pasó como relativa
if [[ "$DB_PATH" != /* ]]; then
  DB_PATH="$SCRIPT_DIR/$DB_PATH"
fi

echo "=============================================="
echo "  Sistema Domótico - Simulador de Integración"
echo "=============================================="
echo "Broker       : $BROKER_HOST:$BROKER_PORT"
echo "Base de datos: $DB_PATH"
echo "Actores dir  : $ACTORS_DIR"
echo ""

# ── Comprobaciones previas ─────────────────────────────────────────────────────
for f in controller.py dummy-switch.py dummy-clock.py dummy-sensor.py; do
  if [[ ! -f "$ACTORS_DIR/$f" ]]; then
    echo "[ERROR] No se encuentra $ACTORS_DIR/$f"
    echo "        Asegúrate de ejecutar el script desde el directorio practica3/"
    exit 1
  fi
done

if [[ ! -f "$DB_PATH" ]]; then
  echo "[ERROR] No se encuentra la base de datos en: $DB_PATH"
  echo "        Ejecuta primero: cd project && python3 manage.py migrate"
  exit 1
fi

PIDS=()

# ── Limpieza al salir ──────────────────────────────────────────────────────────
cleanup() {
  echo ""
  echo "[*] Deteniendo todos los actores..."
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null
      echo "    PID $pid detenido."
    fi
  done
  echo "[*] Simulación finalizada."
}
trap cleanup EXIT INT TERM

# ── 1. Controller (integra el RuleEngine internamente) ─────────────────────────
echo "[1/4] Iniciando Controller..."
python3 "$ACTORS_DIR/controller.py" \
  --host "$BROKER_HOST" \
  --port "$BROKER_PORT" \
  --database "$DB_PATH" &
PIDS+=($!)
echo "      PID: ${PIDS[-1]}"
sleep 2   # Esperamos a que el controller conecte antes de lanzar los dispositivos

# ── 2. Dummy Switch ────────────────────────────────────────────────────────────
echo "[2/4] Iniciando Dummy Switch (ID: switch1, fallo: 0%)..."
python3 "$ACTORS_DIR/dummy-switch.py" \
  --host "$BROKER_HOST" \
  --port "$BROKER_PORT" \
  --probability 0.0 \
  switch1 &
PIDS+=($!)
echo "      PID: ${PIDS[-1]}"
sleep 1

# ── 3. Dummy Clock ─────────────────────────────────────────────────────────────
echo "[3/4] Iniciando Dummy Clock (ID: clock1, inicio: 08:00:00, incremento: 60s)..."
python3 "$ACTORS_DIR/dummy-clock.py" \
  --host "$BROKER_HOST" \
  --port "$BROKER_PORT" \
  --time "08:00:00" \
  --increment 60 \
  --rate 1 \
  clock1 &
PIDS+=($!)
echo "      PID: ${PIDS[-1]}"
sleep 1

# ── 4. Dummy Sensor ────────────────────────────────────────────────────────────
echo "[4/4] Iniciando Dummy Sensor (ID: sensor1, rango: 20-30, intervalo: 2s)..."
python3 "$ACTORS_DIR/dummy-sensor.py" \
  --host "$BROKER_HOST" \
  --port "$BROKER_PORT" \
  --min 20 \
  --max 30 \
  --increment 1 \
  --interval 2 \
  sensor1 &
PIDS+=($!)
echo "      PID: ${PIDS[-1]}"

echo ""
echo "=============================================="
echo "  Todos los actores arrancados."
echo "  Presiona Ctrl+C para detener la simulación."
echo "=============================================="
echo ""

wait
