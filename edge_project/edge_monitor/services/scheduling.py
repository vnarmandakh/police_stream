from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import requests
from django.conf import settings

from edge_monitor.models import LocationSettings, NVRPlaybackEvent
from edge_monitor.services.nvr_client import HikvisionNVRClient
from edge_monitor.services.transfer import TransferResult, upload_recording_to_central

logger = logging.getLogger(__name__)


def get_client_for_location(location: LocationSettings) -> HikvisionNVRClient:
    return HikvisionNVRClient(
        base_url=location.nvr_endpoint,
        username=location.nvr_username,
        password=location.nvr_password,
    )


def fetch_and_store_metadata(
    *,
    location: LocationSettings,
    channel: str,
    start_time: datetime,
    end_time: datetime,
) -> list[NVRPlaybackEvent]:
    client = get_client_for_location(location)
    events: list[NVRPlaybackEvent] = []
    for segment in client.search_recordings(channel=channel, start_time=start_time, end_time=end_time):
        event, created = NVRPlaybackEvent.objects.update_or_create(
            event_id=segment.event_id,
            defaults={
                'location': location,
                'camera_channel': segment.channel,
                'recording_start': segment.start_time,
                'recording_end': segment.end_time,
                'file_path': segment.file_path,
                'file_size': segment.file_size,
                'nvr_url': segment.playback_url,
                'metadata_payload': segment.raw_payload,
                'central_transfer_status': NVRPlaybackEvent.STATUS_PENDING,
            },
        )
        events.append(event)
        logger.info('Discovered event %s for %s (created=%s)', event.event_id, location.location_id, created)
    return events


def transfer_pending_events(location: LocationSettings, *, limit: int | None = None) -> Iterable[TransferResult]:
    client = get_client_for_location(location)
    queryset = location.playback_events.filter(central_transfer_status__in=[
        NVRPlaybackEvent.STATUS_PENDING,
        NVRPlaybackEvent.STATUS_FAILED,
    ]).order_by('central_transfer_status_updated_at')
    if limit:
        queryset = queryset[:limit]
    for event in queryset:
        if event.transfer_attempts >= settings.EDGE_RETRY_LIMIT:
            logger.warning('Skipping event %s due to retry limit', event.event_id)
            continue
        yield upload_recording_to_central(event=event, location_settings=location, nvr_client=client)


def send_heartbeat(location: LocationSettings) -> None:
    payload = {
        'location_id': location.location_id,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'failed_events': location.playback_events.filter(
            central_transfer_status=NVRPlaybackEvent.STATUS_FAILED
        ).count(),
    }
    headers = {
        'X-API-Key': location.central_server_api_key,
        'Content-Type': 'application/json',
    }
    try:
        response = requests.post(location.heartbeat_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        logger.debug('Heartbeat sent for %s', location.location_id)
    except Exception as exc:  # pragma: no cover - network failure
        logger.exception('Failed heartbeat for %s: %s', location.location_id, exc)
