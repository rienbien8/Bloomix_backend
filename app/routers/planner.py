from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, text
from typing import List, Optional
from pydantic import BaseModel
import math

from app.db import get_session
from app.models import Content, User, UserOshi, SpotContent, SpotsOshi

router = APIRouter(prefix="/api/v1/planner", tags=["planner"])

# =============================
# Pydantic Models
# =============================
class PlaylistRequest(BaseModel):
    target_duration_min: int
    user_id: int
    preferred_langs: List[str] = ["ja"]
    tolerance_min: int = 5
    content_types: List[str] = ["youtube"]
    max_items: int = 20

class PlaylistItem(BaseModel):
    content_id: int
    title: str
    duration_min: int
    lang: Optional[str]
    media_type: str
    thumbnail_url: Optional[str]
    total_duration_min: int
    remaining_min: int
    related_oshis: List[str] = []  # 関連する推し名のリスト

class PlaylistSummary(BaseModel):
    total_duration_min: int
    target_duration_min: int
    overage_min: int
    efficiency_score: float

class PlaylistResponse(BaseModel):
    playlist: List[PlaylistItem]
    summary: PlaylistSummary

# =============================
# Helper Functions
# =============================
def calculate_efficiency_score(actual_min: int, target_min: int, tolerance_min: int) -> float:
    """効率性スコアを計算（0.0〜1.0、高いほど良い）"""
    if actual_min <= target_min:
        # 目標時間内の場合：完璧
        return 1.0
    
    overage = actual_min - target_min
    if overage <= tolerance_min:
        # 許容誤差内：線形で減少
        return 1.0 - (overage / tolerance_min) * 0.2
    else:
        # 許容誤差超過：急激に減少
        penalty = (overage - tolerance_min) / target_min
        return max(0.0, 0.8 - penalty)

def get_user_oshi_weights(db: Session, user_id: int) -> dict:
    """ユーザーの推し関連コンテンツの重みを取得"""
    try:
        # ユーザーがフォローしている推しを取得
        user_oshis = db.query(UserOshi).filter(UserOshi.user_id == user_id).all()
        
        if not user_oshis:
            return {}
        
        # 推しIDのリスト
        oshi_ids = [uo.oshi_id for uo in user_oshis]
        
        # 各推しに関連するコンテンツの数を取得
        oshi_content_counts = {}
        for oshi_id in oshi_ids:
            count = db.query(SpotContent).join(SpotsOshi).filter(
                SpotsOshi.oshi_id == oshi_id
            ).count()
            oshi_content_counts[oshi_id] = count
        
        return oshi_content_counts
    except Exception as e:
        print(f"推し重み取得エラー: {e}")
        return {}

