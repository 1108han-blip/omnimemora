# Legacy Docker Development Files - ARCHIVED

**This directory contains legacy Docker-based development artifacts.**

**Superseded by**: OmniMemora Go Runtime (local-runtime/) - native binary deployment

Files:
- docker-compose.yml / docker-compose.full.yml - Old multi-container setup
- Dockerfile - Python adapter container (port 8000)
- openviking.Dockerfile - OpenViking container (port 1933)
- start.sh - Old Docker startup script
- requirements.txt - Python dependencies

**Current Architecture (2026-04-14)**:
- OmniMemora Runtime: Go binary, port 8765 (dynamic fallback)
- Memory Adapter: Python/Go, port 18011
- OpenViking Backend: port 1933 (optional, for legacy compatibility)

These Docker files are kept for reference only and should not be used for new deployments.

