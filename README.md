# Police Stream Edge Project

This repository contains a Django-based edge service that bridges Hikvision DS-7716NI-Q4 NVRs with a centralized evidence platform. The implementation follows the supplied architectural prompts and delivers:

- Management commands for metadata harvesting, transfer orchestration, and heartbeat reporting.
- Models for tracking per-location configuration and NVR playback events with transfer status.
- Service abstractions that encapsulate Hikvision ISAPI communication and resilient HTTP uploads to the central system.

See [`edge_project/README.md`](edge_project/README.md) for detailed setup and usage instructions.
