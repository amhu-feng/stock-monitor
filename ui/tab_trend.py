# -*- coding: utf-8 -*-
"""页签⑦ 走势分析：股票/指数 多周期K线 + 本地指标计算。"""
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from core import datasource

PERIODS = [("30天", 30), ("60天", 60), ("90天", 90), ("半年", 180), ("一年", 365), ("三年", 1095)]


class TrendTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self._build()

    def _build(self):
        top = ttk.Frame(self.frame)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        ttk.Label(top, text="代码").pack(side=tk.LEFT)
        self.var_code = tk.StringVar(value="sh000001")
        ttk.Entry(top, textvariable=self.var_code, width=12).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(top, text="周期").pack(side=tk.LEFT)
        self.var_period = tk.StringVar(value="90天")
        cb = ttk.Combobox(top, textvariable=self.var_period, state="readonly", width=6,
                          values=[p[0] for p in PERIODS])
        cb.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Button(top, text="查看走势", command=self.draw).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="显示字号").pack(side=tk.LEFT, padx=(18, 2))
        self.font_size_var = tk.StringVar(value=str(self.app.cfg.font_size))
        fcb = ttk.Combobox(top, textvariable=self.font_size_var, width=4, state="readonly",
                           values=[str(i) for i in range(9, 19)])
        fcb.pack(side=tk.LEFT)
        fcb.bind("<<ComboboxSelected>>",
                 lambda _e: self.app.set_font(self.font_size_var.get()))

        # 常用指数快捷
        bar = ttk.Frame(self.frame)
        bar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
        ttk.Label(bar, text="常用指数：").pack(side=tk.LEFT)
        for pref, name in datasource.MAIN_INDEXES:
            ttk.Button(bar, text=name, width=8,
                       command=lambda c=pref: self._quick(c)).pack(side=tk.LEFT, padx=2)

        # 图
        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.ax = self.fig.add_subplot(211)
        self.ax2 = self.fig.add_subplot(212, sharex=self.ax)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=6)
        self._empty()

        hint = ttk.Label(self.frame, text="代码可用：6位个股代码（如 600519）或指数代码（如 sh000001 / sz399006）。"
                                          "本地计算：周期涨跌幅、区间最高/最低、MA5/MA20/MA60。",
                         foreground="#888")
        hint.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=4)

    def _quick(self, pref):
        self.var_code.set(pref)
        self.draw()

    def _empty(self):
        self.ax.clear(); self.ax2.clear()
        self.ax.set_title("输入代码并选择周期后查看走势")
        self.ax.axis("off"); self.ax2.axis("off")
        self.canvas.draw()

    def draw(self):
        raw = self.var_code.get().strip()
        if not raw:
            return
        period_label = self.var_period.get()
        days = dict(PERIODS).get(period_label, 90)
        code = raw.lower()
        # 判断是指数还是个股：带 sh/sz/bj 前缀 且 属于指数代码，或用 MAIN_INDEXES 前缀
        is_index = any(code == p for p, _ in datasource.MAIN_INDEXES)
        if is_index:
            title_name = dict(datasource.MAIN_INDEXES).get(code, code)

            def _do():
                return datasource.get_index_kline(code, days)
        else:
            # 个股：去前缀取纯数字
            pure = code[2:] if code[:2] in ("sh", "sz", "bj") else code
            title_name = pure

            def _do():
                return datasource.get_kline(pure, days)
        self.app.run_task("走势", _do,
                          lambda d: self._on_draw_done(title_name, code, days, d))

    def _on_draw_done(self, title_name, code, days, data):
        if not data or len(data) < 2:
            messagebox.showinfo("提示", f"未能获取 {code} 的行情数据，请检查代码或稍后再试。",
                                parent=self.frame)
            self._empty()
            return
        self._plot(data, title_name, code, days)

    def _plot(self, data, title_name, code, days):
        closes = [d["close"] for d in data]
        highs = [d["high"] for d in data]
        lows = [d["low"] for d in data]
        opens = [d["open"] for d in data]
        vols = [d["volume"] for d in data]
        x = list(range(len(data)))

        # 本地计算指标
        chg = (closes[-1] - closes[0]) / closes[0] * 100 if closes[0] else 0
        hi = max(highs); lo = min(lows)

        self.ax.clear(); self.ax2.clear()
        for i in range(len(data)):
            color = "#c00000" if closes[i] >= opens[i] else "#0a7a2f"
            self.ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.7)
            self.ax.plot([i, i], [opens[i], closes[i]], color=color, linewidth=2.8)

        def ma(n):
            return [sum(closes[max(0, i - n + 1):i + 1]) / min(n, i + 1) for i in range(len(closes))]
        for n, color, lab in ((5, "#e69138", "MA5"), (20, "#6f42c1", "MA20"), (60, "#2f7fbf", "MA60")):
            if len(closes) >= n:
                self.ax.plot(x, ma(n), color=color, linewidth=1, label=lab)

        color = "#0a7a2f" if chg >= 0 else "#c00000"
        self.ax.set_title(f"{title_name}（{code}）  {days}日走势   周期涨跌 {chg:+.2f}%   区间最高 {hi:.2f} / 最低 {lo:.2f} / 最新 {closes[-1]:.2f}",
                          color=color, fontsize=11)
        self.ax.legend(loc="upper left", fontsize=8)
        self.ax.grid(alpha=0.3)

        # 成交量副图
        vcolors = ["#c00000" if closes[i] >= opens[i] else "#0a7a2f" for i in range(len(data))]
        self.ax2.bar(x, vols, color=vcolors, width=0.8)
        self.ax2.set_ylabel("成交量")
        self.ax2.grid(alpha=0.3)

        step = max(1, len(x) // 8)
        self.ax.set_xticks(x[::step])
        self.ax.set_xticklabels([data[i]["date"][5:] for i in x[::step]], rotation=45, fontsize=8)
        self.ax2.set_xticks(x[::step])
        self.ax2.set_xticklabels([data[i]["date"][5:] for i in x[::step]], rotation=45, fontsize=8)
        self.fig.autofmt_xdate()
        self.fig.tight_layout()
        self.canvas.draw()
