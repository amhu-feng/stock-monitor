# -*- coding: utf-8 -*-
"""
手续费计算引擎（含最低5元佣金）
所有费率为可配置，实盘必须开启最低佣金。
"""
from dataclasses import dataclass


@dataclass
class FeeConfig:
    comm_rate: float = 0.00025   # 佣金率（默认万2.5）
    min_comm: float = 5.0        # 最低佣金
    transfer_rate: float = 0.00001  # 过户费 0.01‰
    stamp_rate: float = 0.001    # 印花税 1‰（卖出单边）
    use_min_comm: bool = True    # 是否启用最低5元


def _max_comm(fee, amount, rate, min_comm, use_min):
    c = amount * rate
    if use_min:
        return max(c, min_comm)
    return c


def buy_cost(price, shares, cfg: FeeConfig):
    """买入总成本。返回 dict。"""
    amount = price * shares
    comm = _max_comm(cfg, amount, cfg.comm_rate, cfg.min_comm, cfg.use_min_comm)
    transfer = amount * cfg.transfer_rate
    total = amount + comm + transfer
    return {
        "amount": amount,
        "comm": comm,
        "transfer": transfer,
        "total": total,
    }


def sell_fee(price, shares, cfg: FeeConfig):
    """卖出总费用。返回 dict。"""
    amount = price * shares
    comm = _max_comm(cfg, amount, cfg.comm_rate, cfg.min_comm, cfg.use_min_comm)
    transfer = amount * cfg.transfer_rate
    stamp = amount * cfg.stamp_rate
    total = comm + transfer + stamp
    return {
        "amount": amount,
        "comm": comm,
        "transfer": transfer,
        "stamp": stamp,
        "total": total,
    }


def sell_rate(cfg: FeeConfig):
    """综合卖出费率（用于保本价公式）。"""
    return cfg.comm_rate + cfg.transfer_rate + cfg.stamp_rate


def breakeven_price(price, shares, cfg: FeeConfig):
    """保本卖出价：令净盈亏=0 反推的最低卖出价。"""
    b = buy_cost(price, shares, cfg)
    return b["total"] / shares / (1 - sell_rate(cfg))


def net_pnl(price, shares, buy_price, cfg: FeeConfig):
    """净盈亏 = 卖出金额 − 买入总成本 − 卖出总费用。"""
    b = buy_cost(buy_price, shares, cfg)
    s = sell_fee(price, shares, cfg)
    pnl = s["amount"] - b["total"] - s["total"]
    pnl_pct = pnl / b["total"] * 100 if b["total"] else 0
    return {
        "buy_total": b["total"],
        "sell_amount": s["amount"],
        "sell_fee": s["total"],
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }


def target_price(price, shares, cfg: FeeConfig, min_profit_pct=0.003):
    """目标卖出价 = 保本价 × (1 + 最小盈利阈值)。"""
    be = breakeven_price(price, shares, cfg)
    return be * (1 + min_profit_pct)


def simulate(price, shares, buy_price, cfg: FeeConfig):
    """一次性完整计算（手续费计算器面板用）。"""
    b = buy_cost(buy_price, shares, cfg)
    s = sell_fee(price, shares, cfg)
    pnl = s["amount"] - b["total"] - s["total"]
    pnl_pct = pnl / b["total"] * 100 if b["total"] else 0
    be = b["total"] / shares / (1 - sell_rate(cfg))
    return {
        "buy_amount": b["amount"],
        "buy_comm": b["comm"],
        "buy_transfer": b["transfer"],
        "buy_total": b["total"],
        "sell_amount": s["amount"],
        "sell_comm": s["comm"],
        "sell_transfer": s["transfer"],
        "sell_stamp": s["stamp"],
        "sell_fee_total": s["total"],
        "breakeven": be,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
    }
