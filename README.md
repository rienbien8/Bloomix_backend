# Bloomix_backend

# OshiSpoNavi Backend (FastAPI + SQLModel) — v2

## Quickstart (Local)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

## フォルダ構成（Backend + DB、現時点のイメージ）

├─ app/
│ ├─ main.py # FastAPI エントリ。CORS/ルータ登録/health
│ ├─ db.py # SQLModel エンジン・Session・init_db()
│ ├─ models.py # テーブル定義（users/oshis/spots/contents/routes/...）
│ └─ routers/
│ ├─ spots.py # GET /api/v1/spots?near=lat,lng（±0.5°BBox）
│ ├─ oshis.py # GET /api/v1/oshis
│ ├─ routes.py # POST /routes, POST /routes/{id}/spots, GET /routes/{id}
│ └─ contents.py # GET /api/v1/contents?spot_id=（YouTube 優先）
├─ scripts/
│ └─ seed.sql # DB 作成・DDL・初期データ投入（MySQL Workbench/CLI で SOURCE）
├─ docs/
│ └─ folder-structure.txt # この構成図のプレーンテキスト版（任意）
├─ .github/
│ └─ workflows/
│ └─ azure-backend.yml # Azure App Service へのデプロイ用（GitHub Actions）
├─ .env.example # 環境変数の雛形（DATABASE_URL/GIT_SHA/ALLOWED_ORIGINS など）
├─ requirements.txt # Python 依存パッケージ
├─ README.md # セットアップ/実行手順
└─ .gitignore

### 補足(方針とか）

)

- **DB 初期化**は `scripts/seed.sql` を `SOURCE scripts/seed.sql;` で実行。
- **将来の拡張**：`migrations/`（Alembic）を追加してスキーマ変更を履歴管理予定。