# =============================
# Greedy Algorithm for Playlist Generation
# =============================
def generate_playlist_greedy(
    db: Session,
    target_duration_min: int,
    user_id: int,
    preferred_langs: List[str],
    content_types: List[str],
    max_items: int,
    tolerance_min: int
) -> tuple[List[PlaylistItem], PlaylistSummary]:
    """
    貪欲法でプレイリストを生成
    
    アルゴリズム:
    1. 利用可能なコンテンツを時間順でソート
    2. 目標時間に最も近づくように、短いコンテンツから順次追加
    3. ユーザーの推し関連性でスコア調整
    4. 効率性を考慮して最適な組み合わせを選択
    """
    
    try:
        # 1. 利用可能なコンテンツを取得
        query = db.query(Content).filter(
            and_(
                Content.duration_min.isnot(None),
                Content.duration_min > 0,
                Content.media_type.in_(content_types),
                or_(
                    Content.lang.in_(preferred_langs),
                    Content.lang.is_(None)
                )
            )
        ).order_by(Content.duration_min.asc())
        
        available_contents = query.all()
        
        if not available_contents:
            raise HTTPException(status_code=404, detail="利用可能なコンテンツが見つかりません")
        
        # 2. ユーザーの推し関連重みを取得
        oshi_weights = get_user_oshi_weights(db, user_id)
        
        # 3. 貪欲法でプレイリストを構築
        playlist = []
        current_duration = 0
        remaining_duration = target_duration_min
        
        # 短いコンテンツから順次追加
        for content in available_contents:
            if len(playlist) >= max_items:
                break
                
            # 残り時間を超える場合はスキップ
            if content.duration_min > remaining_duration + tolerance_min:
                continue
            
            # 推し関連性でスコア調整
            oshi_score = 1.0
            if oshi_weights:
                # このコンテンツが推しに関連しているかチェック
                related_spots = db.query(SpotContent).filter(
                    SpotContent.content_id == content.id
                ).all()
                
                for spot_content in related_spots:
                    spot_oshis = db.query(SpotsOshi).filter(
                        SpotsOshi.spot_id == spot_content.spot_id
                    ).all()
                    
                    for spot_oshi in spot_oshis:
                        if spot_oshi.oshi_id in oshi_weights:
                            oshi_score += 0.5  # 推し関連でボーナス
            
            # 効率性を考慮したスコア計算
            potential_duration = current_duration + content.duration_min
            efficiency = calculate_efficiency_score(potential_duration, target_duration_min, tolerance_min)
            
            # 総合スコア（時間効率 + 推し関連性）
            total_score = efficiency * 0.7 + oshi_score * 0.3
            
            # スコアが閾値を超える場合のみ追加
            if total_score > 0.6:  # 最低スコア閾値
                # 関連する推し名を取得
                related_oshis = []
                try:
                    # 方法1: 直接contentテーブルからoshi_idを取得（実際のDB構造に合わせて）
                    # 注意: 現在のモデルにはoshi_idフィールドがないため、生SQLで確認
                    raw_result = db.execute(
                        text("SELECT oshi_id FROM contents WHERE id = :content_id AND oshi_id IS NOT NULL"),
                        {"content_id": content.id}
                    ).fetchone()
                    
                    if raw_result and raw_result[0]:
                        oshi = db.query(Oshi).filter(Oshi.id == raw_result[0]).first()
                        if oshi and oshi.name not in related_oshis:
                            related_oshis.append(oshi.name)
                    
                    # 方法2: 従来の方法（spot経由で推しを取得）
                    if not related_oshis:
                        related_spots = db.query(SpotContent).filter(
                            SpotContent.content_id == content.id
                        ).all()
                        
                        for spot_content in related_spots:
                            spot_oshis = db.query(SpotsOshi).filter(
                                SpotsOshi.spot_id == spot_content.spot_id
                            ).all()
                            
                            for spot_oshi in spot_oshis:
                                oshi = db.query(Oshi).filter(Oshi.id == spot_oshi.oshi_id).first()
                                if oshi and oshi.name not in related_oshis:
                                    related_oshis.append(oshi.name)
                    
                    print(f"DEBUG: Content {content.id} の推し情報: {related_oshis}")
                    
                except Exception as e:
                    print(f"推し名取得エラー: {e}")
                    # エラーが発生した場合のフォールバック
                    try:
                        # 生SQLで直接確認
                        result = db.execute(
                            text("SELECT oshi_id FROM contents WHERE id = :content_id"),
                            {"content_id": content.id}
                        ).fetchone()
                        if result:
                            print(f"DEBUG: 生SQL結果: {result}")
                    except Exception as fallback_error:
                        print(f"フォールバックエラー: {fallback_error}")
                
                playlist.append({
                    "content_id": content.id,
                    "title": content.title,
                    "duration_min": content.duration_min,
                    "lang": content.lang,
                    "media_type": content.media_type,
                    "thumbnail_url": content.thumbnail_url,
                    "total_duration_min": potential_duration,
                    "remaining_min": max(0, target_duration_min - potential_duration),
                    "related_oshis": related_oshis
                })
                
                current_duration = potential_duration
                remaining_duration = target_duration_min - current_duration
        
        # 4. 結果を時間順でソート
        playlist.sort(key=lambda x: x["total_duration_min"])
        
        # 5. サマリー情報を計算
        total_duration = current_duration
        overage = max(0, total_duration - target_duration_min)
        efficiency_score = calculate_efficiency_score(total_duration, target_duration_min, tolerance_min)
        
        summary = PlaylistSummary(
            total_duration_min=total_duration,
            target_duration_min=target_duration_min,
            overage_min=overage,
            efficiency_score=efficiency_score
        )
        
        return playlist, summary
        
    except Exception as e:
        print(f"プレイリスト生成エラー: {e}")
        raise HTTPException(status_code=500, detail=f"プレイリスト生成に失敗しました: {str(e)}")

