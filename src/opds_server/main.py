from fastapi import FastAPI, HTTPException
from starlette.responses import PlainTextResponse, RedirectResponse

from opds_server.api import catalog
import logging
from importlib.metadata import version, PackageNotFoundError

from opds_server.db.access import connect_db
from opds_server.core.config import get_config, Config


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

    # Include API routers
    app.include_router(catalog.router, prefix=config.opds_prefix, tags=["opds"])

    # Service endpoints
    @app.get("/", include_in_schema=False)
    def root_redirect():
        """Redirect root URL to the OPDS feed."""
        return RedirectResponse(url=config.opds_prefix, status_code=307)

    @app.get("/healthz", tags=["_service"], include_in_schema=False)
    def healthz() -> PlainTextResponse:
        """Liveness probe endpoint."""
        return PlainTextResponse("ok")

    @app.get("/ready", tags=["_service"], include_in_schema=False)
    def ready() -> PlainTextResponse:
        """Readiness probe endpoint."""
        with connect_db() as conn:
            conn.execute("SELECT 1")
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
