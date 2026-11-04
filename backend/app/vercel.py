"""Vercel 배포용 진입점. 기존 앱을 /api 아래에 붙인다."""

from fastapi import FastAPI

from app.main import app as taskflow

app = FastAPI(lifespan=taskflow.router.lifespan_context)
app.mount("/api", taskflow)
