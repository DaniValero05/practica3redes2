import unittest
from unittest.mock import patch, MagicMock
import importlib.util
import os


# Helper compacto para importar el archivo controller
def cargar_modulo(nombre, archivo):
    ruta = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "actors", archivo)
    )
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Importamos el controlador directamente saltándonos el sys.path
controller = cargar_modulo("controller", "controller.py")


class TestController(unittest.TestCase):

    def setUp(self):
        self.ctrl = controller.Controller("localhost", 1883, "test.db")
        # Simulamos los componentes externos directamente sin decoradores
        self.ctrl.client = MagicMock()
        self.ctrl.rule_engine = MagicMock()
        self.ctrl.log_event = MagicMock()

    def test_conecta_correctamente_broker(self):
        self.ctrl.on_connect(self.ctrl.client, None, None, 0, None)
        self.ctrl.client.subscribe.assert_called_with(self.ctrl.general_topic, qos=1)

    def test_no_conecta_con_broker_da_error(self):
        self.ctrl.on_connect(self.ctrl.client, None, None, 5, None)
        self.ctrl.client.subscribe.assert_not_called()

    @patch.object(controller.Controller, "is_device_registered", return_value=True)
    def test_mensaje_sensor_desencadena_reglas(self, mock_reg):
        msg = MagicMock(topic=f"{controller.BASE_TOPIC}/sen1", payload=b"25")
        self.ctrl.rule_engine.process_event.return_value = []

        self.ctrl.on_message(self.ctrl.client, None, msg)
        self.ctrl.rule_engine.process_event.assert_called_once_with("sen1", "25")

    @patch.object(controller.Controller, "is_device_registered", return_value=True)
    def test_respuesta_rule_engine_realiza_accion(self, mock_reg):
        msg = MagicMock(topic=f"{controller.BASE_TOPIC}/sen1", payload=b"25")
        # Forzamos al motor de reglas a devolver una acción
        self.ctrl.rule_engine.process_event.return_value = [
            {"target": "sw1", "command": "ON"}
        ]

        self.ctrl.on_message(self.ctrl.client, None, msg)

        topic_esperado = f"{controller.BASE_TOPIC}/sw1/set"
        self.ctrl.client.publish.assert_called_with(topic_esperado, "ON", qos=1)

    @patch("sqlite3.connect")
    def test_lee_informacion_dispositivos_persistencia(self, mock_sql):
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)  # Simula que encuentra un dispositivo
        mock_sql.return_value.cursor.return_value = mock_cursor

        resultado = self.ctrl.is_device_registered("sen1")

        self.assertTrue(resultado)
        mock_cursor.execute.assert_called_with(
            "SELECT id FROM app_device WHERE uid = ?", ("sen1",)
        )


if __name__ == "__main__":
    unittest.main()
