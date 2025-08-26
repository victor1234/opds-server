import hashlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import HTTPException
from datetime import datetime
from collections import defaultdict
from opds_server.core.config import Config
import aiosqlite


def get_db_path(config: Config) -> Path:
    """Get absolute path to the Calibre metadata.db and ensure it exists."""
    base = config.calibre_library_path
    path = Path(base, "metadata.db").resolve()
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Calibre DB not found at {path}")
    return path


def get_db_uri(config: Config) -> str:
    return f"file:{get_db_path(config)}?mode=ro"


@asynccontextmanager
async def connect_db(config: Config) -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(
        get_db_uri(config),
        uri=True,
    )
    try:
        yield conn
    finally:
        await conn.close()


async def get_book_title(book_id: int, config: Config) -> str:
    async with connect_db(config) as conn:
        async with conn.execute(
            "SELECT title FROM books WHERE id=?", (book_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Book not found")
            return row[0]


async def get_book_file_path(book_id: int, book_format: str, config: Config) -> Path:
    """Get the absolute path to the book file in the specified format."""
    book_format = book_format.upper().strip()
    async with connect_db(config) as conn:
        # Fetch the folder path for the book
        async with conn.execute(
            "SELECT path FROM books WHERE id=?", (book_id,)
        ) as cursor:
            book_row = await cursor.fetchone()

        if not book_row:
            raise HTTPException(
                status_code=404, detail=f"Book with id={book_id} not found"
            )
        folder = book_row[0]

        # Fetch the format and filename for the book
        async with conn.execute(
            "SELECT name FROM data WHERE book = ? AND format = ?",
            (book_id, book_format),
        ) as cursor:
            file_row = await cursor.fetchone()
        if not file_row:
            raise HTTPException(
                status_code=404,
                detail=f"Book file not found for book_id={book_id} with format={book_format}",
            )
    filename = file_row[0] + "." + book_format.lower()

    return Path(get_db_path(config).parent, folder, filename).resolve()


def generate_book_id(title: str) -> str:
    prefix = "calibre-navcatalog"
    title_bytes = title.strip().encode("utf-8")
    digest = hashlib.sha1(title_bytes).hexdigest()
    return f"{prefix}:{digest}"


async def get_cover_path(book_id: int, config: Config) -> Path:
    async with connect_db(config) as conn:
        async with conn.execute(
            "SELECT path FROM books WHERE id=?", (book_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")

    folder = row[0]
    cover = Path(get_db_path(config).parent, folder, "cover.jpg")
    if not cover.exists():
        raise HTTPException(status_code=404, detail="Cover not found")
    return cover


async def get_author_name(author_id: int, config: Config) -> str:
    async with connect_db(config) as conn:
        async with conn.execute(
            "SELECT name FROM authors WHERE id=?", (author_id,)
        ) as cursor:
            row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Author not found")
    return row[0]


async def add_authors(books: list, config: Config) -> dict[int, dict]:
    """Add authors to the books dictionary."""
    if not books:
        return {}

    book_ids = [book[0] for book in books]
    authors_by_book = defaultdict(list)
    placeholders = ",".join("?" * len(book_ids))

    async with connect_db(config) as conn:
        async with conn.execute(
            f"""
        SELECT bal.book AS book_id, a.id, a.name
        FROM books_authors_link bal
        JOIN authors a ON bal.author = a.id
        WHERE bal.book IN ({placeholders})
        """,
            book_ids,
        ) as cursor:
            async for book_id, author_id, name in cursor:
                authors_by_book[book_id].append({"id": author_id, "name": name})

    result = {}
    for book_id, title, last_modified in books:
        result[book_id] = {
            "title": title,
            "last_modified": datetime.fromisoformat(last_modified),
            "authors": authors_by_book[book_id],
        }

    return result


async def add_files(books: dict[int, dict], config: Config) -> dict[int, dict]:
    """Add files to the books dictionary."""
    if not books:
        return books

    book_ids = list(books.keys())
    files_by_book = defaultdict(list)
    placeholders = ",".join("?" * len(book_ids))
    async with connect_db(config) as conn:
        async with conn.execute(
            f"""
        SELECT book, format, name
        FROM data
        WHERE book IN ({placeholders})
        """,
            book_ids,
        ) as cursor:
            async for book_id, file_format, filename in cursor:
                files_by_book[book_id].append({"format": file_format, "name": filename})

    for book_id, book in books.items():
        book["files"] = files_by_book.get(book_id, [])

    return books


async def select_books(
    sql: str, page: int, config: Config, parameters: list | None = None
) -> tuple[dict[int, dict], bool, bool]:
    """Select books with pagination."""

    if page < 1:
        raise HTTPException(status_code=400, detail="Page number must be >= 1")

    sql_paged = f"{sql.rstrip()} LIMIT ? OFFSET ?"

    limit = config.page_size
    offset = (page - 1) * limit

    async with connect_db(config) as conn:
        async with conn.execute(
            sql_paged, list(parameters or []) + [limit + 1, offset]
        ) as cursor:
            books = await cursor.fetchall()

    has_next = len(books) > limit
    has_previous = offset > 0

    books_dict = await add_authors(books[:limit], config)
    await add_files(books_dict, config)

    return books_dict, has_previous, has_next


async def get_books(
    sort: str,
    page: int,
    config: Config,
) -> tuple[dict[int, dict], bool, bool]:
    if sort == "by_title":
        sort_field = "title"
    elif sort == "by_newest":
        sort_field = "last_modified"
    else:
        raise HTTPException(status_code=400, detail="Invalid sort parameter")

    sql = f"""
          SELECT id, title, last_modified
          FROM books
          ORDER BY {sort_field}
          """

    return await select_books(sql, page, config)


async def get_authors(page: int, config: Config) -> tuple[list, bool, bool]:
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be >= 1")

    sql = """
          SELECT id, name
          FROM authors
          ORDER BY sort
          """

    limit = config.page_size
    offset = (page - 1) * limit
    async with connect_db(config) as conn:
        async with conn.execute(
            f"{sql.rstrip()} LIMIT ? OFFSET ?", [limit + 1, offset]
        ) as cursor:
            authors = await cursor.fetchall()

    has_next = len(authors) > limit
    has_previous = offset > 0

    return authors[:limit], has_previous, has_next


async def get_author_books(
    author_id: int,
    page: int,
    config: Config,
) -> tuple[dict[int, dict], bool, bool]:
    sql = """
          SELECT b.id, b.title, b.last_modified
          FROM books b
                   JOIN books_authors_link bal ON b.id = bal.book
          WHERE bal.author = ?
          ORDER BY b.sort
          """

    return await select_books(sql, page, config, [author_id])


async def search_books(
    query: str,
    page: int,
    config: Config,
) -> tuple[dict[int, dict], bool, bool]:
    sql = """
          SELECT id, title, last_modified
          FROM books
          WHERE title LIKE ? COLLATE NOCASE
          ORDER BY sort
          """

    return await select_books(sql, page, config, [f"%{query}%"])
