import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from opds_server.core.config import Config, get_config
from opds_server.db.access import get_db_path
from opds_server.main import create_app


def make_library(tmp_path: Path, folder: str = "Author/Book", name: str = "Novel"):
    library = tmp_path / "library"
    library.mkdir()
    connection = sqlite3.connect(library / "metadata.db")
    connection.executescript(
        """
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, path TEXT);
        CREATE TABLE data (book INTEGER, format TEXT, name TEXT);
        """
    )
    connection.execute("INSERT INTO books VALUES (1, 'Test Book', ?)", (folder,))
    connection.execute("INSERT INTO data VALUES (1, 'EPUB', ?)", (name,))
    connection.commit()
    connection.close()

    config = Config(calibre_library_path=library)
    app = create_app(config)
    app.dependency_overrides[get_config] = lambda: config
    return library, TestClient(app)


def test_nested_book_and_cover_are_served(tmp_path: Path):
    library, client = make_library(tmp_path)
    book_dir = library / "Author" / "Book"
    book_dir.mkdir(parents=True)
    (book_dir / "Novel.epub").write_bytes(b"book contents")
    (book_dir / "cover.jpg").write_bytes(b"cover contents")

    book = client.get("/opds/book/1/file/epub")
    cover = client.get("/opds/book/1/cover")

    assert book.status_code == 200
    assert book.content == b"book contents"
    assert cover.status_code == 200
    assert cover.content == b"cover contents"


def test_internal_symlinks_are_served(tmp_path: Path):
    library, client = make_library(tmp_path, folder="links", name="linked")
    target = library / "stored"
    target.mkdir()
    (target / "book.epub").write_bytes(b"internal book")
    (target / "image.jpg").write_bytes(b"internal cover")
    links = library / "links"
    links.mkdir()
    (links / "linked.epub").symlink_to(target / "book.epub")
    (links / "cover.jpg").symlink_to(target / "image.jpg")

    assert client.get("/opds/book/1/file/epub").content == b"internal book"
    assert client.get("/opds/book/1/cover").content == b"internal cover"


@pytest.mark.parametrize("folder", ["../outside", "/tmp/outside"])
def test_database_controlled_folder_cannot_escape(tmp_path: Path, folder: str):
    _, client = make_library(tmp_path, folder=folder)

    book = client.get("/opds/book/1/file/epub")
    cover = client.get("/opds/book/1/cover")

    assert (book.status_code, book.text) == (404, "Book file not found")
    assert (cover.status_code, cover.text) == (404, "Cover not found")


def test_escaping_symlinks_are_rejected(tmp_path: Path):
    library, client = make_library(tmp_path, folder="links", name="outside")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "outside.epub").write_bytes(b"secret book")
    (outside / "cover.jpg").write_bytes(b"secret cover")
    links = library / "links"
    links.mkdir()
    (links / "outside.epub").symlink_to(outside / "outside.epub")
    (links / "cover.jpg").symlink_to(outside / "cover.jpg")

    assert client.get("/opds/book/1/file/epub").status_code == 404
    assert client.get("/opds/book/1/cover").status_code == 404


@pytest.mark.parametrize("target_kind", ["missing", "directory"])
def test_missing_files_and_directories_return_404(tmp_path: Path, target_kind: str):
    library, client = make_library(tmp_path)
    book_dir = library / "Author" / "Book"
    book_dir.mkdir(parents=True)
    if target_kind == "directory":
        (book_dir / "Novel.epub").mkdir()
        (book_dir / "cover.jpg").mkdir()

    assert client.get("/opds/book/1/file/epub").status_code == 404
    assert client.get("/opds/book/1/cover").status_code == 404


@pytest.mark.parametrize("db_kind", ["missing", "escaping_symlink"])
def test_invalid_database_error_does_not_leak_paths(tmp_path: Path, db_kind: str):
    library = tmp_path / "library"
    library.mkdir()
    if db_kind == "escaping_symlink":
        outside = tmp_path / "private-metadata.db"
        outside.write_bytes(b"not relevant")
        (library / "metadata.db").symlink_to(outside)

    with pytest.raises(HTTPException) as caught:
        get_db_path(Config(calibre_library_path=library))

    assert caught.value.status_code == 500
    assert caught.value.detail == "Calibre DB not found"
    assert str(tmp_path) not in caught.value.detail
