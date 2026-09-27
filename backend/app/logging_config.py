"""日志配置: 控制台 + 滚动文件 (backend/logs/app.log)."""
import logging
import logging.handlers
from pathlib import Path

from app.config import settings

_FILE_LOG_LIMIT = 5 * 1024 * 1024  # 单文件 5MB
_FILE_LOG_BACKUP = 3              # 保留 3 个滚动备份


def setup_logging() -> None:
    """初始化根日志器: 同时输出到控制台与滚动文件."""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 幂等: 已存在同类 handler 则不重复添加
    has_file = any(isinstance(h, logging.handlers.RotatingFileHandler) for h in root.handlers)
    has_stream = any(isinstance(h, logging.StreamHandler) for h in root.handlers)

    if not has_file:
        fh = logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=_FILE_LOG_LIMIT,
            backupCount=_FILE_LOG_BACKUP,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        root.addHandler(fh)

    if not has_stream:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
