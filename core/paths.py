# -*- coding: utf-8 -*-
"""统一路径：源码模式用项目目录，打包后(exe)用可执行文件所在目录，保证数据持久化。"""
import os
import sys


def get_base_dir():
    if getattr(sys, "frozen", False):  # PyInstaller 打包运行
        return os.path.dirname(os.path.abspath(sys.executable))
    # 源码运行：core/paths.py -> stock_monitor/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = get_base_dir()
DATA_DIR = os.path.join(BASE_DIR, "data")
