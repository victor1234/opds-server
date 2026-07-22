# OPDS Server

[![CI](https://github.com/victor1234/opds-server/actions/workflows/ci.yml/badge.svg)](https://github.com/victor1234/opds-server/actions/workflows/ci.yml)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-blue)](https://ghcr.io/victor1234/opds-server)



📚 Minimal OPDS 1.2 server for browsing a Calibre database.

## Features
- OPDS v1.2 compliant feeds (navigation, acquisition, search)
- Browse by newest, title, or author
- Prebuilt multi-arch Docker images for `amd64` and `arm64`
- Read-only access to Calibre database

## Service Endpoints
- `/healthz` → *liveness probe* (returns `200` if the server process is alive)
- `/ready` → *readiness probe* (returns `200` if the Calibre database is available)

## Configuration

The server can be configured using environment variables

| Variable               | Default  | Description                                      |
|------------------------|----------|--------------------------------------------------|
| `PAGE_SIZE`            | `30`     | Number of items (books, authors) shown per page in OPDS feeds. |


## Installation / Run

### Docker

```bash
docker run --rm -p 9000:8000 \
  -v /path_to_calibre_directory:/app/calibre:ro \
  ghcr.io/victor1234/opds-server:0.1.2
```

### Docker Compose
```yaml
services:
  opds:
    image: ghcr.io/victor1234/opds-server:0.1.2
    ports:
      - "9000:8000"
    volumes:
      - /path_to_calibre_directory:/app/calibre:ro
```
Then open http://localhost:9000/opds in your OPDS-compatible reader.
