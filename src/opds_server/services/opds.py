from opds_server.core.config import Config
from opds_server.db.access import (
    get_books,
    search_books,
    get_authors,
    get_author_books,
    get_author_name,
)
from datetime import datetime, timezone

from opds_server.db.access import generate_book_id
from dataclasses import dataclass, field
from urllib.parse import urlencode
import html
from opds_server.services.xmlutil import build_url, link


@dataclass
class Item:
    title: str
    id: str
    updated_time: datetime
    links: str
    db_id: int = -1
    author: dict = field(default_factory=dict)
    files: list[dict] = field(default_factory=list)
    summary: str = ""


@dataclass
class Feed:
    title: str
    id: str
    updated_time: datetime
    endpoint: str
    links: str = ""
    items: list[Item] = field(default_factory=list)
    kind: str = "acquisition"
    page: int = 1
    previous: bool = False
    next: bool = False
    parameters: dict = field(default_factory=dict)


MIME_BY_EXT = {
    "epub": "application/epub+zip",
    "pdf": "application/pdf",
    "mobi": "application/x-mobipocket-ebook",
    "fb2": "application/x-fictionbook+xml",
    "djvu": "image/vnd.djvu",
    "azw3": "application/vnd.amazon.ebook",
    "azw": "application/vnd.amazon.ebook",
    "cbz": "application/x-cbz",
    "cbr": "application/x-cbr",
    "txt": "text/plain; charset=utf-8",
    "rtf": "application/rtf",
}


def xml_text(s: str | int) -> str:
    """Escape text for safe placement into XML text nodes/attributes."""
    return html.escape(str(s), quote=True)


def fmt_dt(dt: datetime) -> str:
    """Format datetime as Atom-compliant UTC timestamp."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_book_mime_type(extension: str) -> str:
    """Returns the MIME type for a given file extension.

    If the extension is not recognized, returns 'application/octet-
    stream'.
    """
    return MIME_BY_EXT.get(extension.lower(), "application/octet-stream")


def q(params: dict) -> str:
    """Build escaped query tail like '&amp;a=1&amp;b=2' or '' if no params."""
    if not params:
        return ""
    return "&amp;" + urlencode(params, doseq=True)


def nav_link(rel: str, endpoint: str, page: int, params: dict, kind: str) -> str:
    """Uniform OPDS navigation link with profile type."""
    href_link = build_url(endpoint, {"page": page, **(params or {})})
    type_ = f"application/atom+xml;profile=opds-catalog;kind={kind}"
    return link(rel, href_link, type_)


def get_search_link() -> str:
    return '        <link type="application/opensearchdescription+xml" rel="search" title="Search" href="/opds/opensearch.xml"/>'


def get_start_link() -> str:
    return link(
        "start", "/opds", "application/atom+xml;profile=opds-catalog;kind=navigation"
    )


def get_author_xml(author: dict) -> str:
    if author:
        name = xml_text(author["name"])
        aid = xml_text(author.get("id", ""))
        parts = [
            "<author>",
            f"{16 * ' '}<name>{name}</name>",
        ]
        if aid:
            parts.append(f"{16 * ' '}<uri>/opds/author/{aid}</uri>")
        parts.append(f"{12 * ' '}</author>")

        return "\n".join(parts)
    else:
        return ""


def get_files_xml(book_id: int, files: list[dict]) -> str:
    files_xml = []
    for file in files:
        file_format = file["format"].lower()
        files_xml.append(
            link(
                "http://opds-spec.org/acquisition",
                f"/opds/book/{book_id}/file/{file_format}",
                get_book_mime_type(file_format),
            )
        )
    return "\n".join(files_xml)


def create_feed_links(feed: Feed) -> str:
    parts = [
        feed.links,
        get_start_link(),
        get_search_link(),
        nav_link("self", feed.endpoint, feed.page, feed.parameters, feed.kind),
        nav_link("first", feed.endpoint, 1, feed.parameters, feed.kind),
    ]
    if feed.previous:
        parts.append(
            nav_link(
                "previous", feed.endpoint, feed.page - 1, feed.parameters, feed.kind
            )
        )
    if feed.next:
        parts.append(
            nav_link("next", feed.endpoint, feed.page + 1, feed.parameters, feed.kind)
        )

    return "\n".join(parts)


def generate_feed(feed: Feed) -> str:
    entries = ""
    for item in feed.items:
        entries += f"""
        <entry>
            <title>{xml_text(item.title)}</title>
            <id>{xml_text(item.id)}</id>
            {get_author_xml(item.author)}
            <updated>{fmt_dt(item.updated_time)}</updated>
            {get_files_xml(item.db_id, item.files)}
            {item.links}
            <summary type="text">{xml_text(item.summary)}</summary>
        </entry>
    """

    feed_xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>{xml_text(feed.title)}</title>
        <id>{xml_text(feed.id)}</id>
        <updated>{fmt_dt(feed.updated_time)}</updated>
        <author>
            <name>Calibre OPDS Server</name>
        </author>
        {create_feed_links(feed)}
        {entries}
    </feed>"""

    return feed_xml


