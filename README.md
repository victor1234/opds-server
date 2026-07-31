# OPDS Server

[![CI](https://github.com/victor1234/opds-server/actions/workflows/ci.yml/badge.svg)](https://github.com/victor1234/opds-server/actions/workflows/ci.yml)
[![Docker Image](https://img.shields.io/badge/docker-ghcr.io-blue)](https://ghcr.io/victor1234/opds-server)

📚 A minimal, read-only OPDS 1.2 server for existing Calibre libraries.

It is designed for containerized deployments where books are managed with
Calibre but accessed through OPDS-compatible reader applications. The server
provides catalog browsing and book acquisition without a web interface or
library management features.

## Features

- OPDS 1.2 navigation, acquisition, and search feeds
- Browse books by newest, title, or author
- Download available book formats from OPDS-compatible readers
- Read-only access to existing Calibre libraries
- Multi-architecture Docker images for `amd64` and `arm64`
- Liveness and readiness endpoints for container orchestration

## Installation / Run

Mount the root directory of an existing Calibre library. It must contain
`metadata.db` together with the author and book directories managed by Calibre.
The container accesses the library read-only and does not modify its contents.

### Docker

```bash
docker run --rm -p 9000:8000 \
    -v /path/to/calibre-library:/app/calibre:ro \
    ghcr.io/victor1234/opds-server:0.1.3
```

### Docker Compose

```yaml
services:
  opds-server:
    image: ghcr.io/victor1234/opds-server:0.1.3
    restart: unless-stopped
    ports:
      - 9000:8000
    volumes:
      - /path/to/calibre-library:/app/calibre:ro
```

Verify that the library is available:

```bash
curl http://<server-address>:9000/ready
```
Then add `http://<server-address>:9000/opds` to your OPDS-compatible reader.

## Configuration

The server can be configured using environment variables:

| Variable               | Default  | Description                                                                                      |
| ---------------------- | -------- | ------------------------------------------------------------------------------------------------ |
| `PAGE_SIZE`            | `30`     | Number of books or authors shown on each OPDS feed page, from 1 through 100                      |
| `OPDS_PREFIX`          | `/opds`  | URL path where the catalog is mounted. A leading slash is optional; trailing slashes are removed |

The server starts when the configured library is temporarily unavailable so
that `/healthz` can continue to report process liveness. `/ready` checks the
library on every request and returns `503 Calibre database unavailable` until
`metadata.db` can be accessed.

## Probe Endpoints

- `/healthz` → *liveness probe* (returns `200` if the server process is alive)
- `/ready` → *readiness probe* (returns `200` if the Calibre database is available)
