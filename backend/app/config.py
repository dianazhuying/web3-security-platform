"""应用配置: 通过环境变量 / .env 文件加载."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Web3 Security Intelligence API"
    API_PREFIX: str = "/api/v1"

    # 数据库: 默认 SQLite, 可切换 PostgreSQL
    DATABASE_URL: str = "sqlite:///./web3_security.db"

    # 定时抓取间隔(秒), 默认 1 小时
    FETCH_INTERVAL_SECONDS: int = 3600
    # 是否启用定时任务
    ENABLE_SCHEDULER: bool = True
    # 启动时是否自动填充历史事件
    SEED_ON_STARTUP: bool = True
    # 定时任务时区
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"

    # 数据源: defillama (真实公开接口) | simulate (模拟回退)
    DATA_SOURCE: str = "defillama"
    # 单次真实抓取最多新入库的事件数
    FETCH_BATCH_SIZE: int = 5
    # DefiLlama Hacks 公共数据接口
    DEFILLAMA_HACKS_URL: str = "https://api.llama.fi/hacks"

    # 真实数据源失败重试: 次数 + 指数退避基数(秒), 即 10s → 20s → 40s
    FETCH_RETRY_TIMES: int = 3
    FETCH_RETRY_BACKOFF_SECONDS: int = 10

    # 日志级别与目录 (backend/logs/app.log)
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    # 前端静态资源目录 (本地默认 backend 上级的 frontend; Docker 内为 /app/frontend)
    FRONTEND_DIR: str = "../frontend"

    # CORS 允许源, "*" 或逗号分隔列表
    CORS_ORIGINS: str = "*"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
