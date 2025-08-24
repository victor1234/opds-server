from fastapi import FastAPI, HTTPException
from starlette.responses import PlainTextResponse

from opds_server.api import catalog
import logging


def create_app() -> FastAPI:
    app = FastAPI(title="OPDS Server")

    # Include API routers
    app.include_router(catalog.router, tags=["opds"])

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
