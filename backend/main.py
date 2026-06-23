"""FastAPI entry point for Vercel serverless deployment."""

import sys
from pathlib import Path

# Ensure repo root is on PYTHONPATH so `backend.app.*` imports resolve
_REPO_ROOT = Path(__file__).parent.parent.resolve()
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fastapi import FastAPI
from backend.app.routers import receipts

app = FastAPI(title="Socrates API", version="0.1.0")
app.include_router(receipts.router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "socrates-api"}
