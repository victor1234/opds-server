# OPDS Server

📚 Minimal OPDS 1.2 server for browsing a Calibre database.

## Features
- Supports OPDS v1.2
- Opens the Calibre database in read-only mode

## Service Endpoints
- `/healthz` → *liveness probe* (returns `200` if the server process is alive)
- `/ready` → *readiness probe* (returns `200` if the Calibre database is available)

## Configuration

The server can be configured using environment variables

| Variable               | Default  | Description                                      |
|------------------------|----------|--------------------------------------------------|
| `PAGE_SIZE`            | `30`     | Number of items (books, authors) shown per page in OPDS feeds. |


## Installation / Run

### With Docker

```bash
docker run --rm -p 9000:8000 \
  -v /path_to_calibre_directory:/app/calibre:ro \
  ghcr.io/victor1234/opds-server:latest
```

### With Docker Compose
```yaml
services:
  opds:
    build: .
    ports:
      - "9000:8000"
    volumes:
      - /path_to_calibre_directory:/app/calibre:ro
```
Then open http://localhost:9000/opds in your OPDS-compatible reader.
