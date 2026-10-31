# -*- coding: utf-8 -*-
"""页签① 自选行情监控：实时行情表 + K线图 + 信号提醒栏。"""
import math
import tkinter as tk
from tkinter import ttk, simpledialog

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from core import datasource


class WatchTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self._codes = {}  # code -> {"name",...}
        self._page = 1
        self._pages = 1
        self._page_size = 30
        self._all_rows = []
        self._build()

    def _build(self):
        top = ttk.Frame(self.frame)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Button(top, text="手动刷新", command=self.manual_refresh).pack(side=tk.LEFT, padx=2)
        ttk.Button(top, text="添加自选", command=self.add_watch).pack(side=tk.LEFT, padx=2)
        ttk.Label(top, text="选中股票下方显示K线（日线60日）").pack(side=tk.LEFT, padx=10)
        ttk.Label(top, text="显示字号").pack(side=tk.LEFT, padx=(18, 2))
        self.font_size_var = tk.StringVar(value=str(self.app.cfg.font_size))
        fcb = ttk.Combobox(top, textvariable=self.font_size_var, width=4, state="readonly",
                           values=[str(i) for i in range(9, 19)])
        fcb.pack(side=tk.LEFT)
        fcb.bind("<<ComboboxSelected>>", lambda _e: self._apply_font())

        body = ttk.Panedwindow(self.frame, orient=tk.HORIZONTAL)
        body.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=2)

        # 左：行情表
        left = ttk.Frame(body)
        body.add(left, weight=3)
        cols = ("code", "name", "price", "pct", "ts")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=18)
        heads = {"code": "代码", "name": "名称", "price": "现价", "pct": "涨跌幅%", "ts": "更新时间"}
        widths = {"code": 90, "name": 110, "price": 90, "pct": 90, "ts": 130}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor=tk.CENTER)
        ys = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # 分页栏：分批显示，防止一次显示过多
        pg = ttk.Frame(left)
        pg.pack(side=tk.BOTTOM, fill=tk.X, pady=(2, 0))
        ttk.Button(pg, text="◀ 上一页", command=self._prev_page).pack(side=tk.LEFT)
        self.page_var = tk.StringVar(value="1/1")
        ttk.Label(pg, textvariable=self.page_var).pack(side=tk.LEFT, padx=8)
        ttk.Button(pg, text="下一页 ▶", command=self._next_page).pack(side=tk.LEFT)
        ttk.Label(pg, text="每页").pack(side=tk.LEFT, padx=(14, 2))
        self.page_size_var = tk.StringVar(value="30")
        pcb = ttk.Combobox(pg, textvariable=self.page_size_var, width=4, state="readonly",
                           values=["20", "30", "50", "100"])
        pcb.pack(side=tk.LEFT)
        pcb.bind("<<ComboboxSelected>>", lambda _e: self._set_page_size())
        ttk.Label(pg, text="条").pack(side=tk.LEFT)

        # 右：K线
        right = ttk.Frame(body)
        body.add(right, weight=2)
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=right)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.ax.set_title("选中股票显示K线")
        self.ax.axis("off")
        self.canvas.draw()

        # 信号提醒栏
        bar = ttk.LabelFrame(self.frame, text="信号提醒（最近）")
        bar.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=4)
        self.alert_text = tk.Text(bar, height=5, state=tk.DISABLED)
        self.alert_text.pack(fill=tk.X)

    def _all_codes(self):
        codes = list(self._codes.keys())
        for p in self.app.holding_positions:
            codes.append(str(p["code"]))
        codes += [str(c) for c in (self.app.cfg.watchlist or [])]
        return list(dict.fromkeys(codes))

    def update_watch(self, rt, ts):
        import time as _t
        ts_str = _t.strftime("%H:%M:%S", _t.localtime(ts))
        for code, d in rt.items():
            self._codes[code] = {"name": d.get("name", code), "price": d.get("price", 0),
                                 "pct": d.get("pct", 0)}
        rows = {}
        for code, d in self._codes.items():
            price = d.get("price", 0)
            pct = d.get("pct", 0)
            rows[code] = (code, d.get("name", code), price, pct, ts_str)
        self._all_rows = list(rows.values())
        self._pages = max(1, math.ceil(len(self._all_rows) / self._page_size))
        if self._page > self._pages:
            self._page = self._pages
        self._render_page()

    def _render_page(self):
        self.tree.delete(*self.tree.get_children())
        start = (self._page - 1) * self._page_size
        for r in self._all_rows[start:start + self._page_size]:
            tag = "up" if r[3] > 0 else ("down" if r[3] < 0 else "flat")
            self.tree.insert("", tk.END, values=r, tags=(tag,))
        self.tree.tag_configure("up", foreground="#0a7a2f")
        self.tree.tag_configure("down", foreground="#c00000")
        self.tree.tag_configure("flat", foreground="#333333")
        if hasattr(self, "page_var"):
            self.page_var.set(f"{self._page}/{self._pages}")

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self._render_page()

    def _next_page(self):
        if self._page < self._pages:
            self._page += 1
            self._render_page()

    def _set_page_size(self):
        try:
            self._page_size = int(self.page_size_var.get())
        except Exception:
            self._page_size = 30
        self._page = 1
        self._pages = max(1, math.ceil(len(self._all_rows) / self._page_size))
        self._render_page()

    def _apply_font(self):
        try:
            self.app.cfg.font_size = int(self.font_size_var.get())
        except Exception:
            return
        from core.config import save_config
        save_config(self.app.cfg)
        self.app.apply_theme()
        self.app.flash_status(f"字体已调整为 {self.app.cfg.font_size} 号")

    def manual_refresh(self):
        codes = self._all_codes()
        if not codes:
            self.app.flash_status("暂无自选/持仓可刷新")
            return
        self.app.run_task("行情", lambda: datasource.get_realtime(codes), self._on_rt)

    def _on_rt(self, rt):
        if rt:
            import time as _t
            self.update_watch(rt, _t.time())

    def add_watch(self):
        kw = simpledialog.askstring("添加自选", "输入股票代码（如 600519）或名称：", parent=self.frame)
        if not kw:
            return
        self.app.run_task("行情", lambda: datasource.search_code(kw.strip()),
                          lambda found: self._on_search(kw.strip(), found))

    def _on_search(self, kw, found):
        if not found:
            self.app.flash_status(f"未找到 {kw}")
            return
        code = found[0]["code"]
        if code not in (self.app.cfg.watchlist or []):
            self.app.cfg.watchlist.append(code)
            from core.config import save_config
            save_config(self.app.cfg)
        self.app.flash_status(f"已添加自选 {code} {found[0]['name']}")
        self.manual_refresh()

    def _on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        if not vals:
            return
        code = str(vals[0])
        self.draw_kline(code)

    def draw_kline(self, code):
        self.app.run_task("行情", lambda: datasource.get_kline(code, 60),
                          lambda d: self._render_kline(code, d))

    def _render_kline(self, code, data):
        self.ax.clear()
        if not data:
            self.ax.set_title(f"{code} K线（暂无数据）")
            self.ax.axis("off")
            self.canvas.draw()
            return
        closes = [d["close"] for d in data]
        highs = [d["high"] for d in data]
        lows = [d["low"] for d in data]
        opens = [d["open"] for d in data]
        dates = [d["date"][5:] for d in data]
        x = list(range(len(data)))
        for i in range(len(data)):
            color = "#c00000" if closes[i] >= opens[i] else "#0a7a2f"
            self.ax.plot([i, i], [lows[i], highs[i]], color=color, linewidth=0.8)
            self.ax.plot([i, i], [opens[i], closes[i]], color=color, linewidth=3.2)
        # 均线
        if len(data) >= 5:
            ma5 = [sum(closes[max(0, i-4):i+1]) / min(5, i+1) for i in range(len(closes))]
            self.ax.plot(x, ma5, color="#e69138", linewidth=1, label="MA5")
        if len(data) >= 20:
            ma20 = [sum(closes[max(0, i-19):i+1]) / min(20, i+1) for i in range(len(closes))]
            self.ax.plot(x, ma20, color="#6f42c1", linewidth=1, label="MA20")
        self.ax.set_title(f"{code} 日K（近60日）")
        self.ax.legend(loc="upper left", fontsize=8)
        self.ax.set_xticks(x[::max(1, len(x)//8)])
        self.ax.set_xticklabels([dates[i] for i in x[::max(1, len(x)//8)]], rotation=45, fontsize=8)
        self.ax.grid(alpha=0.3)
        self.fig.autofmt_xdate()
        self.canvas.draw()
