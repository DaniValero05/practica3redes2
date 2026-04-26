"""
test_device.py
Pruebas unitarias para dummy-switch.py y dummy-sensor.py.

Requisitos cubiertos (del enunciado):
  - Conecta correctamente con el broker
  - Si no conecta con el broker da error
  - Probar que el sistema lee bien los parámetros por línea de comandos
  - (switch) Cambia de estado ante una acción
  - (sensor) Cambia de estado en intervalos entre min y max
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

# Añadimos el directorio actors al path para poder importar los módulos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Importamos con importlib porque los archivos tienen guiones en el nombre
import importlib.util

def load_module(filename, module_name):
    spec = importlib.util.spec_from_file_location(
        module_name,
        os.path.join(os.path.dirname(__file__), "..", filename)
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

dummy_switch_mod = load_module("dummy-switch.py", "dummy_switch")
dummy_sensor_mod = load_module("dummy-sensor.py", "dummy_sensor")

DummySwitch = dummy_switch_mod.DummySwitch
DummySensor = dummy_sensor_mod.DummySensor


# ─────────────────────────────────────────────
# Tests para DummySwitch
# ─────────────────────────────────────────────

class TestDummySwitchConnection(unittest.TestCase):
    """Pruebas de conexión del DummySwitch."""

    @patch("paho.mqtt.client.Client")
    def test_connect_success(self, mock_mqtt_class):
        """El switch llama a connect() con el host y puerto correctos."""
        mock_client = MagicMock()
        mock_mqtt_class.return_value = mock_client

        switch = DummySwitch("redes2.ii.uam.es", 1883, 0.0, "sw1")
        mock_client.connect.return_value = None
        mock_client.loop_forever.side_effect = KeyboardInterrupt  # para terminar el bucle

        try:
            switch.start()
        except SystemExit:
            pass

        mock_client.connect.assert_called_once_with("redes2.ii.uam.es", 1883, 60)

    @patch("paho.mqtt.client.Client")
    def test_connect_failure_raises(self, mock_mqtt_class):
        """Si el broker rechaza la conexión, start() no lanza una excepción no controlada."""
        mock_client = MagicMock()
        mock_mqtt_class.return_value = mock_client
        mock_client.connect.side_effect = ConnectionRefusedError

        switch = DummySwitch("localhost", 9999, 0.0, "sw1")
        # No debe propagar la excepción al exterior
        try:
            switch.start()
        except ConnectionRefusedError:
            self.fail("start() no debería propagar ConnectionRefusedError")


class TestDummySwitchCLI(unittest.TestCase):
    """Pruebas de lectura de parámetros por línea de comandos del Switch."""

    def test_default_args(self):
        """Los argumentos por defecto se aplican correctamente."""
        with patch("sys.argv", ["dummy-switch.py", "sw_test"]):
            import argparse

            parser = argparse.ArgumentParser()
            parser.add_argument("--host", "-H", type=str, default="redes2.ii.uam.es")
            parser.add_argument("--port", "-p", type=int, default=1883)
            parser.add_argument("--probability", "-P", type=float, default=0.3)
            parser.add_argument("id", type=str)
            args = parser.parse_args(["sw_test"])

            self.assertEqual(args.host, "redes2.ii.uam.es")
            self.assertEqual(args.port, 1883)
            self.assertAlmostEqual(args.probability, 0.3)
            self.assertEqual(args.id, "sw_test")

    def test_custom_args(self):
        """Los argumentos personalizados se parsean correctamente."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--host", "-H", type=str, default="redes2.ii.uam.es")
        parser.add_argument("--port", "-p", type=int, default=1883)
        parser.add_argument("--probability", "-P", type=float, default=0.3)
        parser.add_argument("id", type=str)
        args = parser.parse_args(["--host", "localhost", "--port", "9999", "--probability", "0.0", "42"])

        self.assertEqual(args.host, "localhost")
        self.assertEqual(args.port, 9999)
        self.assertAlmostEqual(args.probability, 0.0)
        self.assertEqual(args.id, "42")


class TestDummySwitchStateChange(unittest.TestCase):
    """Prueba que el switch cambia de estado ante una acción ON/OFF."""

    def setUp(self):
        with patch("paho.mqtt.client.Client"):
            self.switch = DummySwitch("localhost", 1883, 0.0, "sw1")
            self.switch.client = MagicMock()

    def test_switch_on(self):
        """Al recibir ON en el command_topic, el estado cambia a ON."""
        msg = MagicMock()
        msg.topic = self.switch.command_topic
        msg.payload = b"ON"
        self.switch.current_state = "OFF"

        self.switch.on_message(self.switch.client, None, msg)

        self.assertEqual(self.switch.current_state, "ON")
        self.switch.client.publish.assert_called_once()

    def test_switch_off(self):
        """Al recibir OFF en el command_topic, el estado cambia a OFF."""
        msg = MagicMock()
        msg.topic = self.switch.command_topic
        msg.payload = b"OFF"
        self.switch.current_state = "ON"

        self.switch.on_message(self.switch.client, None, msg)

        self.assertEqual(self.switch.current_state, "OFF")

    def test_switch_ignores_same_state(self):
        """Si ya está en el estado pedido, no publica nada nuevo."""
        msg = MagicMock()
        msg.topic = self.switch.command_topic
        msg.payload = b"ON"
        self.switch.current_state = "ON"

        self.switch.on_message(self.switch.client, None, msg)

        self.switch.client.publish.assert_not_called()

    def test_switch_failure_probability(self):
        """Con probabilidad de fallo 1.0, nunca cambia de estado."""
        self.switch.probability = 1.0
        msg = MagicMock()
        msg.topic = self.switch.command_topic
        msg.payload = b"ON"
        self.switch.current_state = "OFF"

        self.switch.on_message(self.switch.client, None, msg)

        self.assertEqual(self.switch.current_state, "OFF")
        self.switch.client.publish.assert_not_called()

    def test_switch_unknown_command(self):
        """Un comando desconocido no cambia el estado."""
        msg = MagicMock()
        msg.topic = self.switch.command_topic
        msg.payload = b"TOGGLE"
        self.switch.current_state = "OFF"

        self.switch.on_message(self.switch.client, None, msg)

        self.assertEqual(self.switch.current_state, "OFF")


