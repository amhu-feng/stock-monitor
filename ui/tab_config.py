# -*- coding: utf-8 -*-
"""页签④ 策略&风控配置：费率、策略参数、新闻参数。"""
import tkinter as tk
from tkinter import ttk, messagebox

from core.config import save_config
from core import fees


class ConfigTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self._build()

    def _build(self):
        c = self.app.cfg
        f = self.app.fee_cfg

        self.vars = {}
        g1 = ttk.LabelFrame(self.frame, text="费率参数")
        g1.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)
        fee_rows = [
            ("comm_rate", "佣金率", f.comm_rate),
            ("min_comm", "最低佣金(元)", f.min_comm),
            ("transfer_rate", "过户费率", f.transfer_rate),
            ("stamp_rate", "印花税率", f.stamp_rate),
        ]
        for i, (k, lab, val) in enumerate(fee_rows):
            ttk.Label(g1, text=lab).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            self.vars[k] = tk.StringVar(value=str(val))
            ttk.Entry(g1, textvariable=self.vars[k], width=16).grid(row=i, column=1, padx=6)
        self.vars["use_min_comm"] = tk.BooleanVar(value=f.use_min_comm)
        ttk.Checkbutton(g1, text="启用最低佣金（实盘建议开启）",
                        variable=self.vars["use_min_comm"]).grid(row=4, column=0, columnspan=2, sticky="w", padx=8)

        g2 = ttk.LabelFrame(self.frame, text="策略与风控")
        g2.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)
        strat_rows = [
            ("min_profit_pct", "最小盈利阈值", c.min_profit_pct),
            ("watch_interval", "行情轮询间隔(秒)", c.watch_interval),
            ("signal_cooldown_min", "信号冷却(分钟)", c.signal_cooldown_min),
            ("default_stop_loss_pct", "默认止损比例", c.default_stop_loss_pct),
        ]
        for i, (k, lab, val) in enumerate(strat_rows):
            ttk.Label(g2, text=lab).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            self.vars[k] = tk.StringVar(value=str(val))
            ttk.Entry(g2, textvariable=self.vars[k], width=16).grid(row=i, column=1, padx=6)
        self.vars["sound_enabled"] = tk.BooleanVar(value=c.sound_enabled)
        ttk.Checkbutton(g2, text="开启声音提醒", variable=self.vars["sound_enabled"]).grid(
            row=len(strat_rows), column=0, columnspan=2, sticky="w", padx=8)

        g3 = ttk.LabelFrame(self.frame, text="新闻采集")
        g3.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)
        self.vars["news_interval"] = tk.StringVar(value=str(c.news_interval))
        self.vars["news_retain_days"] = tk.StringVar(value=str(c.news_retain_days))
        ttk.Label(g3, text="新闻采集间隔(秒)").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(g3, textvariable=self.vars["news_interval"], width=16).grid(row=0, column=1, padx=6)
        ttk.Label(g3, text="新闻保留天数").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Entry(g3, textvariable=self.vars["news_retain_days"], width=16).grid(row=1, column=1, padx=6)

        g4 = ttk.LabelFrame(self.frame, text="界面与外观")
        g4.pack(side=tk.TOP, fill=tk.X, padx=10, pady=6)
        self.vars["font_size"] = tk.StringVar(value=str(c.font_size))
        ttk.Label(g4, text="全局字体大小").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(g4, textvariable=self.vars["font_size"], width=8,
                     values=[str(i) for i in range(9, 19)], state="readonly").grid(row=0, column=1, padx=6)
        self.vars["theme"] = tk.StringVar(value="深色模式" if c.theme == "dark" else "浅色模式")
        ttk.Label(g4, text="配色主题").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Combobox(g4, textvariable=self.vars["theme"], width=10,
                     values=["浅色模式", "深色模式"], state="readonly").grid(row=1, column=1, padx=6)
        ttk.Button(g4, text="应用界面设置", command=self._apply_ui).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=8, pady=6)

        ttk.Button(self.frame, text="保存配置", command=self._save).pack(anchor=tk.W, padx=14, pady=10)
        ttk.Label(self.frame, text="保存后立即生效；持仓单票费率可在页签②单独覆盖；界面设置可单独点“应用界面设置”即时预览。",
                  foreground="#888").pack(anchor=tk.W, padx=14)

    def _save(self):
        c = self.app.cfg
        try:
            c.comm_rate = float(self.vars["comm_rate"].get())
            c.min_comm = float(self.vars["min_comm"].get())
            c.transfer_rate = float(self.vars["transfer_rate"].get())
            c.stamp_rate = float(self.vars["stamp_rate"].get())
            c.use_min_comm = self.vars["use_min_comm"].get()
            c.min_profit_pct = float(self.vars["min_profit_pct"].get())
            c.watch_interval = int(float(self.vars["watch_interval"].get()))
            c.signal_cooldown_min = int(float(self.vars["signal_cooldown_min"].get()))
            c.default_stop_loss_pct = float(self.vars["default_stop_loss_pct"].get())
            c.sound_enabled = self.vars["sound_enabled"].get()
            c.news_interval = int(float(self.vars["news_interval"].get()))
            c.news_retain_days = int(float(self.vars["news_retain_days"].get()))
            c.font_size = int(self.vars["font_size"].get())
            c.theme = "dark" if self.vars["theme"].get() == "深色模式" else "light"
        except Exception:
            messagebox.showerror("输入错误", "请检查各参数格式", parent=self.frame)
            return
        self.app.fee_cfg = fees.FeeConfig(
            comm_rate=c.comm_rate, min_comm=c.min_comm,
            transfer_rate=c.transfer_rate, stamp_rate=c.stamp_rate,
            use_min_comm=c.use_min_comm)
        save_config(c)
        self.app.engine.reset()
        self.app.apply_theme()
        self.app.flash_status("配置已保存并生效")

    def _apply_ui(self):
        c = self.app.cfg
        try:
            c.font_size = int(self.vars["font_size"].get())
        except Exception:
            c.font_size = 10
        c.theme = "dark" if self.vars["theme"].get() == "深色模式" else "light"
        save_config(c)
        self.app.apply_theme()
        self.app.flash_status("界面设置已应用")
