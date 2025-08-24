from fastapi import FastAPI
from opds_server.api import catalog


def create_app() -> FastAPI:
    app = FastAPI(title="OPDS Server")

    # Include API routers
    app.include_router(catalog.router, tags=["opds"])

    return app


app = create_app()
