from __future__ import annotations

from datetime import datetime
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models


class LocationSettings(models.Model):
    """Configuration for a single remote site."""

    location_id = models.CharField(max_length=100, unique=True)
    nvr_endpoint = models.URLField(help_text='Base URL to the Hikvision NVR API')
    nvr_username = models.CharField(max_length=128)
    nvr_password = models.CharField(max_length=256)
    central_server_upload_url = models.URLField(help_text='Central API endpoint for uploads')
    central_server_api_key = models.CharField(max_length=255)
    heartbeat_url = models.URLField(help_text='Central API endpoint for heartbeat payloads')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['location_id']

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"Location {self.location_id}"

    @classmethod
    def load_for_location(cls, location_id: str) -> 'LocationSettings':
        try:
            return cls.objects.get(location_id=location_id)
        except cls.DoesNotExist as exc:  # pragma: no cover - runtime guard
            raise ValidationError(f'No LocationSettings configured for {location_id}') from exc


class NVRPlaybackEvent(models.Model):
    """Represents metadata for a recording segment discovered on an NVR."""

    STATUS_PENDING = 'PENDING'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_COMPLETE = 'COMPLETE'
    STATUS_FAILED = 'FAILED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Transfer'),
        (STATUS_IN_PROGRESS, 'Transfer In Progress'),
        (STATUS_COMPLETE, 'Transfer Complete'),
        (STATUS_FAILED, 'Transfer Failed'),
    ]

    event_id = models.CharField(max_length=128, unique=True)
    location = models.ForeignKey(LocationSettings, on_delete=models.CASCADE, related_name='playback_events')
    camera_channel = models.CharField(max_length=64)
    recording_start = models.DateTimeField()
    recording_end = models.DateTimeField()
    file_path = models.CharField(max_length=512)
    file_size = models.BigIntegerField(help_text='Bytes reported by the NVR', null=True, blank=True)
    nvr_url = models.URLField(help_text='Full URL to fetch the recording segment')
    metadata_payload = models.JSONField(default=dict, blank=True)
    metadata_retrieved_at = models.DateTimeField(auto_now_add=True)
    central_transfer_status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    central_transfer_status_updated_at = models.DateTimeField(auto_now=True)
    transfer_attempts = models.PositiveIntegerField(default=0)
    last_error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-recording_start']
        indexes = [
            models.Index(fields=['central_transfer_status']),
            models.Index(fields=['location', 'camera_channel']),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"Event {self.event_id} ({self.camera_channel})"

    @property
    def duration_seconds(self) -> float:
        delta = self.recording_end - self.recording_start
        return delta.total_seconds()

    def mark_failed(self, message: str) -> None:
        self.central_transfer_status = self.STATUS_FAILED
        self.last_error_message = message[:2000]
        self.save(update_fields=['central_transfer_status', 'last_error_message', 'central_transfer_status_updated_at'])

    def mark_in_progress(self) -> None:
        self.central_transfer_status = self.STATUS_IN_PROGRESS
        self.save(update_fields=['central_transfer_status', 'central_transfer_status_updated_at'])

    def mark_complete(self) -> None:
        self.central_transfer_status = self.STATUS_COMPLETE
        self.save(update_fields=['central_transfer_status', 'central_transfer_status_updated_at', 'transfer_attempts', 'last_error_message'])

    def increment_attempts(self, *, failed: bool = False, error: str | None = None) -> None:
        self.transfer_attempts = models.F('transfer_attempts') + 1
        update_fields: list[str] = ['transfer_attempts']
        if failed:
            self.central_transfer_status = self.STATUS_FAILED
            update_fields.append('central_transfer_status')
            if error:
                self.last_error_message = error[:2000]
                update_fields.append('last_error_message')
        self.save(update_fields=update_fields)
        # Refresh from DB to resolve F expression
        self.refresh_from_db(fields=['transfer_attempts', 'central_transfer_status', 'last_error_message'])

    @classmethod
    def for_transfer(cls) -> models.QuerySet['NVRPlaybackEvent']:
        return cls.objects.filter(central_transfer_status__in=[cls.STATUS_PENDING, cls.STATUS_FAILED])

    def to_payload(self) -> dict[str, Any]:
        return {
            'event_id': self.event_id,
            'location_id': self.location.location_id,
            'camera_channel': self.camera_channel,
            'recording_start': datetime.isoformat(self.recording_start),
            'recording_end': datetime.isoformat(self.recording_end),
            'file_path': self.file_path,
            'file_size': self.file_size,
            'duration_seconds': self.duration_seconds,
            'transfer_attempts': self.transfer_attempts,
            'status': self.central_transfer_status,
        }
