# OPDS Server

📚 Minimal OPDS 1.2 server for browsing a Calibre database.

## Features
- Supports OPDS v1.2
- Opens the Calibre database in read-only mode

## Installation / Run

### With Docker

```bash
docker run --rm -p 9000:8000 \
  -v /path_to_calibre_directory:/app/calibre:ro \
  ghcr.io/victor1234/opds-server:latest
```
Then open http://localhost:8000/opds in your OPDS-compatible reader.
