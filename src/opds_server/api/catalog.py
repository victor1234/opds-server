import re
import unicodedata

from fastapi import APIRouter, Response, Query
from opds_server.services.opds import (
    generate_root_feed,
    generate_newest_feed,
    generate_title_feed,
    generate_book_search_feed,
    generate_author_feed,
    get_book_mime_type,
)
from opds_server.db.access import get_book_file_path, get_cover_path, get_book_title
from fastapi.responses import FileResponse

router = APIRouter()


def title_to_filename(title: str, extension: str) -> str:
    title = unicodedata.normalize("NFKD", title)

    title = re.sub(r'[\\/*?:"<>|]', "_", title)

    title = re.sub(r"\s+", " ", title).strip(" .")

    if not title:
        title = "book"

    title = title[:100]  # можно подстроить по нужной длине

    return f"{title}.{extension}"


@router.get("/opds/book/{book_id}/file/{file_format}")
def download_book(book_id: int, file_format: str) -> FileResponse:
    path = get_book_file_path(book_id, file_format.upper())
    title = get_book_title(book_id)
    return FileResponse(
        path,
        media_type=get_book_mime_type(file_format.upper()),
        filename=title_to_filename(title, extension=file_format.lower()),
    )


@router.get("/opds/book/{book_id}/cover")
def get_cover(book_id: int) -> FileResponse:
    path = get_cover_path(book_id)
    return FileResponse(path, media_type="image/jpeg")


@router.get("/opds/opensearch.xml")
def get_opensearch() -> Response:
    osd = """<?xml version="1.0" encoding="UTF-8"?>
    <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
      <ShortName>OPDS Search</ShortName>
      <Description>Search books in the OPDS catalog</Description>
      <Url type="application/atom+xml;profile=opds-catalog;kind=acquisition"
           template="/opds/search?q={searchTerms}"/>
    </OpenSearchDescription>
    """
    return Response(
        content=osd, media_type="application/opensearchdescription+xml; charset=utf-8"
    )


@router.get("/opds/search")
def search(q: str, page: int = Query(1, ge=1)):
    xml = generate_book_search_feed("/opds/search", q, page)
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/opds", response_class=Response)
def root_main():
    xml = generate_root_feed("/opds")
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/opds/by-newest", response_class=Response)
def root_by_newest(page: int = Query(1, ge=1)):
    xml = generate_newest_feed("/opds/by-newest", page)
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/opds/by-title", response_class=Response)
def root_by_title(page: int = Query(1, ge=1)):
    xml = generate_title_feed("/opds/by-title", page)
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/opds/author/{author_id}")
def get_author_books(author_id: int, page: int = Query(1, ge=1)):
    xml = generate_author_feed(f"/opds/author/{author_id}", author_id, page)
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")
