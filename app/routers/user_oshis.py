# app/routers/user_oshis.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert, delete, and_
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User, Oshi, UserOshi  # type: ignore

router = APIRouter(prefix="/api/v1/users", tags=["user-oshis"])

# ユーザーのフォロー中の推し一覧
@router.get("/{user_id}/oshis")
def list_user_oshis(user_id: int, db: Session = Depends(get_session)):
    # ユーザー存在チェック（無くても空配列で返して良いが、分かりやすさ重視で404）
    u = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if not u:
        raise HTTPException(status_code=404, detail="user not found")

    stmt = (
        select(Oshi, UserOshi.registered_at)
        .join(UserOshi, UserOshi.oshi_id == Oshi.id)
        .where(UserOshi.user_id == user_id)
        .order_by(UserOshi.registered_at.desc())
    )
    rows = db.execute(stmt).all()
    items = [{
        "id": o.id,
        "name": o.name,
        "category": o.category,
        "image_url": getattr(o, "image_url", None),
        "description": getattr(o, "description", None),
        "registered_at": ru,
    } for (o, ru) in rows]
    return {"count": len(items), "items": items}

# フォロー追加（冪等：既存でも200）
@router.post("/{user_id}/oshis/{oshi_id}")
def follow_oshi(user_id: int, oshi_id: int, db: Session = Depends(get_session)):
    # user/oshi の存在を軽く検証（なければ404）
    if not db.execute(select(User.id).where(User.id == user_id)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="user not found")
    if not db.execute(select(Oshi.id).where(Oshi.id == oshi_id)).scalar_one_or_none():
        raise HTTPException(status_code=404, detail="oshi not found")

    # 既にフォロー済みならそのまま200で返す（冪等）
    exists_stmt = select(UserOshi).where(
        and_(UserOshi.user_id == user_id, UserOshi.oshi_id == oshi_id)
    )
    if db.execute(exists_stmt).scalar_one_or_none():
        return {"user_id": user_id, "oshi_id": oshi_id, "status": "exists"}

    # 新規追加
    db.execute(insert(UserOshi).values(user_id=user_id, oshi_id=oshi_id))
    db.commit()
    return {"user_id": user_id, "oshi_id": oshi_id, "status": "created"}

# フォロー解除（存在しなくても204を返す仕様にするのが一般的）
@router.delete("/{user_id}/oshis/{oshi_id}", status_code=204)
def unfollow_oshi(user_id: int, oshi_id: int, db: Session = Depends(get_session)):
    db.execute(
        delete(UserOshi).where(
            and_(UserOshi.user_id == user_id, UserOshi.oshi_id == oshi_id)
        )
    )
    db.commit()
    return None
