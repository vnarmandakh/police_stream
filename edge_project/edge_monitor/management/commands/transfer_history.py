from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from edge_monitor.models import LocationSettings
from edge_monitor.services.scheduling import transfer_pending_events

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Transfer pending recording segments to the central server.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--location', required=True, help='Location identifier to process')
        parser.add_argument('--limit', type=int, help='Limit the number of transfers per run')

    def handle(self, *args: Any, **options: Any):  # type: ignore[override]
        location_id: str = options['location']
        limit: int | None = options.get('limit')

        location = LocationSettings.load_for_location(location_id)
        self.stdout.write(self.style.NOTICE(f'Transferring pending events for {location.location_id}'))

        results = list(transfer_pending_events(location, limit=limit))
        success_count = len([r for r in results if r.success])
        failure_count = len([r for r in results if not r.success])

        self.stdout.write(self.style.SUCCESS(f'Successful transfers: {success_count}'))
        if failure_count:
            self.stdout.write(self.style.WARNING(f'Failures: {failure_count}'))
        for result in results:
            logger.info('Transfer result for %s: success=%s message=%s', result.event.event_id, result.success, result.message)
