# -*- coding: utf-8 -*-
"""配置管理：本地 json 存储，无账号无外发。"""
import json
import os
from dataclasses import dataclass, asdict, field
from .paths import DATA_DIR

CONFIG_FILE = os.path.join(DATA_DIR, "config.json")


@dataclass
class AppConfig:
    # 费率
    comm_rate: float = 0.00025
    min_comm: float = 5.0
    transfer_rate: float = 0.00001
    stamp_rate: float = 0.001
    use_min_comm: bool = True
    # 策略
    min_profit_pct: float = 0.003      # 全局最小盈利阈值
    watch_interval: int = 15           # 行情轮询秒
    signal_cooldown_min: int = 5       # 信号冷却分钟
    default_stop_loss_pct: float = 0.05  # 默认止损5%
    stop_loss_enabled: bool = True
    sound_enabled: bool = True
    # 新闻
    news_interval: int = 300           # 新闻采集秒
    news_retain_days: int = 30
    # 自选
    watchlist: list = field(default_factory=list)  # 额外自选股票代码（不含持仓）
    industry_tags: list = field(default_factory=list)  # 关注的行业板块关键词
    # 界面
    font_size: int = 10           # 全局字体大小（9-16）
    theme: str = "light"          # light 浅色 / dark 深色


def default_config() -> AppConfig:
    return AppConfig()


def load_config() -> AppConfig:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            cfg = AppConfig()
            for k, v in d.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            return cfg
    except Exception:
        pass
    return AppConfig()


def save_config(cfg: AppConfig):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, ensure_ascii=False, indent=2)
