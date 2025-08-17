from fastapi import FastAPI
from opds_server.api import catalog

app = FastAPI(title="OPDS Server")
app.include_router(catalog.router)
