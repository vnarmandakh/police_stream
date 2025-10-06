from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from xml.etree import ElementTree

import requests
from requests.auth import HTTPDigestAuth


logger = logging.getLogger(__name__)


@dataclass
class NVRRecordingSegment:
    event_id: str
    channel: str
    start_time: datetime
    end_time: datetime
    file_path: str
    file_size: int | None
    playback_url: str
    raw_payload: dict


class HikvisionNVRClient:
    """Minimal Hikvision client that wraps the ISAPI search APIs."""

    def __init__(self, *, base_url: str, username: str, password: str, timeout: int = 30) -> None:
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        data: str | None = None,
        stream: bool = False,
    ) -> requests.Response:
        if path.startswith('http://') or path.startswith('https://'):
            url = path
        else:
            url = f"{self.base_url}/{path.lstrip('/')}"
        logger.debug('Requesting %s %s', method, url)
        response = requests.request(
            method,
            url,
            params=params,
            data=data,
            timeout=self.timeout,
            auth=HTTPDigestAuth(self.username, self.password),
            headers={'Content-Type': 'application/xml'} if data else None,
            stream=stream,
        )
        response.raise_for_status()
        return response

    def search_recordings(self, *, channel: str, start_time: datetime, end_time: datetime) -> Iterable[NVRRecordingSegment]:
        """Perform an ISAPI search against the NVR and yield segments."""

        search_payload = f"""
            <CMSearchDescription>
              <searchID>1</searchID>
              <trackList><trackID>{channel}</trackID></trackList>
              <timeSpanList>
                <timeSpan>
                  <startTime>{start_time.strftime('%Y-%m-%dT%H:%M:%SZ')}</startTime>
                  <endTime>{end_time.strftime('%Y-%m-%dT%H:%M:%SZ')}</endTime>
                </timeSpan>
              </timeSpanList>
              <maxResults>40</maxResults>
              <searchResultPostion>0</searchResultPostion>
              <metadataList>
                <metadataDescriptor>//recordType.meta.hikvision.com/VideoMotion</metadataDescriptor>
              </metadataList>
            </CMSearchDescription>
        """.strip()

        response = self._request('POST', 'ISAPI/ContentMgmt/search', data=search_payload)
        root = ElementTree.fromstring(response.content)
        match_list = root.find('matchList')
        if match_list is None:
            return

        for match in match_list.findall('match'):  # type: ignore[attr-defined]
            match_id = match.findtext('matchID', default='')
            track_id = match.findtext('trackID', default=channel)
            time_span = match.find('timeSpan')
            if time_span is None:
                continue
            start_text = time_span.findtext('startTime')
            end_text = time_span.findtext('endTime')
            if not start_text or not end_text:
                continue

            metadata_list = match.find('metadataList')
            playback_uri = None
            file_size = None
            raw_payload = ElementTree.tostring(match, encoding='unicode')
            if metadata_list is not None:
                metadata = metadata_list.find('metadata')
                if metadata is not None:
                    video_motion = metadata.find('VideoMotion')
                    if video_motion is not None:
                        playback_uri = video_motion.findtext('playbackURI')
                        file_size_text = video_motion.findtext('fileSize')
                        if file_size_text:
                            try:
                                file_size = int(file_size_text)
                            except ValueError:
                                file_size = None
            file_path = playback_uri or f'/Streaming/tracks/{track_id}.mp4'
            yield NVRRecordingSegment(
                event_id=match_id,
                channel=str(track_id),
                start_time=datetime.fromisoformat(start_text.replace('Z', '+00:00')),
                end_time=datetime.fromisoformat(end_text.replace('Z', '+00:00')),
                file_path=file_path,
                file_size=file_size,
                playback_url=f"{self.base_url}{file_path}" if not file_path.startswith('http') else file_path,
                raw_payload={'match': raw_payload},
            )

    def download_segment(self, segment: NVRRecordingSegment) -> requests.Response:
        """Download a specific recording segment."""

        response = self._request('GET', segment.playback_url, stream=True)
        return response
