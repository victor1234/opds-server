import logging
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, HTTPException, Request
from starlette.responses import PlainTextResponse, RedirectResponse

from opds_server.api import catalog
from opds_server.core.config import Config, get_config
from opds_server.db.access import connect_db

config = Config()


def _get_version(pkg: str) -> str:
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "0.0.0"


def create_app(config: Config | None = None) -> FastAPI:
    config = config or get_config()

    # Get application version
    package_version = _get_version(config.package_name)

    app = FastAPI(title=config.app_name, version=package_version)

    # FastAPI represents a root-mounted router with an empty prefix.
    router_prefix = "" if config.opds_prefix == "/" else config.opds_prefix
    app.include_router(catalog.router, prefix=router_prefix, tags=["opds"])

    if config.opds_prefix != "/":

        @app.get("/", include_in_schema=False)
        def root_redirect(request: Request):
            """Redirect root URL to the externally visible OPDS feed."""
            root_path = request.scope.get("root_path", "")
            return RedirectResponse(
                url=config.opds_path(root_path=root_path), status_code=307
            )

    @app.get("/healthz", tags=["_service"], include_in_schema=False)
    def healthz() -> PlainTextResponse:
        """Liveness probe endpoint."""
        return PlainTextResponse("ok")

    @app.get("/ready", tags=["_service"], include_in_schema=False)
    async def ready() -> PlainTextResponse:
        """Readiness probe endpoint."""
        async with connect_db(config) as conn:
            await conn.execute("SELECT 1")
        return PlainTextResponse("ok")

    # Set up logging
    log = logging.getLogger("uvicorn.error")

    @app.exception_handler(HTTPException)
    def http_exception_handler(_, exc: HTTPException):
        """Handle HTTP exceptions and log server errors."""
        if exc.status_code >= 500:
            log.exception(f"HTTP {exc.status_code}: {exc.detail}")
        return PlainTextResponse(exc.detail, status_code=exc.status_code)

    @app.exception_handler(Exception)
    def general_exception_handler(_, exc: Exception):
        """Handle unexpected exceptions and log them."""
        log.exception("Unexpected error", exc_info=exc)
        return PlainTextResponse("Internal Server Error", status_code=500)

    return app


app = create_app()
