from __future__ import annotations

import logging

from fastapi import FastAPI

from app.api.routes import router
from app.data.database import initialize_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")

app = FastAPI(title="AI Market Intelligence Platform", version="0.1.0")
app.include_router(router, prefix="/api")


@app.on_event("startup")
def startup() -> None:
    initialize_database()
