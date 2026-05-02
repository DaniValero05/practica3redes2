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


class DeviceCreateView(CreateView):
    model = Device
    template_name = "app/device/new.html"
    fields = ["uid", "name", "is_sensor"]
    success_url = reverse_lazy("app:devices")


class DeviceUpdateView(UpdateView):
    model = Device
    template_name = "app/device/edit.html"
    fields = ["uid", "name", "is_sensor"]
    success_url = reverse_lazy("app:devices")


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