def generate_root_feed(endpoint: str) -> str:
    feed = Feed(
        title="Calibre OPDS Catalog",
        id="urn:opds-server:main",
        updated_time=datetime.now(timezone.utc),
        endpoint=endpoint,
        kind="navigation",
    )

    items = [
        Item(
            title="By Newest",
            id="urn:opds-server:by-newest:",
            updated_time=feed.updated_time,
            links=link(
                "http://opds-spec.org/sort/new",
                "/opds/by-newest",
                "application/atom+xml;profile=opds-catalog;kind=acquisition",
            ),
            summary="Books sorted by date",
        ),
        Item(
            title="By Title",
            id="urn:opds-server:by-title:",
            updated_time=feed.updated_time,
            links=link(
                "subsection",
                "/opds/by-title",
                "application/atom+xml;profile=opds-catalog;kind=acquisition",
            ),
            summary="Books sorted by title",
        ),
        Item(
            title="By Author",
            id="urn:opds-server:by-author:",
            updated_time=feed.updated_time,
            links=link(
                "subsection",
                "/opds/by-author",
                "application/atom+xml;profile=opds-catalog;kind=navigation",
            ),
            summary="Books sorted by author",
        ),
    ]

    feed.items = items

    return generate_feed(feed)


async def generate_newest_feed(endpoint: str, page: int, config: Config) -> str:
    books, has_previous, has_next = await get_books(
        sort="by_newest", page=page, config=config
    )

    items = items_from_books(books)

    feed = Feed(
        title="Calibre OPDS Catalog",
        id="urn:opds-server:by-newest",
        updated_time=datetime.now(timezone.utc),
        items=items,
        endpoint=endpoint,
        kind="acquisition",
        page=page,
        next=has_next,
        previous=has_previous,
    )

    return generate_feed(feed)


async def generate_title_feed(endpoint: str, page: int, config: Config) -> str:
    books, has_previous, has_next = await get_books(
        sort="by_title", page=page, config=config
    )

    items = items_from_books(books)

    feed = Feed(
        title="Calibre OPDS Catalog",
        id="urn:opds-server:by-title",
        updated_time=datetime.now(timezone.utc),
        items=items,
        endpoint=endpoint,
        kind="acquisition",
        page=page,
        next=has_next,
        previous=has_previous,
    )

    return generate_feed(feed)


async def generate_by_author_feed(endpoint: str, page, config: Config) -> str:
    """Generate an OPDS feed listing authors."""
    authors, has_previous, has_next = await get_authors(page, config)

    updated_time = datetime.now(timezone.utc)

    items: list[Item] = []
    for author_id, author_name in authors:
        items.append(
            Item(
                title=author_name,
                id=f"urn:opds-server:author:{author_id}",
                author={"name": "Calibre OPDS Server"},
                updated_time=updated_time,
                links=(
                    f'<link type="application/atom+xml;profile=opds-catalog;kind=acquisition" '
                    f'href="/opds/author/{author_id}"/>'
                ),
            )
        )

    feed_obj = Feed(
        title="By Authors",
        id="urn:opds-server:by-author",
        updated_time=updated_time,
        items=items,
        endpoint=endpoint,
        kind="navigation",
        page=page,
        previous=has_previous,
        next=has_next,
    )

    return generate_feed(feed_obj)


async def generate_author_feed(
    endpoint: str, author_id: int, page: int, config: Config
) -> str:
    books, has_previous, has_next = await get_author_books(
        author_id, page=page, config=config
    )

    items = items_from_books(books)

    author_name = await get_author_name(author_id, config)

    feed = Feed(
        title=f"Books by {author_name}",
        id=f"urn:opds-server:author:{author_id}",
        updated_time=datetime.now(timezone.utc),
        items=items,
        endpoint=endpoint,
        kind="acquisition",
        page=page,
        next=has_next,
        previous=has_previous,
    )
    return generate_feed(feed)


def items_from_books(books: dict[int, dict]) -> list[Item]:
    items = []
    for book_id, book in books.items():
        items.append(
            Item(
                title=book["title"],
                id=generate_book_id(str(book_id)),
                db_id=book_id,
                updated_time=book["last_modified"],
                author=book["authors"][0],
                files=book["files"],
                links=link(
                    "http://opds-spec.org/image",
                    f"/opds/book/{book_id}/cover",
                    type_="image/jpeg",
                ),
            )
        )
    return items


async def generate_book_search_feed(
    endpoint: str, query: str, page: int, config: Config
) -> str:
    books, has_previous, has_next = await search_books(
        query,
        page,
        config=config,
    )
    items = items_from_books(books)
    feed = Feed(
        title=f"Search results for '{query}'",
        id=f"urn:opds-server:search:{query}",
        updated_time=datetime.now(timezone.utc),
        items=items,
        endpoint=endpoint,
        kind="acquisition",
        page=page,
        next=has_next,
        previous=has_previous,
        parameters={"q": query},
    )
    return generate_feed(feed)
