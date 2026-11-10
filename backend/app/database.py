"""数据库引擎与会话管理 (SQLAlchemy 2.0)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# SQLAlchemy 2.x 不认 postgres:// scheme —— Render 默认注入 postgres://, 需转成 postgresql://
_db_url = settings.DATABASE_URL
if _db_url.startswith("postgres://"):
    _db_url = "postgresql://" + _db_url[len("postgres://"):]
    print(f"[database] 已将 postgres:// scheme 规范化为 postgresql://")

_connect_args = (
    {"check_same_thread": False}
    if _db_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    _db_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI 依赖: 提供请求级数据库会话."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
