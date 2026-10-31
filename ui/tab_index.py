# -*- coding: utf-8 -*-
"""页签⑥ 大盘指数监控：主要指数当天开盘/收盘/涨跌。"""
import time as _t
import tkinter as tk
from tkinter import ttk

from core import datasource


class IndexTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self._build()

    def _build(self):
        top = ttk.Frame(self.frame)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        ttk.Label(top, text="大盘指数（当天 开盘/昨收/最新/涨跌幅）").pack(side=tk.LEFT)
        ttk.Button(top, text="手动刷新", command=self.manual_refresh).pack(side=tk.LEFT, padx=10)
        ttk.Label(top, text="显示字号").pack(side=tk.LEFT, padx=(18, 2))
        self.font_size_var = tk.StringVar(value=str(self.app.cfg.font_size))
        fcb = ttk.Combobox(top, textvariable=self.font_size_var, width=4, state="readonly",
                           values=[str(i) for i in range(9, 19)])
        fcb.pack(side=tk.LEFT)
        fcb.bind("<<ComboboxSelected>>",
                 lambda _e: self.app.set_font(self.font_size_var.get()))

        cols = ("name", "open", "preclose", "price", "pct", "high", "low", "time")
        heads = {"name": "指数", "open": "今开", "preclose": "昨收", "price": "最新(收盘)",
                 "pct": "涨跌幅%", "high": "最高", "low": "最低", "time": "时间"}
        widths = {"name": 130, "open": 95, "preclose": 95, "price": 100,
                  "pct": 90, "high": 95, "low": 95, "time": 80}
        wrap = ttk.Frame(self.frame)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=2)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.tag_configure("up", foreground="#0a7a2f")
        self.tree.tag_configure("down", foreground="#c00000")
        self.tree.tag_configure("flat", foreground="#333333")

        info = ttk.Label(self.frame, text="注：数据来自新浪财经公开行情；涨跌幅为当日相对昨收。",
                         foreground="#888")
        info.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=4)

    def update(self, index_data, ts=None):
        self.tree.delete(*self.tree.get_children())
        for pref, d in index_data.items():
            pct = d.get("pct", 0)
            tag = "up" if pct > 0 else ("down" if pct < 0 else "flat")
            self.tree.insert("", tk.END, values=(
                d.get("name", pref), f"{d.get('open',0):.2f}", f"{d.get('pre_close',0):.2f}",
                f"{d.get('price',0):.2f}", f"{pct:+.2f}", f"{d.get('high',0):.2f}",
                f"{d.get('low',0):.2f}", d.get("time", "")), tags=(tag,))

    def manual_refresh(self):
        self.app.run_task("指数", lambda: datasource.get_index_realtime(), self._on_refresh)

    def _on_refresh(self, res):
        if res:
            self.update(res)
            self.app.flash_status(f"大盘指数已刷新 {_t.strftime('%H:%M:%S')}")
