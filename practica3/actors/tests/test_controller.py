"""
test_controller.py
Pruebas unitarias para controller.py (con RuleEngine integrado).

Requisitos cubiertos (del enunciado):
  - Conecta correctamente con el broker
  - Si no conecta con el broker da error
  - Ante un mensaje de sensor, desencadena el mecanismo para comprobar reglas
  - Ante una respuesta de RuleEngine para realizar una acción, realiza la acción
  - Se lee correctamente la información de los dispositivos de la persistencia
"""

import sys
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Añadimos actors/ al path para importar controller.py directamente
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from controller import Controller, RuleEngine

GRUPO = "2303"
PAREJA = "02"
BASE_TOPIC = f"redes2/{GRUPO}/{PAREJA}"


# ── Utilidad: base de datos de prueba ─────────────────────────────────────────

def create_test_db(devices=None, rules=None):
    """
    Crea un fichero SQLite temporal con el esquema de Django y datos opcionales.
    Devuelve la ruta al fichero (el llamador es responsable de borrarlo).
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE app_device (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            uid       VARCHAR(100) UNIQUE NOT NULL,
            name      VARCHAR(100) NOT NULL,
            is_sensor BOOLEAN NOT NULL DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE app_event (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   DATETIME NOT NULL,
            device_uid  VARCHAR(100) NOT NULL,
            event_type  VARCHAR(50)  NOT NULL,
            description TEXT         NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE app_rule (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             VARCHAR(100) NOT NULL,
            trigger_device_id INTEGER NOT NULL,
            operator         VARCHAR(2)   NOT NULL,
            condition_value  REAL         NOT NULL,
            target_device_id  INTEGER NOT NULL,
            action_command   VARCHAR(50)  NOT NULL
        )
    """)

    if devices:
        for uid, name, is_sensor in devices:
            c.execute(
                "INSERT INTO app_device (uid, name, is_sensor) VALUES (?, ?, ?)",
                (uid, name, 1 if is_sensor else 0),
            )

    if rules:
        # rules = [(name, trigger_uid, operator, value, target_uid, command), ...]
        for name, trigger_uid, op, val, target_uid, cmd in rules:
            c.execute("SELECT id FROM app_device WHERE uid=?", (trigger_uid,))
            tid = c.fetchone()[0]
            c.execute("SELECT id FROM app_device WHERE uid=?", (target_uid,))
            aid = c.fetchone()[0]
            c.execute(
                "INSERT INTO app_rule "
                "(name, trigger_device_id, operator, condition_value, target_device_id, action_command) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, tid, op, val, aid, cmd),
            )

    conn.commit()
    conn.close()
    return tmp.name


# ══════════════════════════════════════════════════════════════════════════════
# Tests de conexión
# ══════════════════════════════════════════════════════════════════════════════

