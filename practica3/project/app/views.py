from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    TemplateView,
)
from .models import Device, Rule, Event


class IndexView(TemplateView):
    template_name = "app/index.html"


class DeviceListView(ListView):
    model = Device
    template_name = "app/device/list.html"
    context_object_name = "devices"


class DeviceDetailView(DetailView):
    model = Device
    template_name = "app/device/detail.html"
    context_object_name = "device"


class DeviceTypeSelectView(TemplateView):
    # Esta vista solo carga el HTML con los botones de selección
    template_name = "app/device/new.html"

class SensorCreateView(CreateView):
    model = Device
    template_name = "app/device/new_sensor.html"
    fields = ["uid", "name", "host", "port", "interval", "min_value", "max_value", "sensor_increment"]
    success_url = reverse_lazy("app:devices")
    
    def form_valid(self, form):
        form.instance.device_type = 'sensor' # Fuerza el tipo automáticamente
        return super().form_valid(form)

class SwitchCreateView(CreateView):
    model = Device
    template_name = "app/device/new_switch.html"
    fields = ["uid", "name", "host", "port", "probability"]
    success_url = reverse_lazy("app:devices")

    def form_valid(self, form):
        form.instance.device_type = 'switch'
        return super().form_valid(form)

class ClockCreateView(CreateView):
    model = Device
    template_name = "app/device/new_clock.html"
    fields = ["uid", "name", "host", "port", "start_time", "clock_increment", "rate"]
    success_url = reverse_lazy("app:devices")

    def form_valid(self, form):
        form.instance.device_type = 'clock'
        return super().form_valid(form)


def device_remove(request, pk):
    device = get_object_or_404(Device, pk=pk)
    device.delete()
    return redirect("app:devices")


class RuleListView(ListView):
    model = Rule
    template_name = "app/rule/list.html"
    context_object_name = "rules"


class RuleCreateView(CreateView):
    model = Rule
    template_name = "app/rule/new.html"
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
    template_name = "app/rule/edit.html"
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
    template_name = "app/event/list.html"
    context_object_name = "events"
    paginate_by = 20


def rule_remove(request, pk):
    rule = get_object_or_404(Rule, pk=pk)
    rule.delete()
    return redirect("app:rules")
