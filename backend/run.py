"""开发/本地启动入口: python run.py

支持通过环境变量 PORT / HOST 动态绑定端口与地址 (Render/Koyeb 等平台自动注入 PORT).
"""
import os

import uvicorn

if __name__ == "__main__":
    # 未设置 PORT 时回退到 8000 (本地开发默认)
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    reload = os.environ.get("RELOAD", "0").lower() in ("1", "true", "yes")

    uvicorn.run("app.main:app", host=host, port=port, reload=reload)