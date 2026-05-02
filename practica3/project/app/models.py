from django.db import models


class Device(models.Model):
    DEVICE_TYPES = [
        ('sensor', 'Sensor'),
        ('switch', 'Switch'),
        ('clock', 'Clock'),
    ]

    # --- Campos Obligatorios (Comunes) ---
    uid = models.CharField(max_length=100, unique=True, help_text="Identificador único (ej. 1)")
    name = models.CharField(max_length=100, help_text="Nombre descriptivo")
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPES, default='sensor')

    # --- Campos No Obligatorios (Comunes) ---
    host = models.CharField(max_length=100, default="localhost", blank=True, null=True)
    port = models.IntegerField(default=1883, blank=True, null=True)

    # --- Específicos de Switch (No obligatorios) ---
    probability = models.FloatField(blank=True, null=True, help_text="Probabilidad de fallo (0.0 a 1.0)")

    # --- Específicos de Sensor (No obligatorios) ---
    interval = models.FloatField(blank=True, null=True, help_text="Intervalo en segundos")
    min_value = models.IntegerField(blank=True, null=True, help_text="Valor mínimo")
    max_value = models.IntegerField(blank=True, null=True, help_text="Valor máximo")
    sensor_increment = models.IntegerField(blank=True, null=True, help_text="Incremento")

    # --- Específicos de Clock (No obligatorios) ---
    start_time = models.CharField(max_length=8, blank=True, null=True, help_text="Hora de inicio (HH:MM:SS)")
    clock_increment = models.IntegerField(blank=True, null=True, help_text="Incremento en segundos")
    rate = models.FloatField(blank=True, null=True, help_text="Frecuencia (mensajes por segundo)")

    def __str__(self):
        return f"{self.name} ({self.uid}) - {self.get_device_type_display()}"
    def get_last_event(self):
        # Busca el evento más reciente para este dispositivo específico
        return Event.objects.filter(device_uid=self.uid).order_by('-timestamp').first()


class Rule(models.Model):
    OPERATOR_CHOICES = [
        ("==", "Igual a"),
        (">", "Mayor que"),
        ("<", "Menor que"),
    ]

    CONDITION_TYPE_CHOICES = [
        ("numeric", "Numérico"),
        ("time", "Hora (HH:MM:SS)"),
    ]

    name = models.CharField(max_length=100, help_text="Nombre de la regla")
    trigger_device = models.ForeignKey(
        Device,
        related_name="rules_triggered",
        on_delete=models.CASCADE,
        help_text="Dispositivo que dispara la regla",
    )
    operator = models.CharField(
        max_length=2, choices=OPERATOR_CHOICES, help_text="Operador de comparación"
    )
    condition_type = models.CharField(
        max_length=10,
        choices=CONDITION_TYPE_CHOICES,
        default="numeric",
        help_text="Tipo de condición: numérica o de hora",
    )
    condition_value = models.FloatField(
        help_text="Valor numérico a comparar (si el tipo es numérico)",
        null=True,
        blank=True,
    )
    condition_time = models.CharField(
        max_length=8,
        help_text="Hora a comparar en formato HH:MM:SS (si el tipo es hora)",
        null=True,
        blank=True,
    )
    target_device = models.ForeignKey(
        Device,
        related_name="rules_targeted",
        on_delete=models.CASCADE,
        help_text="Dispositivo sobre el que se realizará la acción",
    )
    action_command = models.CharField(
        max_length=50, help_text="Comando a enviar (ej. ON, OFF)"
    )

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.condition_type == "numeric" and self.condition_value is None:
            raise ValidationError("Se requiere un valor numérico para condiciones de tipo numérico.")
        if self.condition_type == "time" and not self.condition_time:
            raise ValidationError("Se requiere una hora en formato HH:MM:SS para condiciones de tipo hora.")

    def __str__(self):
        if self.condition_type == "time":
            cond = self.condition_time
        else:
            cond = self.condition_value
        return f"{self.name}: Si {self.trigger_device.uid} {self.operator} {cond} -> {self.target_device.uid} = {self.action_command}"


class Event(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    device_uid = models.CharField(max_length=100)
    event_type = models.CharField(
        max_length=50
    )  # Ejemplo: "TELEMETRÍA", "ACCIÓN", "ERROR"
    description = models.TextField()

    class Meta:
        ordering = ["-timestamp"]  # Para ver los más recientes primero

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.device_uid}: {self.description}"