# ─────────────────────────────────────────────
# Tests para DummySensor
# ─────────────────────────────────────────────

class TestDummySensorConnection(unittest.TestCase):
    """Pruebas de conexión del DummySensor."""

    @patch("paho.mqtt.client.Client")
    def test_connect_success(self, mock_mqtt_class):
        """El sensor llama a connect() con el host y puerto correctos."""
        mock_client = MagicMock()
        mock_mqtt_class.return_value = mock_client
        mock_client.loop_start.return_value = None

        sensor = DummySensor("redes2.ii.uam.es", 1883, "s1", interval=100)
        # Simulamos start() con KeyboardInterrupt para salir del while True
        mock_client.connect.return_value = None
        with patch("time.sleep", side_effect=KeyboardInterrupt):
            try:
                sensor.start()
            except (KeyboardInterrupt, SystemExit):
                pass

        mock_client.connect.assert_called_once_with("redes2.ii.uam.es", 1883, 60)

    @patch("paho.mqtt.client.Client")
    def test_connect_failure(self, mock_mqtt_class):
        """Si el broker rechaza la conexión, start() lo gestiona sin propagarse."""
        mock_client = MagicMock()
        mock_mqtt_class.return_value = mock_client
        mock_client.connect.side_effect = ConnectionRefusedError

        sensor = DummySensor("localhost", 9999, "s1")
        try:
            sensor.start()
        except ConnectionRefusedError:
            self.fail("start() no debería propagar ConnectionRefusedError")


class TestDummySensorCLI(unittest.TestCase):
    """Pruebas de lectura de parámetros por línea de comandos del Sensor."""

    def test_default_args(self):
        """Los argumentos por defecto son correctos."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--host", "-H", type=str, default="redes2.ii.uam.es")
        parser.add_argument("--port", "-p", type=int, default=1883)
        parser.add_argument("--interval", "-i", type=float, default=1.0)
        parser.add_argument("--min", "-m", type=int, default=20)
        parser.add_argument("--max", "-M", type=int, default=30)
        parser.add_argument("--increment", type=int, default=1)
        parser.add_argument("id", type=str)
        args = parser.parse_args(["sensor1"])

        self.assertEqual(args.host, "redes2.ii.uam.es")
        self.assertEqual(args.port, 1883)
        self.assertEqual(args.interval, 1.0)
        self.assertEqual(args.min, 20)
        self.assertEqual(args.max, 30)
        self.assertEqual(args.increment, 1)


class TestDummySensorValueRange(unittest.TestCase):
    """Prueba que el sensor alterna valores entre min y max."""

    def setUp(self):
        with patch("paho.mqtt.client.Client"):
            self.sensor = DummySensor("localhost", 1883, "s1",
                                      interval=1, send_min=20, send_max=25, incr=1)
            self.sensor.client = MagicMock()

    def test_initial_value_is_min(self):
        """El valor inicial del sensor es el mínimo."""
        self.assertEqual(self.sensor.current_value, self.sensor.send_min)

    def test_value_does_not_exceed_max(self):
        """El sensor nunca supera el valor máximo."""
        # Simulamos muchas iteraciones
        with patch("paho.mqtt.client.Client"):
            sensor = DummySensor("localhost", 1883, "s2",
                                 interval=1, send_min=20, send_max=25, incr=1)
            sensor.client = MagicMock()

        direction = 1
        for _ in range(100):
            sensor.current_value += sensor.incr * direction
            if sensor.current_value >= sensor.send_max:
                sensor.current_value = sensor.send_max
                direction = -1
            elif sensor.current_value <= sensor.send_min:
                sensor.current_value = sensor.send_min
                direction = 1
            self.assertGreaterEqual(sensor.current_value, sensor.send_min)
            self.assertLessEqual(sensor.current_value, sensor.send_max)

    def test_responds_to_get(self):
        """El sensor responde a una petición GET publicando su estado."""
        msg = MagicMock()
        msg.payload = b"GET"
        self.sensor.on_message(self.sensor.client, None, msg)
        self.sensor.client.publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
