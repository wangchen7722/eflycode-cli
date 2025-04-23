from sqlalchemy import BigInteger, MetaData, JSON
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from echoai.server.utils.snowflake import generate_snowflake_id

class BaseEntity(AsyncAttrs, DeclarativeBase):
    """
    所有数据库实体的基类
    """
    __abstract__ = True
    
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=False,
        default=generate_snowflake_id
    )
    
    metadata = MetaData(
        # ix: Index
        # uq: Unique constraint
        # ck: Check constraint
        # fk: Foreign key
        # pk: Primary key
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_label)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_label)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s"
        }
    )
    
    type_annotation_map = {
        list: JSON,
        dict: JSON,
    }
    
    def __repr__(self) -> str:
        # 仅展示纯粹的列属性，避免触发延迟加载
        cols = []
        for col in self.__table__.columns:
            val = getattr(self, col.name, None)
            cols.append(f"{col.name}={val!r}")
        cols_str = ", ".join(cols)
        return f"<{self.__class__.__name__}({cols_str})>"
    