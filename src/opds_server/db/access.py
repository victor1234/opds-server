import sqlite3
import os
import hashlib
from pathlib import Path
from fastapi import HTTPException
from datetime import datetime
from collections import defaultdict


def get_db_path() -> Path:
    """Get absolute path to the Calibre metadata.db and ensure it exists."""
    base = os.getenv("CALIBRE_LIBRARY_PATH", "/books").rstrip("/")
    path = Path(base, "metadata.db").resolve()
    if not path.exists():
        raise HTTPException(status_code=500, detail=f"Calibre DB not found at {path}")
    return path


def get_db_uri() -> str:
    return f"file:{get_db_path()}?mode=ro"


def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(
        get_db_uri(),
        uri=True,
    )
    return conn


def get_book_title(book_id: int) -> str:
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM books WHERE id=?", (book_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Book not found")
        return row[0]


def get_book_file_path(book_id: int, book_format: str) -> Path:
    """Get the absolute path to the book file in the specified format."""
    book_format = book_format.upper().strip()
    with connect_db() as conn:
        cursor = conn.cursor()

        # Fetch the folder path for the book
        book_row = cursor.execute(
            "SELECT path FROM books WHERE id=?", (book_id,)
        ).fetchone()
        if not book_row:
            raise HTTPException(
                status_code=404, detail=f"Book with id={book_id} not found"
            )
        folder = book_row[0]

        # Fetch the format and filename for the book
        file_row = cursor.execute(
            "SELECT name FROM data WHERE book = ? AND format = ?",
            (book_id, book_format),
        ).fetchone()
        if not file_row:
            raise HTTPException(
                status_code=404,
                detail=f"Book file not found for book_id={book_id} with format={book_format}",
            )
        filename = file_row[0] + "." + book_format.lower()

        return Path(get_db_path().parent, folder, filename).resolve()


def generate_book_id(title: str) -> str:
    prefix = "calibre-navcatalog"
    title_bytes = title.strip().encode("utf-8")
    digest = hashlib.sha1(title_bytes).hexdigest()
    return f"{prefix}:{digest}"


def get_cover_path(book_id: int) -> Path:
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT path FROM books WHERE id=?", (book_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Book not found")

        folder = row[0]
        cover = Path(get_db_path().parent, folder, "cover.jpg")
        if not cover.exists():
            raise HTTPException(status_code=404, detail="Cover not found")
        return cover


def get_author_name(author_id: int) -> str:
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM authors WHERE id=?", (author_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Author not found")
        return row[0]


def add_authors(books: list) -> dict[int, dict]:
    """Add authors to the books dictionary."""
    if not books:
        return {}

    book_ids = [book[0] for book in books]
    with connect_db() as conn:
        cur = conn.cursor()

        authors_by_book = defaultdict(list)

        placeholders = ",".join("?" * len(book_ids))
        cur.execute(
            f"""
        SELECT bal.book AS book_id, a.id, a.name
        FROM books_authors_link bal
        JOIN authors a ON bal.author = a.id
        WHERE bal.book IN ({placeholders})
        """,
            book_ids,
        )

        for book_id, author_id, name in cur.fetchall():
            authors_by_book[book_id].append({"id": author_id, "name": name})

        result = {}
        for book_id, title, last_modified in books:
            result[book_id] = {
                "title": title,
                "last_modified": datetime.fromisoformat(last_modified),
                "authors": authors_by_book[book_id],
            }

        return result


def add_files(books: dict[int, dict]) -> dict[int, dict]:
    book_ids = list(books.keys())
    with connect_db() as conn:
        cur = conn.cursor()

        files_by_book = defaultdict(list)

        placeholders = ",".join("?" * len(book_ids))
        cur.execute(
            f"""
        SELECT book, format, name
        FROM data
        WHERE book IN ({placeholders})
        """,
            book_ids,
        )

        for book_id, file_format, filename in cur.fetchall():
            files_by_book[book_id].append({"format": file_format, "name": filename})

        for book_id, book in books.items():
            book["files"] = files_by_book.get(book_id, [])

    return books


def select_books(
    sql: str, page: int, limit: int = 10, parameters: list | None = None
) -> tuple[dict[int, dict], bool, bool]:
    with connect_db() as conn:
        cur = conn.cursor()

        offset = (page - 1) * limit
        sql += "LIMIT ? OFFSET ?"
        if parameters is None:
            parameters = []
        parameters += [limit + 1, offset]
        cur.execute(sql, parameters)
        books = cur.fetchall()

        has_next = len(books) > limit
        has_previous = offset > 0

        books_dict = add_authors(books[:limit])
        add_files(books_dict)

        return books_dict, has_previous, has_next


def get_books(
    sort: str, page: int, limit: int = 10
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

    return select_books(sql, page, limit)


def get_authors(page: int, limit: int = 10) -> tuple[list, bool, bool]:
    sql = """
          SELECT id, name
          FROM authors
          ORDER BY sort
          """

    with connect_db() as conn:
        cur = conn.cursor()
        offset = (page - 1) * limit
        sql += "LIMIT ? OFFSET ?"
        cur.execute(sql, [limit + 1, offset])
        authors = cur.fetchall()

        has_next = len(authors) > limit
        has_previous = offset > 0

        return authors, has_previous, has_next


def get_author_books(
    author_id: int, page: int, limit: int = 10
) -> tuple[dict[int, dict], bool, bool]:
    sql = """
          SELECT b.id, b.title, b.last_modified
          FROM books b
          JOIN books_authors_link bal ON b.id = bal.book
          WHERE bal.author = ?
          ORDER BY b.sort
          """

    return select_books(sql, page, limit, [author_id])


def search_books(
    query: str, page: int, limit: int = 10
) -> tuple[dict[int, dict], bool, bool]:
    sql = """
          SELECT id, title, last_modified
          FROM books
          WHERE LOWER(title) LIKE LOWER(?)
          ORDER BY sort
          """

    return select_books(sql, page, limit, ["%" + query + "%"])
