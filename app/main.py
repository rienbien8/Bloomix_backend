from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from os import getenv
from app.db import init_db
from app.routers import spots, oshis, routes, contents

app = FastAPI(title="OshiSpoNavi API", version="0.2.0")

origins = [o.strip() for o in getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup():
    init_db()

@app.get("/health") #稼働確認用エンドポイント
def health():
    return {"status": "ok", "version": getenv("GIT_SHA", "dev")}

app.include_router(spots.router, prefix="/api/v1")
app.include_router(oshis.router, prefix="/api/v1")
app.include_router(routes.router, prefix="/api/v1")
app.include_router(contents.router, prefix="/api/v1")
