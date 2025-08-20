import sqlite3
import os
import hashlib
from pathlib import Path
from fastapi import HTTPException
from datetime import datetime
from collections import defaultdict


def get_db_path() -> Path:
    path = os.getenv("CALIBRE_LIBRARY_PATH", "/books").rstrip("/") + "/metadata.db"
    return Path(path).resolve()


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


def get_book_file_path(book_id: int, format: str) -> Path:
    with connect_db() as conn:
        cursor = conn.cursor()

        # Fetch the folder path for the book
        cursor.execute("SELECT path FROM books WHERE id=?", (book_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Book not found")
        folder = row[0]

        # Fetch the format and filename for the book
        cursor.execute(
            "SELECT name FROM data WHERE book=? AND format=?", (book_id, format)
        )
        row2 = cursor.fetchone()
        if not row2:
            raise HTTPException(status_code=404, detail="Book file not found")
        (filename,) = row2

        filename = Path(filename + "." + format.lower())

        return Path(get_db_path().parent, folder, filename)


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


def add_authors(books: list) -> dict[int, dict]:
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
