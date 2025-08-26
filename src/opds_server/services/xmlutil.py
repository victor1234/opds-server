from lxml import etree
from urllib.parse import urlencode, urlunparse

ATOM = "http://www.w3.org/2005/Atom"


def build_url(path: str, params: dict | None = None) -> str:
    """Build a URL with the given path and query parameters."""
    query = urlencode(params or {})
    return urlunparse(("", "", path, "", query, ""))


def link(rel: str, href: str, type_: str) -> str:
    """Create an Atom link element as a string."""
    el = etree.Element("link", rel=rel, href=href, type=type_)
    return etree.tostring(el, encoding="unicode")
