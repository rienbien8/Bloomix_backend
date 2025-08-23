# app/routers/user_contents.py
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, Content, UserOshi, SpotsOshi, SpotContent

router = APIRouter(prefix="/api/v1/users", tags=["user-contents"])

@router.get("/{user_id}/contents")
def list_user_contents(
    user_id: int,
    # 言語フィルタ
    langs: Optional[str] = Query(None, description="例: ja,en"),
    lang: Optional[str] = Query(None, description="後方互換の単数指定"),
    # 再生時間（分）
    min_duration: Optional[int] = Query(None, ge=0),
    max_duration: Optional[int] = Query(None, ge=0),
    # 返却件数
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    """
    ユーザーがフォローしている推しに関連するコンテンツを取得
    User → UserOshi → Oshi → SpotsOshi → Spot → SpotContent → Content
    の流れでコンテンツを取得
    """
    
    # ユーザー存在チェック
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    # 言語フィルタの正規化
    lang_list: Optional[List[str]] = None
    if langs:
        lang_list = [x.strip() for x in langs.split(",") if x.strip()]
    elif lang:
        lang_list = [lang.strip()]

    # ユーザーの推しに関連するコンテンツを取得
    stmt = (
        select(distinct(Content))
        .join(SpotContent, SpotContent.content_id == Content.id)
        .join(SpotsOshi, SpotsOshi.spot_id == SpotContent.spot_id)
        .join(UserOshi, UserOshi.oshi_id == SpotsOshi.oshi_id)
        .where(UserOshi.user_id == user_id)
    )

    # 言語・時間の範囲フィルタ
    if lang_list:
        stmt = stmt.where(Content.lang.in_(lang_list))
    if min_duration is not None:
        stmt = stmt.where(Content.duration_min >= min_duration)
    if max_duration is not None:
        stmt = stmt.where(Content.duration_min <= max_duration)

    # 並び順（短い順→id）
    stmt = stmt.order_by(
        (Content.duration_min.is_(None)).asc(),
        Content.duration_min.asc(),
        Content.id.asc()
    ).limit(limit)
    
    rows = db.execute(stmt).scalars().all()

    items = [{
        "id": c.id,
        "title": c.title,
        "media_type": c.media_type,
        "media_url": getattr(c, "media_url", None),
        "youtube_id": getattr(c, "youtube_id", None),
        "lang": getattr(c, "lang", None),
        "thumbnail_url": getattr(c, "thumbnail_url", None),
        "duration_min": getattr(c, "duration_min", None),
    } for c in rows]

    return {"count": len(items), "items": items} 