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

| Variable | Default | Description |
|---|---|---|
| `CALIBRE_LIBRARY_PATH` | `/books` | Absolute path to the mounted Calibre library. |
| `PAGE_SIZE` | `30` | Number of books or authors shown on each OPDS feed page, from 1 through 100. |
| `OPDS_PREFIX` | `/opds` | URL path where the catalog is mounted. A leading slash is optional; trailing slashes are removed. |

The server starts when the configured library is temporarily unavailable so
that `/healthz` can continue to report process liveness. `/ready` checks the
library on every request and returns `503 Calibre database unavailable` until
`metadata.db` can be accessed.

## Pagination

Catalog feeds use page numbers from 1 through 10,000 and offset pagination.
Each request reads the current Calibre database, so books added or removed
between page requests can cause entries to be repeated or skipped during a
traversal. Keyset pagination is deferred unless benchmarks on large libraries
show that changing the page-number interface would provide a material benefit.

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

## CI security policy

Before publishing container images, CI scans the locked Python environment and
a locally built `linux/amd64` image for known vulnerabilities. Any `HIGH` or
`CRITICAL` finding blocks publication, including findings without an available
fix. Lower-severity findings remain visible in the scanner output but do not
block a release.
