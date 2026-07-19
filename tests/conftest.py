"""Shared database-backed fixtures for OPDS endpoint integration tests."""

import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from opds_server.core.config import Config, get_config
from opds_server.main import create_app

CALIBRE_SCHEMA = """
CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT NOT NULL, sort TEXT NOT NULL, last_modified TEXT, path TEXT NOT NULL);
CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT NOT NULL, sort TEXT NOT NULL);
CREATE TABLE books_authors_link (book INTEGER NOT NULL, author INTEGER NOT NULL);
CREATE TABLE data (book INTEGER NOT NULL, format TEXT NOT NULL, name TEXT NOT NULL);
"""


def _populate_library(connection: sqlite3.Connection, library: Path) -> None:
    """Populate a compact catalog containing pagination and escaping edge
    cases."""
    connection.executemany(
        "INSERT INTO authors VALUES (?, ?, ?)",
        [(1, "Ada & Sons", "Ada & Sons"), (2, "Zoë Автор", "Zoe Author")],
    )
    connection.executemany(
        "INSERT INTO books VALUES (?, ?, ?, ?, ?)",
        [
            (
                1,
                "A <Practical> Book",
                "A Practical Book",
                "2024-01-04 12:00:00+00:00",
                "Ada/Practical",
            ),
            (
                2,
                "100% Unicode книга",
                "100 Unicode",
                "2024-01-03 12:00:00+00:00",
                "Zoe/Unicode",
            ),
            (
                3,
                "Under_score",
                "Under score",
                "2024-01-02 12:00:00+00:00",
                "Shared/Under",
            ),
            (
                4,
                "Authorless",
                "Authorless",
                "2024-01-01 12:00:00+00:00",
                "Nobody/Authorless",
            ),
        ],
    )
    connection.executemany(
        "INSERT INTO books_authors_link VALUES (?, ?)",
        [(1, 1), (1, 2), (2, 2), (3, 1)],
    )
    connection.executemany(
        "INSERT INTO data VALUES (?, ?, ?)",
        [(1, "EPUB", "Practical"), (1, "PDF", "Practical"), (2, "EPUB", "Unicode")],
    )
    for relative_path, contents in {
        "Ada/Practical/Practical.epub": b"epub contents",
        "Ada/Practical/Practical.pdf": b"pdf contents",
        "Ada/Practical/cover.jpg": b"jpeg contents",
        "Zoe/Unicode/Unicode.epub": b"unicode contents",
    }.items():
        target = library / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)


@pytest.fixture
def client_factory(tmp_path: Path) -> Callable[..., tuple[Path, TestClient]]:
    """Build isolated apps backed by a minimal read-only Calibre-style
    database."""
    sequence = 0

    def make_client(
        *, populated: bool = True, page_size: int = 2
    ) -> tuple[Path, TestClient]:
        nonlocal sequence
        sequence += 1
        library = tmp_path / f"library-{sequence}"
        library.mkdir()
        connection = sqlite3.connect(library / "metadata.db")
        connection.executescript(CALIBRE_SCHEMA)
        if populated:
            _populate_library(connection, library)
        connection.commit()
        connection.close()

        config = Config(calibre_library_path=library, page_size=page_size)
        app = create_app(config)
        app.dependency_overrides[get_config] = lambda: config
        return library, TestClient(app, raise_server_exceptions=False)

    return make_client


@pytest.fixture
def catalog_client(client_factory) -> tuple[Path, TestClient]:
    """Return the standard populated library and its isolated test client."""
    return client_factory()
