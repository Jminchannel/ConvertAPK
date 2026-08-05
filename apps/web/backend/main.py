"""兼容旧的 ``python main.py`` 启动方式。"""

from importlib import import_module
import os
import sys


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("CONVERTAPK_PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
else:
    sys.modules[__name__] = import_module("app.main")
