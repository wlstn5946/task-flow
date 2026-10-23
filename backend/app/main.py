from fastapi import FastAPI

from app.routes import auth, tasks

app = FastAPI(title="task-flow")
app.include_router(auth.router)
app.include_router(tasks.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
