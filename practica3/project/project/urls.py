from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # Redirigir el tráfico hacía las rutas definidas en nuestra app
    path("", include("app.urls")),
]
