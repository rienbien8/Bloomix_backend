# app/routers/contents.py
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy import asc

from app.db import get_session
from app.models import Content, SpotContent, SpotsOshi, Oshi  # type: ignore

router = APIRouter(prefix="/api/v1/contents", tags=["contents"])

@router.get("")
def list_contents(
    # 絞り込み
    spot_id: Optional[int] = Query(None, description="このスポットに紐づくコンテンツ"),
    oshi_id: Optional[int] = Query(None, description="この推しに紐づくコンテンツ（spot_oshi経由）"),
    # 言語（カンマ区切り／単数どちらでも）
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
    コンテンツ横断検索。
    - spot_id 指定: そのスポットに紐づくもの
    - oshi_id 指定: spot_oshi を介して、該当推しに紐づくスポットのコンテンツ
    - 両方指定も可（積集合）
    - langs / lang で言語フィルタ、duration で長さの範囲
    """

    # 言語フィルタの正規化
    lang_list: Optional[List[str]] = None
    if langs:
        lang_list = [x.strip() for x in langs.split(",") if x.strip()]
    elif lang:
        lang_list = [lang.strip()]

    # ベース: Content
    # 条件によって SpotContent / SpotsOshi を段階的にJOIN
    stmt = select(Content, Oshi.name.label('oshi_name')).distinct()
    stmt = stmt.outerjoin(Oshi, Content.oshi_id == Oshi.id)

    sc_joined = False
    so_joined = False

    if spot_id is not None:
        stmt = stmt.join(SpotContent, SpotContent.content_id == Content.id)
        stmt = stmt.where(SpotContent.spot_id == spot_id)
        sc_joined = True

    if oshi_id is not None:
        if not sc_joined:
            # oshiのみ指定のときは SpotContent も必要
            stmt = stmt.join(SpotContent, SpotContent.content_id == Content.id)
            sc_joined = True
        # SpotsOshi を通じて推しに紐づくスポットに限定
        stmt = stmt.join(SpotsOshi, SpotsOshi.spot_id == SpotContent.spot_id)
        stmt = stmt.where(SpotsOshi.oshi_id == oshi_id)
        so_joined = True

    # 言語・時間の範囲
    if lang_list:
        stmt = stmt.where(Content.lang.in_(lang_list))
    if min_duration is not None:
        stmt = stmt.where(Content.duration_min >= min_duration)
    if max_duration is not None:
        stmt = stmt.where(Content.duration_min <= max_duration)

    # 並び（とりあえず短い順→id）
    #stmt = stmt.order_by(Content.duration_min.asc().nulls_last(), Content.id.asc()).limit(limit)
    stmt = stmt.order_by(
    (Content.duration_min.is_(None)).asc(),  # ← 先に「NULLかどうか」で並べる（False=0 → 非NULLが先行）
    Content.duration_min.asc(),              # 次に値の昇順
    Content.id.asc()                         # 最後に安定化
).limit(limit)
    
    rows = db.execute(stmt).all()

    items = [{
        "id": c.id,
        "title": c.title,
        "media_type": c.media_type,
        "media_url": getattr(c, "media_url", None),
        "youtube_id": getattr(c, "youtube_id", None),
        "lang": getattr(c, "lang", None),
        "thumbnail_url": getattr(c, "thumbnail_url", None),
        "duration_min": getattr(c, "duration_min", None),
        "oshi_name": oshi_name,  # 推しの名前を正しく取得
    } for c, oshi_name in rows]

    return {"count": len(items), "items": items}
