from sqlalchemy import (
    Column, BigInteger, Integer, SmallInteger, String, Text, Boolean, DateTime,
    ForeignKey, Index, DECIMAL, func, PrimaryKeyConstraint
)
from sqlalchemy.orm import relationship
from app.base import Base  # declarative_base() を定義済み

# 既存テーブルを“使うだけ”。create_all は呼ばない想定です。

# ----------------------------
# USERS
# ----------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    oshis = relationship("Oshi", secondary="user_oshi", back_populates="users", lazy="noload")

    __table_args__ = (
        Index("ix_users_username", "username"),
    )

# ----------------------------
# OSHIS
# ----------------------------
class Oshi(Base):
    __tablename__ = "oshis"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False, unique=True)
    category = Column(String(50), nullable=False)    # 'artist','team','comedian',...
    description = Column(Text, nullable=True)
    image_url = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    users = relationship("User", secondary="user_oshi", back_populates="oshis", lazy="noload")
    spots = relationship("Spot", secondary="spot_oshi", back_populates="oshis", lazy="noload")
    contents = relationship("Content", back_populates="oshi", lazy="noload")

    __table_args__ = (
        Index("ix_oshis_name", "name"),
        Index("ix_oshis_category", "category"),
    )

# ----------------------------
# SPOTS
# ----------------------------
class Spot(Base):
    __tablename__ = "spots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    lat = Column(DECIMAL(10, 7), nullable=False)
    lng = Column(DECIMAL(10, 7), nullable=False)
    type = Column(String(50), nullable=True)
    is_special = Column(Boolean, nullable=False, default=False)
    dwell_min = Column(Integer, nullable=True)   # 滞在目安
    address = Column(String(255), nullable=True)
    place_id = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    contents = relationship("Content", secondary="spot_content", back_populates="spots", lazy="noload")
    oshis = relationship("Oshi", secondary="spot_oshi", back_populates="spots", lazy="noload")

    __table_args__ = (
        Index("ix_spots_lat_lng", "lat", "lng"),
        Index("ix_spots_is_special", "is_special"),
        Index("ix_spots_name", "name"),
    )

# ----------------------------
# CONTENTS
# ----------------------------
class Content(Base):
    __tablename__ = "contents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    media_type = Column(String(50), nullable=False)      # 'youtube' など
    media_url = Column(String(512), nullable=True)
    youtube_id = Column(String(32), nullable=True)
    lang = Column(String(8), nullable=True)              # 'ja','en' など
    thumbnail_url = Column(String(512), nullable=True)
    duration_min = Column(SmallInteger, nullable=True)
    oshi_id = Column(BigInteger, ForeignKey("oshis.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    spots = relationship("Spot", secondary="spot_content", back_populates="contents", lazy="noload")
    oshi = relationship("Oshi", back_populates="contents", lazy="noload")

    __table_args__ = (
        Index("ix_contents_lang_duration", "lang", "duration_min"),
        Index("ix_contents_title", "title"),
        Index("ix_contents_oshi", "oshi_id"),
    )

# ----------------------------
# 中間: spot_content（Spot × Content）
# ----------------------------
class SpotContent(Base):
    __tablename__ = "spot_content"

    spot_id = Column(BigInteger, ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(BigInteger, ForeignKey("contents.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("spot_id", "content_id", name="pk_spot_content"),
        Index("ix_spot_content_spot", "spot_id"),
        Index("ix_spot_content_content", "content_id"),
    )

# ----------------------------
# 中間: user_oshi（User × Oshi）
# ----------------------------
class UserOshi(Base):
    __tablename__ = "user_oshi"

    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    oshi_id = Column(BigInteger, ForeignKey("oshis.id", ondelete="CASCADE"), nullable=False)
    registered_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("user_id", "oshi_id", name="pk_user_oshi"),
        Index("ix_user_oshi_user", "user_id"),
        Index("ix_user_oshi_oshi", "oshi_id"),
    )

# ----------------------------
# 中間: spot_oshi（Spot × Oshi）※テーブル名はご提示どおり
# ----------------------------
class SpotsOshi(Base):
    __tablename__ = "spot_oshi"

    spot_id = Column(BigInteger, ForeignKey("spots.id", ondelete="CASCADE"), nullable=False)
    oshi_id = Column(BigInteger, ForeignKey("oshis.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("spot_id", "oshi_id", name="pk_spot_oshi"),
        Index("ix_spot_oshi_spot", "spot_id"),
        Index("ix_spot_oshi_oshi", "oshi_id"),
    )


__all__ = [
    "User",
    "Oshi",
    "Spot",
    "Content",
    "SpotContent",
    "UserOshi",
    "SpotsOshi",
]
