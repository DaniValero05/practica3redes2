# rule_engine.py
import argparse
import sqlite3


class RuleEngine:
    """Motor de reglas."""

    def __init__(self, db_path):
        self.db_path = db_path

    def process_event(self, device_id, payload):
        """
        Evalúa el evento recibido comprobando las reglas en la persistencia.
        Retorna una lista de diccionarios con las acciones a realizar.
        """
        print(
            f"[RuleEngine] Procesando evento del dispositivo '{device_id}': {payload}"
        )
        acciones = []

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Consulta SQL: Unimos app_rule con app_device DOS veces
            # (una para el disparador y otra para el destino)
            query = """
                SELECT r.operator, r.condition_value, d_target.uid, r.action_command 
                FROM app_rule r
                JOIN app_device d_trigger ON r.trigger_device_id = d_trigger.id
                JOIN app_device d_target ON r.target_device_id = d_target.id
                WHERE d_trigger.uid = ?
            """
            cursor.execute(query, (device_id,))
            reglas = cursor.fetchall()

            for regla in reglas:
                operador, cond_value, target_uid, command = regla

                # Intentamos convertir el payload de MQTT a número flotante
                try:
                    valor_recibido = float(payload)
                except ValueError:
                    # Si el sensor manda un texto no numérico (ej. "ON"),
                    # lo ignoramos ya que tu base de datos espera comparar con un FloatField
                    print(
                        f"[RuleEngine] Aviso: payload '{payload}' ignorado (no numérico)."
                    )
                    continue

                # Evaluamos la regla
                regla_cumplida = False
                if operador == "==" and valor_recibido == cond_value:
                    regla_cumplida = True
                elif operador == ">" and valor_recibido > cond_value:
                    regla_cumplida = True
                elif operador == "<" and valor_recibido < cond_value:
                    regla_cumplida = True

                # Si la condición es cierta, añadimos la orden a la lista de acciones
                if regla_cumplida:
                    print(
                        f"[RuleEngine] ¡Regla cumplida! Si {device_id} {operador} {cond_value} -> {target_uid}={command}"
                    )
                    acciones.append({"target": target_uid, "command": command})

            conn.close()
        except sqlite3.Error as e:
            print(f"[RuleEngine] Error accediendo a la BD de reglas: {e}")

        return acciones


def main():
    """Punto de entrada si se ejecuta de forma independiente (ej. opción Discord/Separada)."""
    parser = argparse.ArgumentParser(description="Aplicación Rule Engine")
    parser.add_argument(
        "--host",
        "-H",
        type=str,
        default="redes2.ii.uam.es",
        help="Host del broker MQTT (si se conecta de forma independiente)",
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

    print(f"Iniciando Rule Engine con BD: {args.database}")


if __name__ == "__main__":
    main()
