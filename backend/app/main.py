from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import init_db
from app.routes import tasks


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="task-flow", lifespan=lifespan)
app.include_router(tasks.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
