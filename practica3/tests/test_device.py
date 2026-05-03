import unittest
from unittest.mock import MagicMock, patch
import importlib.util
import os


# Helper compacto para importar archivos con guiones en el nombre
def cargar_modulo(nombre, archivo):
    ruta = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "actors", archivo)
    )
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dummy_switch = cargar_modulo("dummy_switch", "dummy-switch.py")
dummy_sensor = cargar_modulo("dummy_sensor", "dummy-sensor.py")


class TestDevice(unittest.TestCase):

    def test_conecta_correctamente_broker(self):
        sw = dummy_switch.DummySwitch("localhost", 1883, 0.0, "sw1")
        sw.client = MagicMock()  # Simulamos el cliente MQTT directamente
        sw.on_connect(sw.client, None, None, 0, None)  # rc=0 (éxito)
        self.assertEqual(sw.client.subscribe.call_count, 2)

    def test_no_conecta_con_broker_da_error(self):
        sw = dummy_switch.DummySwitch("localhost", 1883, 0.0, "sw1")
        sw.client = MagicMock()
        sw.on_connect(sw.client, None, None, 1, None)  # rc=1 (error)
        sw.client.subscribe.assert_not_called()

    @patch(
        "sys.argv",
        ["dummy-switch.py", "--host", "broker", "-p", "1884", "-P", "0.5", "sw1"],
    )
    @patch.object(dummy_switch, "DummySwitch")
    def test_lee_parametros_linea_comandos(self, mock_clase):
        dummy_switch.main()
        mock_clase.assert_called_with("broker", 1884, 0.5, "sw1")

    def test_switch_cambia_estado_ante_accion(self):
        sw = dummy_switch.DummySwitch("localhost", 1883, 0.0, "sw1")
        sw.client = MagicMock()
        msg = MagicMock(topic=sw.command_topic, payload=b"ON")

        sw.on_message(sw.client, None, msg)
        self.assertEqual(sw.current_state, "ON")

    @patch("time.sleep", side_effect=[None, KeyboardInterrupt])
    def test_sensor_cambia_estado_intervalos(self, mock_sleep):
        sen = dummy_sensor.DummySensor("localhost", 1883, "sen1", 1, 20, 22, 1)
        sen.client = MagicMock()

        sen.start()  # Da 2 vueltas (20 -> 21 -> 22) y el mock_sleep corta la ejecución
        self.assertEqual(sen.current_value, 22)


if __name__ == "__main__":
    unittest.main()
