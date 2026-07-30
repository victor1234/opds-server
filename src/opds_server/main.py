import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version

from fastapi import FastAPI, HTTPException
from starlette.responses import PlainTextResponse, RedirectResponse

from opds_server.api import catalog
from opds_server.core.config import Config, get_config
from opds_server.db.access import check_library_availability


def _get_version(pkg: str) -> str:
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "0.0.0"


def create_app(config: Config | None = None) -> FastAPI:
    """Create an application using one consistent configuration instance."""
    app_config = config or get_config()
    log = logging.getLogger("uvicorn.error")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """Check initial readiness without making library access liveness."""
        try:
            await check_library_availability(app_config)
        except HTTPException as exc:
            if exc.status_code != 503:
                raise
            log.warning("Starting with Calibre database unavailable")
        yield

    package_version = _get_version(app_config.package_name)
    app = FastAPI(
        title=app_config.app_name,
        version=package_version,
        lifespan=lifespan,
    )

    if config is not None:

        def get_supplied_config() -> Config:
            """Provide the configuration supplied to the application
            factory."""
            return app_config

        app.dependency_overrides[get_config] = get_supplied_config

    # FastAPI represents a root-mounted router with an empty prefix.
    router_prefix = "" if app_config.opds_prefix == "/" else app_config.opds_prefix
    app.include_router(catalog.router, prefix=router_prefix, tags=["opds"])

    if app_config.opds_prefix != "/":

        @app.get("/", include_in_schema=False)
        def root_redirect():
            """Redirect root URL to the configured OPDS feed."""
            return RedirectResponse(url=app_config.opds_prefix, status_code=307)

    @app.get("/healthz", tags=["_service"], include_in_schema=False)
    def healthz() -> PlainTextResponse:
        """Liveness probe endpoint."""
        return PlainTextResponse("ok")

    @app.get("/ready", tags=["_service"], include_in_schema=False)
    async def ready() -> PlainTextResponse:
        """Readiness probe endpoint."""
        await check_library_availability(app_config)
        return PlainTextResponse("ok")

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
