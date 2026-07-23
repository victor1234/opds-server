import re
import unicodedata

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import FileResponse

from opds_server.core.config import Config, get_config
from opds_server.db.access import get_book_file_path, get_book_title, get_cover_path
from opds_server.services.opds import (
    generate_author_feed,
    generate_book_search_feed,
    generate_by_author_feed,
    generate_newest_feed,
    generate_root_feed,
    generate_title_feed,
    get_book_mime_type,
)

router = APIRouter()


def external_config(request: Request, config: Config) -> Config:
    """Include an ASGI proxy root path in URLs advertised to clients."""
    root_path = request.scope.get("root_path", "")
    if not root_path:
        return config
    return config.model_copy(
        update={"opds_prefix": config.opds_path(root_path=root_path)}
    )


def title_to_filename(title: str, extension: str) -> str:
    title = unicodedata.normalize("NFKD", title)

    title = re.sub(r'[\\/*?:"<>|]', "_", title)

    title = re.sub(r"\s+", " ", title).strip(" .")

    if not title:
        title = "book"

    title = title[:100]  # можно подстроить по нужной длине

    return f"{title}.{extension}"


@router.get("/book/{book_id}/file/{file_format}")
async def download_book(
    book_id: int, file_format: str, config: Config = Depends(get_config)
) -> FileResponse:
    path = await get_book_file_path(book_id, file_format, config)
    title = await get_book_title(book_id, config)
    return FileResponse(
        path,
        media_type=get_book_mime_type(file_format.upper()),
        filename=title_to_filename(title, extension=file_format.lower()),
    )


@router.get("/book/{book_id}/cover")
async def get_cover(book_id: int, config: Config = Depends(get_config)) -> FileResponse:
    path = await get_cover_path(book_id, config)
    return FileResponse(path, media_type="image/jpeg")


@router.get("/opensearch.xml")
def get_opensearch(request: Request, config: Config = Depends(get_config)) -> Response:
    """Return an OpenSearch document using the configured catalog path."""
    config = external_config(request, config)
    search_template = config.opds_path("search")
    osd = f"""<?xml version="1.0" encoding="UTF-8"?>
    <OpenSearchDescription xmlns="http://a9.com/-/spec/opensearch/1.1/">
      <ShortName>OPDS Search</ShortName>
      <Description>Search books in the OPDS catalog</Description>
      <Url type="application/atom+xml;profile=opds-catalog;kind=acquisition"
           template="{search_template}?q={{searchTerms}}"/>
    </OpenSearchDescription>
    """
    return Response(
        content=osd, media_type="application/opensearchdescription+xml; charset=utf-8"
    )


@router.get("/search")
async def search(
    request: Request,
    q: str,
    page: int = Query(1, ge=1),
    config: Config = Depends(get_config),
) -> Response:
    xml = await generate_book_search_feed(q, page, external_config(request, config))
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/", response_class=Response)
def root_main(request: Request, config: Config = Depends(get_config)):
    xml = generate_root_feed(external_config(request, config))
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/by-newest", response_class=Response)
async def root_by_newest(
    request: Request,
    page: int = Query(1, ge=1),
    config: Config = Depends(get_config),
):
    xml = await generate_newest_feed(page, external_config(request, config))
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/by-title", response_class=Response)
async def root_by_title(
    request: Request,
    page: int = Query(1, ge=1),
    config: Config = Depends(get_config),
):
    xml = await generate_title_feed(page, external_config(request, config))
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/by-author")
async def root_by_author(
    request: Request,
    page: int = Query(1, ge=1),
    config: Config = Depends(get_config),
):
    xml = await generate_by_author_feed(page, external_config(request, config))
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")


@router.get("/author/{author_id}")
async def get_author_books(
    request: Request,
    author_id: int,
    page: int = Query(1, ge=1),
    config: Config = Depends(get_config),
):
    xml = await generate_author_feed(author_id, page, external_config(request, config))
    return Response(content=xml, media_type="application/atom+xml; charset=utf-8")
