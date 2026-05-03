from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    TemplateView,
)
from .models import Device, Rule, Event
import subprocess, os, sys


ACTORS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "actors"))

def _python():
    return sys.executable


class IndexView(TemplateView):
    template_name = "app/index.html"


class DeviceListView(ListView):
    model = Device
    template_name = "app/device/device_list.html"
    context_object_name = "devices"


class DeviceTypeSelectView(TemplateView):
    # Esta vista solo carga el HTML con los botones de selección
    template_name = "app/device/device_new.html"

class SensorCreateView(CreateView):
    model = Device
    template_name = "app/device/new_sensor.html"
    fields = ["uid", "name", "host", "port", "interval", "min_value", "max_value", "sensor_increment"]
    success_url = reverse_lazy("app:devices")
    
    def form_valid(self, form):
        form.instance.device_type = 'sensor'
        response = super().form_valid(form)
        d = self.object
        cmd = [_python(), os.path.join(ACTORS_DIR, "dummy-sensor.py"),
               "--host", d.host or "localhost",
               "--port", str(d.port or 1883),
               "--min", str(d.min_value or 20),
               "--max", str(d.max_value or 30),
               "--increment", str(d.sensor_increment or 1),
               "--interval", str(d.interval or 1),
               d.uid]
        subprocess.Popen(cmd)
        return response

class SwitchCreateView(CreateView):
    model = Device
    template_name = "app/device/new_switch.html"
    fields = ["uid", "name", "host", "port", "probability"]
    success_url = reverse_lazy("app:devices")

    def form_valid(self, form):
        form.instance.device_type = 'switch'
        response = super().form_valid(form)
        d = self.object
        cmd = [_python(), os.path.join(ACTORS_DIR, "dummy-switch.py"),
               "--host", d.host or "localhost",
               "--port", str(d.port or 1883),
               "--probability", str(d.probability or 0.0),
               d.uid]
        subprocess.Popen(cmd)
        return response

class ClockCreateView(CreateView):
    model = Device
    template_name = "app/device/new_clock.html"
    fields = ["uid", "name", "host", "port", "start_time", "clock_increment", "rate"]
    success_url = reverse_lazy("app:devices")

    def form_valid(self, form):
        form.instance.device_type = 'clock'
        response = super().form_valid(form)
        d = self.object
        cmd = [_python(), os.path.join(ACTORS_DIR, "dummy-clock.py"),
               "--host", d.host or "localhost",
               "--port", str(d.port or 1883),
               "--increment", str(d.clock_increment or 1),
               "--rate", str(d.rate or 1.0),
               d.uid]
        if d.start_time:
            cmd += ["--time", d.start_time]
        subprocess.Popen(cmd)
        return response
    
class DeviceUpdateView(UpdateView):
    model = Device
    template_name = "app/device/device_edit.html"
    # Quitamos la lista estática de fields de aquí
    fields = "__all__" # Cargamos todos inicialmente para luego filtrarlos
    success_url = reverse_lazy("app:devices")

    def get_form(self, form_class=None):
        # Obtenemos el formulario original generado por Django
        form = super().get_form(form_class)
        # Obtenemos el dispositivo concreto que estamos editando
        device = self.object
        
        # 1. Definimos los campos base obligatorios para cualquier dispositivo
        allowed_fields = ['uid', 'name', 'host', 'port']
        
        # 2. Añadimos los campos específicos según el tipo de dispositivo guardado
        if device.device_type == 'sensor':
            allowed_fields += ['interval', 'min_value', 'max_value', 'sensor_increment']
        elif device.device_type == 'switch':
            allowed_fields += ['probability']
        elif device.device_type == 'clock':
            allowed_fields += ['start_time', 'clock_increment', 'rate']
            
        # 3. Recorremos el formulario y borramos los campos que no pertenecen a este tipo
        for field_name in list(form.fields.keys()):
            if field_name not in allowed_fields:
                del form.fields[field_name]
                
        return form


def device_remove(request, pk):
    device = get_object_or_404(Device, pk=pk)
    device.delete()
    return redirect("app:devices")


class RuleListView(ListView):
    model = Rule
    template_name = "app/rule/rule_list.html"
    context_object_name = "rules"


class RuleCreateView(CreateView):
    model = Rule
    template_name = "app/rule/rule_new.html"
    fields = [
        "name",
        "trigger_device",
        "operator",
        "condition_type",
        "condition_value",
        "condition_time",
        "target_device",
        "action_command",
    ]
    success_url = reverse_lazy("app:rules")


class RuleUpdateView(UpdateView):
    model = Rule
    template_name = "app/rule/rule_edit.html"
    fields = [
        "name",
        "trigger_device",
        "operator",
        "condition_type",
        "condition_value",
        "condition_time",
        "target_device",
        "action_command",
    ]
    success_url = reverse_lazy("app:rules")


class EventListView(ListView):
    model = Event
    template_name = "app/event/event_list.html"
    context_object_name = "events"
    paginate_by = 20


def rule_remove(request, pk):
    rule = get_object_or_404(Rule, pk=pk)
    rule.delete()
    return redirect("app:rules")
