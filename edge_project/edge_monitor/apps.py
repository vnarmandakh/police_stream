from __future__ import annotations

from django.apps import AppConfig


class EdgeMonitorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'edge_monitor'
    verbose_name = 'Edge Monitoring'
