from __future__ import annotations

import io
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

import requests

from edge_monitor.models import LocationSettings, NVRPlaybackEvent
from edge_monitor.services.nvr_client import HikvisionNVRClient, NVRRecordingSegment

logger = logging.getLogger(__name__)


@dataclass
class TransferResult:
    event: NVRPlaybackEvent
    success: bool
    message: str = ''


@contextmanager
def _streaming_response(response: requests.Response) -> Iterator[io.BufferedReader]:
    try:
        yield response.raw  # type: ignore[return-value]
    finally:
        response.close()


def initiate_video_retrieval(event: NVRPlaybackEvent, nvr_client: HikvisionNVRClient) -> NVRRecordingSegment:
    """Retrieve the latest metadata for the event and prepare for download."""

    segment = NVRRecordingSegment(
        event_id=event.event_id,
        channel=event.camera_channel,
        start_time=event.recording_start,
        end_time=event.recording_end,
        file_path=event.file_path,
        file_size=event.file_size,
        playback_url=event.nvr_url,
        raw_payload=event.metadata_payload,
    )
    return segment


def upload_recording_to_central(
    *,
    event: NVRPlaybackEvent,
    location_settings: LocationSettings,
    nvr_client: HikvisionNVRClient,
    chunk_size: int = 1024 * 1024,
) -> TransferResult:
    """Upload the recording to the central server via streaming POST."""

    try:
        event.mark_in_progress()
        segment = initiate_video_retrieval(event, nvr_client)
        response = nvr_client.download_segment(segment)
    except Exception as exc:  # pragma: no cover - network failure
        logger.exception('Failed to download segment %s', event.event_id)
        event.increment_attempts(failed=True, error=str(exc))
        return TransferResult(event=event, success=False, message=str(exc))

    headers = {
        'X-API-Key': location_settings.central_server_api_key,
        'Content-Type': 'application/octet-stream',
        'X-Event-ID': event.event_id,
        'X-Location-ID': location_settings.location_id,
        'X-Recording-Start': event.recording_start.isoformat(),
        'X-Recording-End': event.recording_end.isoformat(),
    }

    with _streaming_response(response) as file_stream:
        try:
            upload_response = requests.post(
                location_settings.central_server_upload_url,
                data=iter(lambda: file_stream.read(chunk_size), b''),
                headers=headers,
                timeout=120,
            )
            upload_response.raise_for_status()
        except Exception as exc:  # pragma: no cover - network failure
            logger.exception('Upload failed for event %s', event.event_id)
            event.increment_attempts(failed=True, error=str(exc))
            return TransferResult(event=event, success=False, message=str(exc))

    event.increment_attempts()
    event.mark_complete()
    return TransferResult(event=event, success=True, message='Uploaded successfully')
