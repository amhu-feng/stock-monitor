# -*- coding: utf-8 -*-
"""页签③ 快速手续费计算器：试算一单，不入库。"""
import tkinter as tk
from tkinter import ttk

from core import fees


class CalcTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self._build()

    def _build(self):
        wrap = ttk.Frame(self.frame)
        wrap.pack(padx=20, pady=20, anchor=tk.NW)
        self.var_price = tk.StringVar(value="10.00")
        self.var_shares = tk.StringVar(value="100")
        self.var_sell = tk.StringVar(value="10.10")
        self.var_comm = tk.StringVar(value=str(self.app.fee_cfg.comm_rate))

        rows = [("买入价", self.var_price), ("股数", self.var_shares),
                ("卖出价", self.var_sell), ("佣金率(如0.00025)", self.var_comm)]
        for i, (lab, v) in enumerate(rows):
            ttk.Label(wrap, text=lab).grid(row=i, column=0, sticky="w", pady=6, padx=4)
            e = ttk.Entry(wrap, textvariable=v, width=22)
            e.grid(row=i, column=1, padx=4)
            v.trace_add("write", lambda *_: self._calc())

        ttk.Label(wrap, text="费率来源：页签④配置。卖出含印花税1‰。",
                  foreground="#888").grid(row=4, column=0, columnspan=2, pady=8)

        self.out = tk.Text(self.frame, width=60, height=16, font=("Microsoft YaHei", 10),
                           state=tk.DISABLED, bg="#fafafa")
        self.out.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=10)

    def _cfg(self):
        c = self.app.fee_cfg
        try:
            comm = float(self.var_comm.get())
            if comm > 0:
                return fees.FeeConfig(comm_rate=comm, min_comm=c.min_comm,
                                      transfer_rate=c.transfer_rate, stamp_rate=c.stamp_rate,
                                      use_min_comm=c.use_min_comm)
        except Exception:
            pass
        return c

    def _calc(self):
        try:
            buy = float(self.var_price.get())
            shares = int(float(self.var_shares.get()))
            sell = float(self.var_sell.get())
        except Exception:
            return
        if buy <= 0 or shares <= 0:
            return
        cfg = self._cfg()
        r = fees.simulate(sell, shares, buy, cfg)
        lines = [
            "════ 手续费与保本计算 ════",
            f"买入金额        : {r['buy_amount']:,.2f} 元",
            f"买入佣金        : {r['buy_comm']:.2f} 元",
            f"买入过户费      : {r['buy_transfer']:.2f} 元",
            f"买入总成本      : {r['buy_total']:,.2f} 元",
            "",
            f"卖出金额        : {r['sell_amount']:,.2f} 元",
            f"卖出佣金        : {r['sell_comm']:.2f} 元",
            f"卖出过户费      : {r['sell_transfer']:.2f} 元",
            f"卖出印花税      : {r['sell_stamp']:.2f} 元",
            f"卖出总手续费    : {r['sell_fee_total']:.2f} 元",
            "",
            f"【保本卖出价】   : {r['breakeven']:.3f} 元",
            f"【净盈亏】       : {r['pnl']:+,.2f} 元",
            f"【净盈亏率】     : {r['pnl_pct']:+.2f} %",
        ]
        if r["pnl"] > 0:
            lines.append("")
            lines.append("✅ 该价格卖出扣完手续费后有利润")
        elif r["pnl"] < 0:
            lines.append("")
            lines.append("⚠️ 该价格卖出扣完手续费后亏损（注意5元最低佣金）")
        self.out.configure(state=tk.NORMAL)
        self.out.delete("1.0", tk.END)
        self.out.insert(tk.END, "\n".join(lines))
        self.out.configure(state=tk.DISABLED)
