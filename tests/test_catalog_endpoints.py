"""Database-backed integration tests for the public OPDS and service
endpoints."""

from datetime import datetime
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

import pytest

ATOM = "http://www.w3.org/2005/Atom"
OPENSEARCH = "http://a9.com/-/spec/opensearch/1.1/"
NS = {"atom": ATOM, "os": OPENSEARCH}


def parse_atom(response) -> ElementTree.Element:
    """Assert the OPDS media type and parse a structurally valid Atom feed."""
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/atom+xml")
    root = ElementTree.fromstring(response.content)
    assert root.tag == f"{{{ATOM}}}feed"
    return root


def entries(feed: ElementTree.Element) -> list[ElementTree.Element]:
    """Return Atom entries from a parsed feed."""
    return feed.findall("atom:entry", NS)


def links(element: ElementTree.Element, rel: str) -> list[ElementTree.Element]:
    """Return direct Atom links having the requested relation."""
    return [link for link in element.findall("atom:link", NS) if link.get("rel") == rel]


def test_root_navigation_is_valid_atom(catalog_client):
    """Expose namespaced navigation entries with stable IDs and usable
    links."""
    _, client = catalog_client
    feed = parse_atom(client.get("/opds"))
    assert feed.findtext("atom:id", namespaces=NS) == "urn:opds-server:main"
    assert [entry.findtext("atom:title", namespaces=NS) for entry in entries(feed)] == [
        "By Newest",
        "By Title",
        "By Author",
    ]
    for entry in entries(feed):
        assert client.get(entry.find("atom:link", NS).get("href")).status_code == 200


@pytest.mark.parametrize("endpoint", ["/opds/by-title", "/opds/by-newest"])
def test_book_feeds_include_metadata_and_valid_acquisition_links(
    catalog_client, endpoint
):
    """Serialize escaped metadata, timestamps, covers, and downloadable
    formats."""
    _, client = catalog_client
    first = entries(parse_atom(client.get(endpoint)))[0]
    assert first.findtext("atom:id", namespaces=NS).startswith("calibre-navcatalog:")
    datetime.fromisoformat(
        first.findtext("atom:updated", namespaces=NS).replace("Z", "+00:00")
    )
    for link in first.findall("atom:link", NS):
        href = link.get("href")
        assert href.startswith("/opds/")
        if link.get("rel") == "http://opds-spec.org/acquisition":
            assert client.get(href).status_code == 200


def test_title_feed_paginates_at_boundaries(catalog_client):
    """Publish correct previous and next relations at each page boundary."""
    _, client = catalog_client
    first = parse_atom(client.get("/opds/by-title?page=1"))
    second = parse_atom(client.get("/opds/by-title?page=2"))
    beyond = parse_atom(client.get("/opds/by-title?page=3"))
    assert len(entries(first)) == 2
    assert not links(first, "previous") and links(first, "next")
    assert len(entries(second)) == 2
    assert links(second, "previous") and not links(second, "next")
    assert not entries(beyond)
    assert links(beyond, "previous") and not links(beyond, "next")


def test_author_navigation_detail_and_authorless_books(catalog_client):
    """Follow author links and keep authorless or multiply-authored books
    readable."""
    _, client = catalog_client
    author_feed = parse_atom(client.get("/opds/by-author"))
    detail_href = entries(author_feed)[0].find("atom:link", NS).get("href")
    detail = parse_atom(client.get(detail_href))
    assert detail.findtext("atom:title", namespaces=NS) == "Books by Ada & Sons"
    assert {
        entry.findtext("atom:title", namespaces=NS) for entry in entries(detail)
    } == {
        "A <Practical> Book",
        "Under_score",
    }
    second_page = parse_atom(client.get("/opds/by-title?page=2"))
    assert "Authorless" in {
        entry.findtext("atom:title", namespaces=NS) for entry in entries(second_page)
    }


@pytest.mark.parametrize(
    ("query", "page", "expected_title"),
    [
        ("Unicode книга", 1, "100% Unicode книга"),
        ("<Practical>", 1, "A <Practical> Book"),
        ("%", 1, "100% Unicode книга"),
        ("_", 2, "Under_score"),
    ],
)
def test_search_special_queries(catalog_client, query, page, expected_title):
    """Keep Unicode, XML-special, and SQL wildcard queries valid in XML and
    URLs."""
    _, client = catalog_client
    feed = parse_atom(client.get("/opds/search", params={"q": query, "page": page}))
    titles = {entry.findtext("atom:title", namespaces=NS) for entry in entries(feed)}
    assert expected_title in titles
    assert parse_qs(urlsplit(links(feed, "self")[0].get("href")).query)["q"] == [query]


def test_empty_catalog_returns_valid_empty_feeds(client_factory):
    """Return well-formed feeds without entries for a valid empty database."""
    _, client = client_factory(populated=False)
    for endpoint in ("/opds/by-title", "/opds/by-newest", "/opds/by-author"):
        assert not entries(parse_atom(client.get(endpoint)))


def test_download_and_cover_responses(catalog_client):
    """Serve known files with correct types and stable not-found responses."""
    _, client = catalog_client
    book = client.get("/opds/book/1/file/epub")
    cover = client.get("/opds/book/1/cover")
    assert (book.status_code, book.content, book.headers["content-type"]) == (
        200,
        b"epub contents",
        "application/epub+zip",
    )
    assert (cover.status_code, cover.content, cover.headers["content-type"]) == (
        200,
        b"jpeg contents",
        "image/jpeg",
    )
    assert client.get("/opds/book/3/file/epub").text == "Book file not found"
    assert client.get("/opds/book/2/cover").text == "Cover not found"
    assert client.get("/opds/book/999/file/epub").status_code == 404


def test_service_endpoints_and_root_redirect(catalog_client):
    """Expose liveness, readiness, and a root redirect to the configured
    catalog."""
    _, client = catalog_client
    assert client.get("/healthz").text == "ok"
    assert client.get("/ready").text == "ok"
    redirect = client.get("/", follow_redirects=False)
    assert (redirect.status_code, redirect.headers["location"]) == (307, "/opds")


def test_readiness_fails_safely_after_database_disappears(catalog_client):
    """Avoid exposing filesystem details when metadata.db vanishes at
    runtime."""
    library, client = catalog_client
    (library / "metadata.db").unlink()
    response = client.get("/ready")
    assert (response.status_code, response.text) == (500, "Calibre DB not found")
    assert str(library) not in response.text


def test_opensearch_document_is_namespaced(catalog_client):
    """Advertise search through a parseable, namespaced OpenSearch document."""
    _, client = catalog_client
    response = client.get("/opds/opensearch.xml")
    root = ElementTree.fromstring(response.content)
    assert response.status_code == 200
    assert root.tag == f"{{{OPENSEARCH}}}OpenSearchDescription"
    assert root.find("os:Url", NS).get("template") == "/opds/search?q={searchTerms}"


@pytest.mark.parametrize(
    ("path", "status", "message"),
    [
        ("/opds/by-title?page=0", 422, None),
        ("/opds/author/999", 404, "Author not found"),
        ("/opds/book/999/cover", 404, "Cover not found"),
    ],
)
def test_error_responses_are_stable(catalog_client, path, status, message):
    """Return deliberate client errors for invalid pages and missing
    resources."""
    _, client = catalog_client
    response = client.get(path)
    assert response.status_code == status
    if message:
        assert response.text == message
