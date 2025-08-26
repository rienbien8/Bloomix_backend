# app/routers/user_contents.py
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, Content, UserOshi, SpotsOshi, SpotContent, Oshi

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
    最適化されたクエリで効率的に取得
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

    # 方法1: Contentテーブルに直接oshi_idがある場合（最優先）
    try:
        print(f"DEBUG: 方法1を試行中 - ユーザーID: {user_id}")
        
        # ユーザーがフォローしている推しIDを取得
        user_oshi_ids = db.execute(
            select(UserOshi.oshi_id).where(UserOshi.user_id == user_id)
        ).scalars().all()
        
        print(f"DEBUG: フォロー推しID: {user_oshi_ids}")
        
        if not user_oshi_ids:
            print("DEBUG: フォロー推しなし")
            return {"count": 0, "items": []}
        
        # 直接Contentテーブルから取得（JOINなし！）
        stmt = (
            select(Content)
            .where(Content.oshi_id.in_(user_oshi_ids))
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
        
        print(f"DEBUG: 実行するSQL: {stmt}")
        
        contents = db.execute(stmt).scalars().all()
        
        print(f"DEBUG: 方法1で取得したコンテンツ数: {len(contents)}")
        
        if contents:
            # Oshi名を取得
            oshi_names = {}
            for c in contents:
                if c.oshi_id:
                    oshi = db.execute(select(Oshi).where(Oshi.id == c.oshi_id)).scalar_one_or_none()
                    if oshi:
                        oshi_names[c.id] = oshi.name
            
            items = [{
                "id": c.id,
                "title": c.title,
                "media_type": c.media_type,
                "media_url": getattr(c, "media_url", None),
                "youtube_id": getattr(c, "youtube_id", None),
                "lang": getattr(c, "lang", None),
                "thumbnail_url": getattr(c, "thumbnail_url", None),
                "duration_min": getattr(c, "duration_min", None),
                "oshi_name": oshi_names.get(c.id),
            } for c in contents]
            
            print(f"DEBUG: 方法1成功 - 返却件数: {len(items)}")
            return {"count": len(items), "items": items}
    
    except Exception as e:
        # 直接取得に失敗した場合は、従来の方法でフォールバック
        print(f"DEBUG: 方法1失敗、フォールバック: {e}")
        print(f"DEBUG: エラーの詳細: {type(e).__name__}: {str(e)}")
    
    # 方法2: 従来のJOIN方式（フォールバック）
    try:
        print(f"DEBUG: 方法2（JOIN方式）を試行中")
        
        # 最適化: 必要なフィールドのみを選択
        stmt = (
            select(
                Content.id,
                Content.title,
                Content.media_type,
                Content.media_url,
                Content.youtube_id,
                Content.lang,
                Content.thumbnail_url,
                Content.duration_min
            )
            .join(SpotContent, SpotContent.content_id == Content.id)
            .join(SpotsOshi, SpotsOshi.spot_id == SpotContent.spot_id)
            .join(UserOshi, UserOshi.oshi_id == SpotsOshi.oshi_id)
            .where(UserOshi.user_id == user_id)
            .distinct()
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
        
        print(f"DEBUG: 方法2で実行するSQL: {stmt}")
        
        contents = db.execute(stmt).all()
        
        print(f"DEBUG: 方法2で取得したコンテンツ数: {len(contents)}")

        # Oshi名を取得（JOIN方式の場合は、Content.oshi_idから取得）
        oshi_names = {}
        for c in contents:
            if hasattr(c, 'oshi_id') and c.oshi_id:
                oshi = db.execute(select(Oshi).where(Oshi.id == c.oshi_id)).scalar_one_or_none()
                if oshi:
                    oshi_names[c.id] = oshi.name

        items = [{
            "id": c.id,
            "title": c.title,
            "media_type": c.media_type,
            "media_url": c.media_url,
            "youtube_id": c.youtube_id,
            "lang": c.lang,
            "thumbnail_url": c.thumbnail_url,
            "duration_min": c.duration_min,
            "oshi_name": oshi_names.get(c.id),
        } for c in contents]

        print(f"DEBUG: 方法2成功 - 返却件数: {len(items)}")
        return {"count": len(items), "items": items}
        
    except Exception as e:
        print(f"DEBUG: 方法2も失敗: {e}")
        print(f"DEBUG: エラーの詳細: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="コンテンツ取得に失敗しました") 