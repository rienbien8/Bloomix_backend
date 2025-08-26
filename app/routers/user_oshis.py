# app/routers/user_oshis.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_session
from app.models import UserOshi, Oshi  # type: ignore

router = APIRouter(prefix="/api/v1/users", tags=["user_oshis"])

@router.post("/{user_id}/oshis/{oshi_id}")
def follow_oshi(
    user_id: int,
    oshi_id: int,
    db: Session = Depends(get_session)
):
    """アーティストをフォローする"""
    try:
        # 既にフォローしているかチェック
        existing_follow = db.execute(
            select(UserOshi).where(
                UserOshi.user_id == user_id,
                UserOshi.oshi_id == oshi_id
            )
        ).scalar_one_or_none()
        
        if existing_follow:
            raise HTTPException(status_code=400, detail="Already following this oshi")
        
        # フォロー追加
        new_follow = UserOshi(
            user_id=user_id,
            oshi_id=oshi_id
        )
        db.add(new_follow)
        db.commit()
        
        return {"message": "Successfully followed oshi", "user_id": user_id, "oshi_id": oshi_id}
        
    except Exception as e:
        db.rollback()
        print(f"フォローエラーの詳細: {e}")
        print(f"エラータイプ: {type(e)}")
        import traceback
        print(f"スタックトレース: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to follow oshi: {str(e)}")

@router.delete("/{user_id}/oshis/{oshi_id}")
def unfollow_oshi(
    user_id: int,
    oshi_id: int,
    db: Session = Depends(get_session)
):
    """アーティストのフォローを解除する"""
    try:
        # フォロー状態をチェック
        existing_follow = db.execute(
            select(UserOshi).where(
                UserOshi.user_id == user_id,
                UserOshi.oshi_id == oshi_id
            )
        ).scalar_one_or_none()
        
        if not existing_follow:
            raise HTTPException(status_code=404, detail="Not following this oshi")
        
        # フォロー解除
        db.delete(existing_follow)
        db.commit()
        
        return {"message": "Successfully unfollowed oshi", "user_id": user_id, "oshi_id": oshi_id}
        
    except Exception as e:
        db.rollback()
        print(f"フォロー解除エラーの詳細: {e}")
        print(f"エラータイプ: {type(e)}")
        import traceback
        print(f"スタックトレース: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to unfollow oshi: {str(e)}")

@router.get("/{user_id}/oshis")
def get_user_oshis(
    user_id: int,
    db: Session = Depends(get_session)
):
    """ユーザーがフォローしているアーティスト一覧を取得"""
    try:
        follows = db.execute(
            select(UserOshi.oshi_id).where(UserOshi.user_id == user_id)
        ).scalars().all()
        
        return {"user_id": user_id, "following_oshi_ids": follows}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get user oshis: {str(e)}")
