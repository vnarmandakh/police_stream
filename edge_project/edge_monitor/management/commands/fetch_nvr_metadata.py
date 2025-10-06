from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from django.core.management.base import BaseCommand, CommandParser

from edge_monitor.models import LocationSettings
from edge_monitor.services.scheduling import fetch_and_store_metadata

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Pull recording metadata from the configured Hikvision NVR.'

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument('--location', required=True, help='Location identifier to poll')
        parser.add_argument('--channel', default='1', help='NVR channel identifier')
        parser.add_argument('--hours', type=int, default=1, help='Window (hours) to search backwards from now')
        parser.add_argument('--start', help='Explicit ISO start time (UTC)')
        parser.add_argument('--end', help='Explicit ISO end time (UTC)')

    def handle(self, *args, **options):  # type: ignore[override]
        location_id: str = options['location']
        channel: str = options['channel']
        hours: int = options['hours']

        location = LocationSettings.load_for_location(location_id)

        if options.get('start'):
            start = datetime.fromisoformat(options['start']).astimezone(timezone.utc)
        else:
            start = datetime.now(timezone.utc) - timedelta(hours=hours)

        if options.get('end'):
            end = datetime.fromisoformat(options['end']).astimezone(timezone.utc)
        else:
            end = datetime.now(timezone.utc)

        self.stdout.write(
            self.style.NOTICE(
                f'Fetching metadata for {location.location_id} channel {channel} between {start.isoformat()} and {end.isoformat()}'
            )
        )

        events = fetch_and_store_metadata(location=location, channel=channel, start_time=start, end_time=end)
        self.stdout.write(self.style.SUCCESS(f'Fetched {len(events)} events.'))
        for event in events:
            logger.debug('Event stored: %s', event)
