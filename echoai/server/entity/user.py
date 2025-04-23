import uuid
from datetime import datetime

from sqlalchemy import VARCHAR, DATETIME, INTEGER, CHAR, BIGINT, VARBINARY, ForeignKey
from sqlalchemy import func as db_func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from echoai.server.entity.base import BaseEntity

class UserAccountEntity(BaseEntity):
    __tablename__ = "user_account"
    __table_args__ = {
        "comment": "用户表"
    }
    
    uuid: Mapped[str] = mapped_column(
        CHAR(36),
        nullable=False,
        unique=True,
        comment="用户唯一标识",
        default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        VARCHAR(64),
        nullable=False,
        unique=True,
        comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        VARCHAR(128),
        unique=True,
        comment="用户邮箱"
    )
    phone: Mapped[str] = mapped_column(
        VARCHAR(32),
        unique=True,
        comment="用户手机号"
    )
    password: Mapped[str] = mapped_column(
        VARCHAR(256),
        nullable=False,
        comment="用户密码"
    )
    is_deleted: Mapped[bool] = mapped_column(
        INTEGER(1),
        nullable=False,
        default=0,
        comment="用户是否被删除, 0 未删除, 1 已删除"
    )
    is_disabled: Mapped[bool] = mapped_column(
        INTEGER(1),
        nullable=False,
        default=0,
        comment="用户是否被禁用, 0 未禁用, 1 已禁用"
    )
    create_time: Mapped[datetime] = mapped_column(
        DATETIME(3),
        nullable=False,
        default=db_func.now(),
        comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DATETIME(3),
        nullable=False,
        default=db_func.now(),
        onupdate=db_func.now(),
        comment="更新时间"
    )
    refresh_tokens: Mapped[list["UserRefreshTokenEntity"]] = relationship(
        back_populates="user_account",
        cascade="all, delete-orphan",  # 父子同生同灭，不留孤儿
        lazy="selectin"
    )
    
class UserRefreshTokenEntity(BaseEntity):
    __tablename__ = "user_refresh_token"
    __table_args__ = {
        "comment": "用户刷新令牌表"
    }
    
    jti: Mapped[str] = mapped_column(
        VARCHAR(256),
        nullable=False,
        unique=True,
        default=uuid.uuid4,
        comment="JWT ID"
    )
    user_id: Mapped[int] = mapped_column(
        BIGINT,
        ForeignKey(
            "user_account.id",
            name="fk_user_refresh_token_user_account_id",
            ondelete="CASCADE"
        ),
        nullable=False,
        comment="用户ID"
    )
    user_agent: Mapped[str | None] = mapped_column(
        VARCHAR(256),
        comment="UA 指纹（浏览器/设备信息）"
    )
    ip_address: Mapped[str | None] = mapped_column(
        VARBINARY(16),
        comment="IP 地址"
    )
    expires_time: Mapped[datetime] = mapped_column(
        DATETIME(3),
        nullable=False,
        comment="过期时间"
    )
    is_revoked: Mapped[bool] = mapped_column(
        INTEGER(1),
        nullable=False,
        default=0,
        comment="是否被撤销, 0 未撤销, 1 已撤销"
    )
    create_time: Mapped[datetime] = mapped_column(
        DATETIME(3),
        nullable=False,
        default=db_func.now(),
        comment="创建时间"
    )
    update_time: Mapped[datetime] = mapped_column(
        DATETIME(3),
        nullable=False,
        default=db_func.now(),
        onupdate=db_func.now(),
        comment="更新时间"
    )
    user_account: Mapped["UserAccountEntity"] = relationship(
        back_populates="refresh_tokens",
        lazy="joined"
    )
    