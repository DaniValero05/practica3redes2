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


def _launch_device(d):
    """Lanza el subproceso del actor y devuelve el PID."""
    if d.device_type == 'sensor':
        cmd = [_python(), os.path.join(ACTORS_DIR, "dummy-sensor.py"),
               "--host", d.host or "localhost",
               "--port", str(d.port or 1883),
               "--min", str(d.min_value or 20),
               "--max", str(d.max_value or 30),
               "--increment", str(d.sensor_increment or 1),
               "--interval", str(d.interval or 1),
               d.uid]
    elif d.device_type == 'switch':
        cmd = [_python(), os.path.join(ACTORS_DIR, "dummy-switch.py"),
               "--host", d.host or "localhost",
               "--port", str(d.port or 1883),
               "--probability", str(d.probability or 0.0),
               d.uid]
    elif d.device_type == 'clock':
        cmd = [_python(), os.path.join(ACTORS_DIR, "dummy-clock.py"),
               "--host", d.host or "localhost",
               "--port", str(d.port or 1883),
               "--increment", str(d.clock_increment or 1),
               "--rate", str(d.rate or 1.0),
               d.uid]
        if d.start_time:
            cmd += ["--time", d.start_time]
    else:
        return None

    proc = subprocess.Popen(cmd)
    return proc.pid


class IndexView(TemplateView):
    template_name = "app/index.html"

class DeviceListView(ListView):
    model = Device
    template_name = "app/device/device_list.html"
    context_object_name = "devices"

class DeviceTypeSelectView(TemplateView):
    template_name = "app/device/device_new.html"

class SensorCreateView(CreateView):
    model = Device
    template_name = "app/device/new_sensor.html"
    fields = ["uid", "name", "host", "port", "interval", "min_value", "max_value", "sensor_increment"]
    success_url = reverse_lazy("app:devices")

    def form_valid(self, form):
        form.instance.device_type = 'sensor'
        response = super().form_valid(form)
        pid = _launch_device(self.object)
        if pid:
            self.object.pid = pid
            self.object.save(update_fields=['pid'])
        return response

class SwitchCreateView(CreateView):
    model = Device
    template_name = "app/device/new_switch.html"
    fields = ["uid", "name", "host", "port", "probability"]
    success_url = reverse_lazy("app:devices")

    def form_valid(self, form):
        form.instance.device_type = 'switch'
        response = super().form_valid(form)
        pid = _launch_device(self.object)
        if pid:
            self.object.pid = pid
            self.object.save(update_fields=['pid'])
        return response

class ClockCreateView(CreateView):
    model = Device
    template_name = "app/device/new_clock.html"
    fields = ["uid", "name", "host", "port", "start_time", "clock_increment", "rate"]
    success_url = reverse_lazy("app:devices")

    def form_valid(self, form):
        form.instance.device_type = 'clock'
        response = super().form_valid(form)
        pid = _launch_device(self.object)
        if pid:
            self.object.pid = pid
            self.object.save(update_fields=['pid'])
        return response

class DeviceUpdateView(UpdateView):
    model = Device
    template_name = "app/device/device_edit.html"
    fields = "__all__"
    success_url = reverse_lazy("app:devices")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        device = self.object
        allowed_fields = ['uid', 'name', 'host', 'port']
        if device.device_type == 'sensor':
            allowed_fields += ['interval', 'min_value', 'max_value', 'sensor_increment']
        elif device.device_type == 'switch':
            allowed_fields += ['probability']
        elif device.device_type == 'clock':
            allowed_fields += ['start_time', 'clock_increment', 'rate']
        for field_name in list(form.fields.keys()):
            if field_name not in allowed_fields:
                del form.fields[field_name]
        return form

    def form_valid(self, form):
        # Matar el proceso antiguo antes de relanzar
        device = self.object
        device.kill_process()
        response = super().form_valid(form)
        pid = _launch_device(self.object)
        if pid:
            self.object.pid = pid
            self.object.save(update_fields=['pid'])
        return response


def device_remove(request, pk):
    device = get_object_or_404(Device, pk=pk)
    device.kill_process()
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
        "name", "trigger_device", "operator", "condition_type",
        "condition_value", "condition_time", "target_device", "action_command",
    ]
    success_url = reverse_lazy("app:rules")

class RuleUpdateView(UpdateView):
    model = Rule
    template_name = "app/rule/rule_edit.html"
    fields = [
        "name", "trigger_device", "operator", "condition_type",
        "condition_value", "condition_time", "target_device", "action_command",
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
