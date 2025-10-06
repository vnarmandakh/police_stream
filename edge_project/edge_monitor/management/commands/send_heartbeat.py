from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from edge_monitor.models import LocationSettings
from edge_monitor.services.scheduling import send_heartbeat


class Command(BaseCommand):
    help = 'Send heartbeat payloads to the central server.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--location', required=True, help='Location identifier to heartbeat')

    def handle(self, *args, **options):  # type: ignore[override]
        location_id: str = options['location']
        location = LocationSettings.load_for_location(location_id)
        self.stdout.write(self.style.NOTICE(f'Sending heartbeat for {location.location_id}'))
        send_heartbeat(location)
        self.stdout.write(self.style.SUCCESS('Heartbeat dispatched.'))
        self.stdout.write(self.style.NOTICE(f'Heartbeat interval is {settings.EDGE_HEARTBEAT_INTERVAL_SECONDS}s'))
