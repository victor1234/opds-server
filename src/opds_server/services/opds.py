from opds_server.db.access import get_recent_books, search_books
from datetime import datetime, timezone

from opds_server.db.access import generate_book_id
from dataclasses import dataclass, field
from urllib.parse import urlencode


@dataclass
class Item:
    title: str
    id: str
    updated_time: datetime
    links: str
    author: dict = field(default_factory=dict)
    summary: str = ""


@dataclass
class Feed:
    title: str
    id: str
    updated_time: datetime
    endpoint: str
    links: str = ""
    items: list[Item] = field(default_factory=list)
    page: int = 1
    previous: bool = False
    next: bool = False
    parameters: dict = field(default_factory=dict)


def get_search_link() -> str:
    return '<link type="application/opensearchdescription+xml" rel="search" title="Search" href="/opds/opensearch.xml"/>'


def get_start_link() -> str:
    return '<link rel="start" href="/opds" type="application/atom+xml;profile=opds-catalog;kind=navigation"/>'


def get_author_xml(author: dict) -> str:
    if author:
        return f"""
        <author>
            <name>{author["name"]}</name>
        </author>
        """
    else:
        return ""


def create_feed_links(feed: Feed) -> str:
    links = f"""
        {feed.links}
        {get_start_link()}
        {get_search_link()}
    """
    query = "&amp;" + urlencode(feed.parameters) if feed.parameters else ""

    links += f"""
        <link rel="self" href="{feed.endpoint}?page={feed.page}{query}"
            type="application/atom+xml;profile=opds-catalog"/>"""
    links += f"""
        <link rel="first" href="{feed.endpoint}?page=1{query}"
            type="application/atom+xml;profile=opds-catalog"/>"""
    if feed.previous:
        links += f"""
        <link rel="previous" href="{feed.endpoint}?page={feed.page - 1}{query}"
            type="application/atom+xml;profile=opds-catalog"/>"""
    if feed.next:
        links += f"""
        <link rel="next" href="{feed.endpoint}?page={feed.page + 1}{query}"
            type="application/atom+xml;profile=opds-catalog"/>
        """

    return links


def generate_feed(feed: Feed) -> str:
    entries = ""
    for item in feed.items:
        entries += f"""
        <entry>
            <title>{item.title}</title>
            <id>{item.id}</id>
            {get_author_xml(item.author)}
            <updated>{item.updated_time.strftime("%Y-%m-%dT%H:%M:%SZ")}</updated>
            {item.links}
        </entry>
    """

    feed = f"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
        <title>{feed.title}</title>
        <id>{feed.id}</id>
        <updated>{feed.updated_time.strftime("%Y-%m-%dT%H:%M:%SZ")}</updated>
        <author>
            <name>Calibre OPDS Server</name>
        </author>
        {create_feed_links(feed)}
        {entries}
    </feed>"""

    return feed


def generate_root_feed(endpoint: str) -> str:
    feed = Feed(
        title="Calibre OPDS Catalog",
        id="urn:opds-server:main",
        updated_time=datetime.now(timezone.utc),
        endpoint=endpoint,
    )

    items = [
        Item(
            title="By Title",
            id="urn:opds-server:by-title:",
            updated_time=feed.updated_time,
            links='<link rel="http://opds-spec.org/sort" href="/opds/by-title" type="application/atom+xml;type=feed;profile=opds-catalog"/>',
            summary="Browse books by title",
        )
    ]

    feed.items = items

    return generate_feed(feed)


def generate_title_feed(endpoint: str, page: int) -> str:
    books, has_previous, has_next = get_recent_books(page=page)

    items = items_from_books(books)

    feed = Feed(
        title="Calibre OPDS Catalog",
        id="urn:opds-server:by-title",
        updated_time=datetime.now(timezone.utc),
        items=items,
        endpoint=endpoint,
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
                updated_time=book["last_modified"],
                author=book["authors"][0],
                links=f"""
            <link type="application/pdf" href="/opds/book/{book_id}/file" rel="http://opds-spec.org/acquisition"/>
            <link type="image/jpeg" href="/opds/book/{book_id}/cover" rel="http://opds-spec.org/image"/>
            """,
            )
        )
    return items


def generate_book_search_feed(
    endpoint: str, query: str, page: int = 1, limit: int = 10
) -> str:
    books, has_previous, has_next = search_books(query, page, limit)
    items = items_from_books(books)
    feed = Feed(
        title=f"Search results for '{query}'",
        id=f"urn:opds-server:search:{query}",
        updated_time=datetime.now(timezone.utc),
        items=items,
        endpoint=endpoint,
        page=page,
        next=has_next,
        previous=has_previous,
        parameters={"q": query},
    )
    return generate_feed(feed)
