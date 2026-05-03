from django.urls import path
from . import views

app_name = "app"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("devices/", views.DeviceListView.as_view(), name="devices"),
    path("device/new/", views.DeviceTypeSelectView.as_view(), name="device_new"),
    path("device/<int:pk>/remove/", views.device_remove, name="device_remove"),
    path("rules/", views.RuleListView.as_view(), name="rules"),
    path("rule/new/", views.RuleCreateView.as_view(), name="rule_new"),
    path("rule/<int:pk>/edit/", views.RuleUpdateView.as_view(), name="rule_edit"),
    path("rule/<int:pk>/remove/", views.rule_remove, name="rule_remove"),
    path("events/", views.EventListView.as_view(), name="events"),
    path("device/new/sensor/", views.SensorCreateView.as_view(), name="device_new_sensor"),
    path("device/new/switch/", views.SwitchCreateView.as_view(), name="device_new_switch"),
    path("device/new/clock/", views.ClockCreateView.as_view(), name="device_new_clock"),
    path("device/<int:pk>/edit/", views.DeviceUpdateView.as_view(), name="device_edit"),
]
