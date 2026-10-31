# -*- coding: utf-8 -*-
"""股票盯盘助手 - 入口"""
import os
import sys

# 确保能导入本项目模块（打包后同样生效）
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

from core.db import init_db
from ui.app import App


def main():
    init_db()
    app = App()
    app.run()


if __name__ == "__main__":
    main()