# =============================
# API Endpoints
# =============================
@router.post("/playlist", response_model=PlaylistResponse)
async def generate_playlist(
    request: PlaylistRequest,
    db: Session = Depends(get_session)
):
    """
    プレイリスト提案エンドポイント
    
    貪欲法を使用して、指定された所要時間に最適なコンテンツの組み合わせを提案します。
    """
    
    # 入力値の検証
    if request.target_duration_min <= 0:
        raise HTTPException(status_code=400, detail="目標時間は正の値である必要があります")
    
    if request.max_items <= 0 or request.max_items > 100:
        raise HTTPException(status_code=400, detail="最大提案件数は1〜100の範囲で指定してください")
    
    if request.tolerance_min < 0:
        raise HTTPException(status_code=400, detail="許容誤差は0以上の値である必要があります")
    
    # ユーザーの存在確認
    user = db.query(User).filter(User.id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="指定されたユーザーが見つかりません")
    
    # プレイリスト生成
    try:
        playlist_items, summary = generate_playlist_greedy(
            db=db,
            target_duration_min=request.target_duration_min,
            user_id=request.user_id,
            preferred_langs=request.preferred_langs,
            content_types=request.content_types,
            max_items=request.max_items,
            tolerance_min=request.tolerance_min
        )
        
        # Pydanticモデルに変換
        playlist = [PlaylistItem(**item) for item in playlist_items]
        
        return PlaylistResponse(
            playlist=playlist,
            summary=summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"予期しないエラー: {e}")
        raise HTTPException(status_code=500, detail="プレイリスト生成中に予期しないエラーが発生しました")

@router.get("/contents", response_model=List[dict])
async def get_available_contents(
    user_id: int,
    preferred_langs: str = "ja",  # カンマ区切り
    content_types: str = "youtube",  # カンマ区切り
    db: Session = Depends(get_session)
):
    """
    利用可能なコンテンツ一覧を取得（デバッグ・開発用）
    """
    
    # パラメータをパース
    langs = [lang.strip() for lang in preferred_langs.split(",") if lang.strip()]
    types = [type_.strip() for type_ in content_types.split(",") if type_.strip()]
    
    try:
        query = db.query(Content).filter(
            and_(
                Content.duration_min.isnot(None),
                Content.duration_min > 0,
                Content.media_type.in_(types),
                or_(
                    Content.lang.in_(langs),
                    Content.lang.is_(None)
                )
            )
        ).order_by(Content.duration_min.asc())
        
        contents = query.limit(50).all()  # 最大50件
        
        return [
            {
                "id": c.id,
                "title": c.title,
                "duration_min": c.duration_min,
                "lang": c.lang,
                "media_type": c.media_type,
                "thumbnail_url": c.thumbnail_url
            }
            for c in contents
        ]
        
    except Exception as e:
        print(f"コンテンツ取得エラー: {e}")
        raise HTTPException(status_code=500, detail="コンテンツ取得に失敗しました")

@router.get("/health")
async def health_check():
    """プランナーサービスの健全性確認"""
    return {
        "status": "healthy",
        "service": "planner",
        "algorithm": "greedy",
        "features": ["playlist_generation", "content_optimization"]
    }

@router.get("/debug/contents/{content_id}")
async def debug_content_oshi(
    content_id: int,
    db: Session = Depends(get_session)
):
    """特定のコンテンツの推し情報をデバッグ表示"""
    try:
        # 方法1: 生SQLで直接確認
        raw_result = db.execute(
            text("SELECT * FROM contents WHERE id = :content_id"),
            {"content_id": content_id}
        ).fetchone()
        
        # 方法2: ORMで確認
        content = db.query(Content).filter(Content.id == content_id).first()
        
        # 方法3: spot経由で推しを確認
        related_spots = db.query(SpotContent).filter(
            SpotContent.content_id == content_id
        ).all()
        
        spot_oshis = []
        for spot_content in related_spots:
            spot_oshis_query = db.query(SpotsOshi).filter(
                SpotsOshi.spot_id == spot_content.spot_id
            ).all()
            for spot_oshi in spot_oshis_query:
                oshi = db.query(Oshi).filter(Oshi.id == spot_oshi.oshi_id).first()
                if oshi:
                    spot_oshis.append({
                        "spot_id": spot_content.spot_id,
                        "oshi_id": spot_oshi.oshi_id,
                        "oshi_name": oshi.name
                    })
        
        return {
            "content_id": content_id,
            "raw_sql_result": dict(raw_result) if raw_result else None,
            "orm_content": {
                "id": content.id,
                "title": content.title,
                "duration_min": content.duration_min
            } if content else None,
            "related_spots_count": len(related_spots),
            "spot_oshis": spot_oshis
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "content_id": content_id
        }
