"""工具函数 — 跨脚本/EXE 的路径解析。"""

import sys
from pathlib import Path


def get_app_dir() -> Path:
    """获取应用根目录。

    开发模式下为脚本所在目录，PyInstaller 打包后为 exe 所在目录。
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后
        return Path(sys.executable).parent
    else:
        # 正常 Python 运行
        return Path(__file__).resolve().parent.parent
