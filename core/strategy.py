# -*- coding: utf-8 -*-
"""策略引擎：对每条持仓判断状态（持有/保本/止盈/止损），带信号冷却。"""
import time


class StrategyEngine:
    def __init__(self):
        self._cooldown = {}  # position_id -> last alert ts

    def reset(self):
        self._cooldown.clear()

    def evaluate(self, pos, price, cfg, fee_cfg):
        """返回 dict: state, breakeven, target, stop, pnl, pnl_pct, msg。
        不做任何自动交易，仅输出状态与提示文本。"""
        from . import fees
        code = pos["code"]
        buy_price = pos["buy_price"]
        shares = pos["shares"]
        # 单票费率覆盖
        eff_cfg = fee_cfg
        comm = pos.get("comm_rate", -1)
        if comm and comm > 0:
            eff_cfg = fees.FeeConfig(comm_rate=comm, min_comm=fee_cfg.min_comm,
                                     transfer_rate=fee_cfg.transfer_rate,
                                     stamp_rate=fee_cfg.stamp_rate,
                                     use_min_comm=fee_cfg.use_min_comm)
        # 单票最小盈利覆盖
        min_pct = pos.get("min_profit_pct", -1)
        if not (min_pct and min_pct > 0):
            min_pct = cfg.min_profit_pct
        # 止损
        stop = pos.get("stop_loss", -1)
        if not (stop and stop > 0):
            stop = buy_price * (1 - cfg.default_stop_loss_pct)

        be = fees.breakeven_price(buy_price, shares, eff_cfg)
        target = be * (1 + min_pct)
        np_ = fees.net_pnl(price, shares, buy_price, eff_cfg)
        state = "holding"
        msg = ""
        if price <= 0:
            state = "no_data"
            msg = "暂无行情"
        elif stop > 0 and price <= stop:
            state = "stop_loss"
            msg = f"跌破止损价 {stop:.3f}"
        elif price >= target:
            state = "take_profit"
            msg = f"已达目标价 {target:.3f}，扣费净盈 {np_['pnl']:.2f} 元"
        elif price >= be:
            state = "breakeven"
            msg = f"已过保本价 {be:.3f}，可观察"
        return {
            "state": state, "breakeven": be, "target": target, "stop": stop,
            "pnl": np_["pnl"], "pnl_pct": np_["pnl_pct"], "msg": msg,
        }

    def should_alert(self, pid, state, cooldown_min):
        """是否应触发弹窗提醒（按状态+冷却）。仅止盈/止损弹窗。"""
        if state not in ("take_profit", "stop_loss"):
            return False, None
        now = time.time()
        last = self._cooldown.get(pid, 0)
        if now - last < cooldown_min * 60:
            return False, None
        self._cooldown[pid] = now
        return True, state