class TestControllerConnection(unittest.TestCase):

    def setUp(self):
        self.db = create_test_db()

    def tearDown(self):
        os.unlink(self.db)

    @patch("controller.mqtt.Client")
    def test_connect_success_calls_connect(self, mock_cls):
        """start() llama a client.connect() con el host y puerto correctos."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.loop_forever.side_effect = KeyboardInterrupt

        ctrl = Controller("redes2.ii.uam.es", 1883, self.db)
        try:
            ctrl.start()
        except (KeyboardInterrupt, SystemExit):
            pass

        mock_client.connect.assert_called_once_with("redes2.ii.uam.es", 1883, keepalive=60)

    @patch("controller.mqtt.Client")
    def test_connect_failure_does_not_propagate(self, mock_cls):
        """Si el broker rechaza la conexión, start() no propaga la excepción."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.connect.side_effect = ConnectionRefusedError

        ctrl = Controller("localhost", 9999, self.db)
        try:
            ctrl.start()  # No debe lanzar
        except ConnectionRefusedError:
            self.fail("start() no debería propagar ConnectionRefusedError")

    @patch("controller.mqtt.Client")
    def test_on_connect_subscribes_to_wildcard(self, mock_cls):
        """on_connect suscribe al topic wildcard correcto."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        ctrl = Controller("localhost", 1883, self.db)
        ctrl.on_connect(mock_client, None, None, rc=0)

        mock_client.subscribe.assert_called_once_with(f"{BASE_TOPIC}/#", qos=1)

    @patch("controller.mqtt.Client")
    def test_on_connect_failure_does_not_subscribe(self, mock_cls):
        """Si rc != 0, no se intenta suscribir."""
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        ctrl = Controller("localhost", 1883, self.db)
        ctrl.on_connect(mock_client, None, None, rc=1)

        mock_client.subscribe.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Tests de persistencia
# ══════════════════════════════════════════════════════════════════════════════

class TestControllerPersistence(unittest.TestCase):

    def setUp(self):
        self.db = create_test_db(devices=[
            ("sensor1", "Sensor Salón", True),
            ("switch1", "Luz Cocina",   False),
        ])

    def tearDown(self):
        os.unlink(self.db)

    @patch("controller.mqtt.Client")
    def test_registered_device_is_accepted(self, _):
        ctrl = Controller("localhost", 1883, self.db)
        self.assertTrue(ctrl.is_device_registered("sensor1"))
        self.assertTrue(ctrl.is_device_registered("switch1"))

    @patch("controller.mqtt.Client")
    def test_unregistered_device_is_rejected(self, _):
        ctrl = Controller("localhost", 1883, self.db)
        self.assertFalse(ctrl.is_device_registered("fantasma"))
        self.assertFalse(ctrl.is_device_registered(""))

    @patch("controller.mqtt.Client")
    def test_invalid_db_path_returns_false(self, _):
        """Si la BD no existe, is_device_registered devuelve False sin excepción."""
        ctrl = Controller("localhost", 1883, "/no/existe.sqlite3")
        self.assertFalse(ctrl.is_device_registered("sensor1"))

    @patch("controller.mqtt.Client")
    def test_log_event_inserts_row(self, _):
        """log_event escribe correctamente un registro en app_event."""
        ctrl = Controller("localhost", 1883, self.db)
        ctrl.log_event("sensor1", "TELEMETRÍA", "Valor recibido: 25.5")

        conn = sqlite3.connect(self.db)
        row = conn.execute(
            "SELECT device_uid, event_type, description FROM app_event"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "sensor1")
        self.assertEqual(row[1], "TELEMETRÍA")
        self.assertIn("25.5", row[2])


# ══════════════════════════════════════════════════════════════════════════════
# Tests del motor de mensajes MQTT
# ══════════════════════════════════════════════════════════════════════════════

class TestControllerMessageHandling(unittest.TestCase):

    def setUp(self):
        self.db = create_test_db(devices=[
            ("sensor1", "Sensor Temperatura", True),
            ("switch1", "Caldera",            False),
        ])

    def tearDown(self):
        os.unlink(self.db)

    def _make_controller(self):
        with patch("controller.mqtt.Client"):
            ctrl = Controller("localhost", 1883, self.db)
            ctrl.client = MagicMock()
            ctrl.rule_engine = MagicMock()
            ctrl.rule_engine.process_event.return_value = []
        return ctrl

    def _make_msg(self, topic, payload_str):
        msg = MagicMock()
        msg.topic   = topic
        msg.payload = payload_str.encode("utf-8")
        return msg

    def test_sensor_message_calls_rule_engine(self):
        """Un mensaje de sensor registrado dispara process_event en el RuleEngine."""
        ctrl = self._make_controller()
        msg  = self._make_msg(f"{BASE_TOPIC}/sensor1", "25.5")
        ctrl.on_message(ctrl.client, None, msg)
        ctrl.rule_engine.process_event.assert_called_once_with("sensor1", "25.5")

    def test_unregistered_device_skips_rule_engine(self):
        """Un dispositivo no registrado no llega al RuleEngine."""
        ctrl = self._make_controller()
        msg  = self._make_msg(f"{BASE_TOPIC}/intruso", "99")
        ctrl.on_message(ctrl.client, None, msg)
        ctrl.rule_engine.process_event.assert_not_called()

    def test_set_subtopic_is_ignored(self):
        """Mensajes en /set son ignorados para evitar bucles."""
        ctrl = self._make_controller()
        msg  = self._make_msg(f"{BASE_TOPIC}/switch1/set", "ON")
        ctrl.on_message(ctrl.client, None, msg)
        ctrl.rule_engine.process_event.assert_not_called()

    def test_rule_action_publishes_command(self):
        """Si el RuleEngine devuelve una acción, se publica el comando MQTT."""
        ctrl = self._make_controller()
        ctrl.rule_engine.process_event.return_value = [
            {"target": "switch1", "command": "ON"}
        ]
        msg = self._make_msg(f"{BASE_TOPIC}/sensor1", "30")
        ctrl.on_message(ctrl.client, None, msg)

        expected_topic = f"{BASE_TOPIC}/switch1/set"
        ctrl.client.publish.assert_called_once_with(expected_topic, "ON", qos=1)

    def test_multiple_actions_publish_multiple_commands(self):
        """Varias acciones del RuleEngine generan varias publicaciones MQTT."""
        ctrl = self._make_controller()
        ctrl.rule_engine.process_event.return_value = [
            {"target": "switch1", "command": "ON"},
            {"target": "switch1", "command": "OFF"},
        ]
        msg = self._make_msg(f"{BASE_TOPIC}/sensor1", "30")
        ctrl.on_message(ctrl.client, None, msg)
        self.assertEqual(ctrl.client.publish.call_count, 2)


# ══════════════════════════════════════════════════════════════════════════════
# Tests del RuleEngine integrado
# ══════════════════════════════════════════════════════════════════════════════

class TestRuleEngine(unittest.TestCase):
    """Prueba el RuleEngine directamente con una BD real."""

    def setUp(self):
        self.db = create_test_db(
            devices=[
                ("sensor1", "Sensor", True),
                ("switch1", "Actuador", False),
            ],
            rules=[
                ("Encender si >25", "sensor1", ">",  25.0, "switch1", "ON"),
                ("Apagar si <20",   "sensor1", "<",  20.0, "switch1", "OFF"),
                ("Reset si ==0",    "sensor1", "==",  0.0, "switch1", "OFF"),
            ],
        )
        self.engine = RuleEngine(self.db)

    def tearDown(self):
        os.unlink(self.db)

    def test_greater_than_triggers(self):
        actions = self.engine.process_event("sensor1", "26")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0], {"target": "switch1", "command": "ON"})

    def test_less_than_triggers(self):
        actions = self.engine.process_event("sensor1", "19")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0], {"target": "switch1", "command": "OFF"})

    def test_equal_triggers(self):
        actions = self.engine.process_event("sensor1", "0")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0], {"target": "switch1", "command": "OFF"})

    def test_no_rule_matches(self):
        # 22 no cumple >25 ni <20 ni ==0
        actions = self.engine.process_event("sensor1", "22")
        self.assertEqual(actions, [])

    def test_non_numeric_payload_returns_empty(self):
        actions = self.engine.process_event("sensor1", "ON")
        self.assertEqual(actions, [])

    def test_unknown_device_returns_empty(self):
        actions = self.engine.process_event("dispositivo_fantasma", "30")
        self.assertEqual(actions, [])


if __name__ == "__main__":
    unittest.main()
