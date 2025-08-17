from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from os import getenv
from app.db import init_db, test_connection  # DB接続機能を有効化
# from app.routers import spots #, oshis, routes, contents  # 後で実装
import app.routers.spots as spots_router
import app.routers.oshis as oshis_router
import app.routers.user_oshis as user_oshis_router
import app.routers.contents as contents_router
import app.routers.bff_maps as bff_maps_router



app = FastAPI(title="OshiSpoNavi API", version="0.2.0")

origins = [o.strip() for o in getenv("ALLOWED_ORIGINS", "*").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def _startup():
    init_db()  # DB初期化を有効化（エラーでもアプリは起動継続）

@app.get("/health")
def health():
    """アプリケーション稼働確認用エンドポイント"""
    return {"status": "ok", "version": getenv("GIT_SHA", "dev")}

@app.get("/health/db")
def health_db():
    """データベース接続確認用エンドポイント"""
    if test_connection():
        return {"status": "ok", "database": "connected", "message": "Azure MySQLに正常に接続しました"}
    else:
        return {
            "status": "error", 
            "database": "disconnected",
            "message": "MySQLサーバーに接続できません。サーバーが起動しているか確認してください。",
            "troubleshooting": [
                "1. MySQLサーバーが起動しているか確認",
                "2. 環境変数(.env)が正しく設定されているか確認", 
                "3. ネットワーク接続を確認",
                "4. Azure MySQLのファイアウォール設定を確認"
            ]
        }

# 追加↓↓
app.include_router(spots_router.router)
app.include_router(oshis_router.router)
app.include_router(user_oshis_router.router)
app.include_router(contents_router.router)
app.include_router(bff_maps_router.router)


# app.include_router(spots.router, prefix="/api/v1")  # 後で実装
# app.include_router(oshis.router, prefix="/api/v1")  # 後で実装
# app.include_router(routes.router, prefix="/api/v1")  # 後で実装
# app.include_router(contents.router, prefix="/api/v1")  # 後で実装
