import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.main import app as taskflow

app = FastAPI(lifespan=taskflow.router.lifespan_context)
app.mount("/api", taskflow)
app.mount("/", StaticFiles(directory=ROOT / "frontend" / "dist", html=True))