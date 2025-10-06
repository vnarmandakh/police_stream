# Edge Police Stream Project

This Django project orchestrates communication between distributed Hikvision NVR devices and a centralized evidence management platform. It focuses on four pillars described in the provided prompt set:

1. **Metadata Extraction** – Django management commands and services query Hikvision ISAPI search endpoints, persisting results as `NVRPlaybackEvent` records.
2. **File Transfer** – Streaming transfers move recording segments from the NVR to the central server, tracking success/failure state on the model.
3. **Asynchronous Scheduling** – Commands are designed for cron/Celery style execution, with retry controls and logging hooks.
4. **Configuration & Heartbeats** – `LocationSettings` stores NVR and central server credentials while periodic heartbeats keep the central system informed about local health.

## Project Layout

```
edge_project/
├── manage.py
├── edge_project/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── edge_monitor/
│   ├── models.py
│   ├── apps.py
│   ├── services/
│   │   ├── nvr_client.py
│   │   ├── scheduling.py
│   │   └── transfer.py
│   └── management/
│       └── commands/
│           ├── fetch_nvr_metadata.py
│           ├── transfer_history.py
│           └── send_heartbeat.py
└── requirements.txt
```

## Key Components

### Models

- `LocationSettings` captures the per-site configuration: NVR endpoint, credentials, and central API details.
- `NVRPlaybackEvent` tracks discovered recordings and transfer lifecycle metadata.

### Services

- `HikvisionNVRClient` (`services/nvr_client.py`) wraps Hikvision ISAPI search and download behaviour with HTTP Digest authentication.
- `services/transfer.py` streams recordings from the NVR into the central server upload API with resilient status updates.
- `services/scheduling.py` orchestrates metadata fetches, transfer loops, and heartbeat emissions.

### Management Commands

- `fetch_nvr_metadata` – Use for scheduled metadata polling.
- `transfer_history` – Moves pending/failed segments to the central server.
- `send_heartbeat` – Posts a heartbeat payload summarising edge health.

## Getting Started

Install dependencies inside a virtual environment and run migrations. You can
either execute the repository's `bootstrap.sh` helper from the repo root or run
the commands manually as shown below.

```bash
./bootstrap.sh
```

If you prefer to perform the steps yourself:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
```

> **Note:** Debian-based systems ship with an *externally managed* Python where the
> global `pip` executable is disabled. Creating a virtual environment (or using
> the `bootstrap.sh` helper) ensures the dependencies install cleanly without
> requiring system package changes.

Then configure a `LocationSettings` record (via admin or Django shell) before invoking the management commands, e.g.:

```bash
python manage.py fetch_nvr_metadata --location HQ --channel 1 --hours 2
python manage.py transfer_history --location HQ
python manage.py send_heartbeat --location HQ
```

These commands are idempotent and designed to be orchestrated by cron or Celery beat as appropriate for the deployment.
