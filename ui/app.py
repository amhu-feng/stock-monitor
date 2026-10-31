# -*- coding: utf-8 -*-
"""主窗口：组装5个页签，启动后台行情/新闻线程，处理提醒通知。"""
import queue
import threading
import time
import winsound
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox

from core.config import load_config
from core import fees, db, datasource, strategy
from core.monitor import FetchMonitor
from ui.tab_watch import WatchTab
from ui.tab_positions import PositionsTab
from ui.tab_calc import CalcTab
from ui.tab_config import ConfigTab
from ui.tab_news import NewsTab
from ui.tab_index import IndexTab
from ui.tab_trend import TrendTab

DISCLAIMER = "本工具仅个人行情分析辅助，不构成投资建议。所有交易请由你本人在券商软件手动操作，股市有风险。"


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("股票盯盘助手 · 本地个人版")
        self.root.geometry("1320x840")
        self.root.minsize(1000, 680)

        self.cfg = load_config()
        self.fee_cfg = fees.FeeConfig(
            comm_rate=self.cfg.comm_rate, min_comm=self.cfg.min_comm,
            transfer_rate=self.cfg.transfer_rate, stamp_rate=self.cfg.stamp_rate,
            use_min_comm=self.cfg.use_min_comm)
        self.engine = strategy.StrategyEngine()
        self.q = queue.Queue()
        self._running = True

        self._build_topbar()
        self._build_monitor()
        self._build_notebook()
        self._build_statusbar()
        self.apply_theme()
        self._start_threads()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(300, self._pump)

    # ---------- 界面主题 ----------
    def _palette(self):
        dark = self.cfg.theme == "dark"
        return {
            "dark": dark,
            "bg": "#23272e" if dark else "#f2f3f5",
            "fg": "#e8eaed" if dark else "#1a1a1a",
            "panel": "#1c2027" if dark else "#ffffff",
            "select_bg": "#2f6fd0" if dark else "#0067c0",
            "select_fg": "#ffffff",
            "head_bg": "#2c323a" if dark else "#e3e6ea",
            "head_fg": "#e8eaed" if dark else "#222222",
            "btn_bg": "#39404a" if dark else "#e5e8ec",
            "entry_bg": "#1a1e24" if dark else "#ffffff",
            "border": "#3a414c" if dark else "#c9ced4",
        }

    def apply_theme(self, *_):
        import tkinter.font as tkfont
        style = ttk.Style(self.root)
        style.theme_use("clam")
        p = self._palette()

        # 字体大小
        size = max(9, min(18, int(self.cfg.font_size or 10)))
        for fname in ("TkDefaultFont", "TkTextFont", "TkHeadingFont",
                      "TkMenuFont", "TkFixedFont"):
            try:
                tkfont.nametofont(fname).configure(size=size)
            except Exception:
                pass

        style.configure(".", background=p["bg"], foreground=p["fg"])
        style.configure("TFrame", background=p["bg"])
        style.configure("TLabel", background=p["bg"], foreground=p["fg"])
        style.configure("TButton", background=p["btn_bg"], foreground=p["fg"],
                        bordercolor=p["border"], lightcolor=p["btn_bg"],
                        darkcolor=p["btn_bg"], padding=(10, 4))
        style.map("TButton", background=[("active", p["select_bg"])],
                  foreground=[("active", "#ffffff")])
        style.configure("TNotebook", background=p["bg"], bordercolor=p["border"])
        style.configure("TNotebook.Tab", background=p["btn_bg"], foreground=p["fg"],
                        padding=(14, 6))
        style.map("TNotebook.Tab",
                  background=[("selected", p["panel"])],
                  foreground=[("selected", p["fg"])])
        style.configure("Treeview", background=p["panel"], fieldbackground=p["panel"],
                        foreground=p["fg"], bordercolor=p["border"], rowheight=max(22, size + 12))
        style.map("Treeview", background=[("selected", p["select_bg"])],
                  foreground=[("selected", p["select_fg"])])
        style.configure("Treeview.Heading", background=p["head_bg"],
                        foreground=p["head_fg"], relief="flat", font=("Microsoft YaHei", size, "bold"))
        style.map("Treeview.Heading", background=[("active", p["head_bg"])])
        style.configure("TEntry", fieldbackground=p["entry_bg"], foreground=p["fg"],
                        insertcolor=p["fg"], bordercolor=p["border"])
        style.configure("TCombobox", fieldbackground=p["entry_bg"], foreground=p["fg"],
                        background=p["btn_bg"], arrowcolor=p["fg"], bordercolor=p["border"])
        style.configure("TSpinbox", fieldbackground=p["entry_bg"], foreground=p["fg"],
                        arrowcolor=p["fg"], bordercolor=p["border"])
        style.configure("TScrollbar", background=p["btn_bg"], troughcolor=p["bg"],
                        bordercolor=p["border"], arrowcolor=p["fg"])

        # matplotlib 图（自选 / 走势分析）
        try:
            import matplotlib.pyplot as _plt
            _plt.rcParams["figure.facecolor"] = p["bg"]
            _plt.rcParams["axes.facecolor"] = p["panel"]
            _plt.rcParams["axes.edgecolor"] = p["fg"]
            _plt.rcParams["text.color"] = p["fg"]
            _plt.rcParams["axes.labelcolor"] = p["fg"]
            _plt.rcParams["xtick.color"] = p["fg"]
            _plt.rcParams["ytick.color"] = p["fg"]
            for tab in (getattr(self, "tab_watch", None), getattr(self, "tab_trend", None)):
                fig = getattr(tab, "fig", None)
                if fig is not None:
                    fig.patch.set_facecolor(p["bg"])
                    for ax in fig.axes:
                        ax.set_facecolor(p["panel"])
                        ax.tick_params(colors=p["fg"])
                        for sp in ax.spines.values():
                            sp.set_color(p["fg"])
                        for lbl in (ax.title, ax.xaxis.label, ax.yaxis.label):
                            lbl.set_color(p["fg"])
                    fig.canvas.draw_idle()
        except Exception:
            pass

    # ---------- UI 骨架 ----------
    def _build_topbar(self):
        bar = ttk.Frame(self.root, padding=(8, 4))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(bar, text=DISCLAIMER, foreground="#888888").pack(side=tk.LEFT)

    def _build_monitor(self):
        """数据源后台监测提示行：流畅/卡顿/无法获取 + 网络延迟。"""
        self.monitor = FetchMonitor(self)
        row = ttk.Frame(self.root, padding=(8, 0))
        row.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(row, text="数据源监测：", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        self.mon_vars = {}
        self.mon_labels = {}
        for lb in ("行情", "指数", "新闻", "走势"):
            v = tk.StringVar(value=f"{lb}源 待机")
            lbl = ttk.Label(row, textvariable=v, foreground="#888888")
            lbl.pack(side=tk.LEFT, padx=(14, 0))
            self.mon_vars[lb] = v
            self.mon_labels[lb] = lbl

    def run_task(self, label, fn, on_done=None, **kw):
        """后台执行拉取并监测，主线程不阻塞；on_done 在主线程回调(result)。"""
        self.monitor.run(label, fn, on_done, **kw)

    def set_font(self, size):
        """统一字体调整入口：改全局字号并即时应用。"""
        try:
            size = int(size)
        except Exception:
            return
        self.cfg.font_size = size
        from core.config import save_config
        save_config(self.cfg)
        self.apply_theme()
        self.flash_status(f"字体已调整为 {size} 号")

    def _set_mon(self, label, note):
        v = self.mon_vars.get(label)
        if v:
            v.set(f"{label}源 {note}")

    @staticmethod
    def _state_color(state):
        return {"流畅": "#0a7a2f", "卡顿": "#d98324",
                "超时": "#d98324", "无法获取": "#c00000",
                "读取中": "#888888"}.get(state, "#888888")

    def _build_notebook(self):
        nb = ttk.Notebook(self.root)
        nb.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.nb = nb

        self.tab_watch = WatchTab(nb, self)
        self.tab_positions = PositionsTab(nb, self)
        self.tab_calc = CalcTab(nb, self)
        self.tab_config = ConfigTab(nb, self)
        self.tab_news = NewsTab(nb, self)
        self.tab_index = IndexTab(nb, self)
        self.tab_trend = TrendTab(nb, self)

        nb.add(self.tab_watch.frame, text="① 自选行情监控")
        nb.add(self.tab_positions.frame, text="② 持仓交易记录")
        nb.add(self.tab_calc.frame, text="③ 手续费计算器")
        nb.add(self.tab_config.frame, text="④ 策略&风控配置")
        nb.add(self.tab_news.frame, text="⑤ 新闻舆情中心")
        nb.add(self.tab_index.frame, text="⑥ 大盘指数")
        nb.add(self.tab_trend.frame, text="⑦ 走势分析")

    def _build_statusbar(self):
        self.status_var = tk.StringVar(value="就绪")
        sb = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN,
                       anchor=tk.W, padding=(6, 2))
        sb.pack(side=tk.BOTTOM, fill=tk.X)

    # ---------- 后台线程 ----------
    def _start_threads(self):
        threading.Thread(target=self._watch_loop, daemon=True).start()
        threading.Thread(target=self._news_loop, daemon=True).start()

    def _watch_loop(self):
        while self._running:
            try:
                positions = db.get_positions("holding")
                self.holding_positions = positions
                codes = [str(p["code"]) for p in positions if p["shares"] > 0]
                codes += [str(c) for c in (self.cfg.watchlist or []) if c]
                codes = list(dict.fromkeys(codes))
                rt = {}
                if codes:
                    rt = datasource.get_realtime(codes)
                results = []
                alerts = []
                for p in positions:
                    if p["shares"] <= 0:
                        continue
                    price = rt.get(str(p["code"]), {}).get("price", 0)
                    ev = self.engine.evaluate(p, price, self.cfg, self.fee_cfg)
                    results.append({"pos": p, "price": price, "ev": ev})
                    if price > 0:
                        fire, st = self.engine.should_alert(
                            p["id"], ev["state"], self.cfg.signal_cooldown_min)
                        if fire:
                            alerts.append((p, ev, price))
                index_data = datasource.get_index_realtime()
                self.q.put({"type": "watch", "rt": rt, "results": results,
                            "alerts": alerts, "ts": time.time(),
                            "index": index_data})
            except Exception as e:
                self.q.put({"type": "watch_error", "err": str(e)})
            time.sleep(max(5, int(self.cfg.watch_interval)))

    def _news_loop(self):
        while self._running:
            try:
                positions = db.get_positions("holding")
                codes = [str(p["code"]) for p in positions]
                inserted = db  # avoid unused
                from core import news as news_mod
                ins = news_mod.fetch_all_news(codes)
                db.cleanup_old_news(self.cfg.news_retain_days)
                self.q.put({"type": "news_done", "inserted": ins})
            except Exception as e:
                self.q.put({"type": "news_error", "err": str(e)})
            time.sleep(max(60, int(self.cfg.news_interval)))

    # ---------- 事件泵 ----------
    def _pump(self):
        if not self._running:
            return
        try:
            while True:
                msg = self.q.get_nowait()
                self._handle(msg)
        except queue.Empty:
            pass
        self.root.after(300, self._pump)

    def _handle(self, msg):
        t = msg.get("type")
        if t == "monitor":
            self._set_mon(msg["label"], msg["note"])
            lbl = self.mon_labels.get(msg["label"])
            if lbl:
                lbl.configure(foreground=self._state_color(msg["state"]))
        elif t == "fetch_done":
            cb = msg.get("cb")
            if cb:
                cb(msg["result"])
        elif t == "fetch_fail":
            cb = msg.get("cb")
            if cb:
                cb(None)
        elif t == "watch":
            self.tab_watch.update_watch(msg["rt"], msg["ts"])
            self.tab_positions.update_positions(msg["results"])
            if msg.get("index"):
                self.tab_index.update(msg["index"])
            for p, ev, price in msg.get("alerts", []):
                self.notify(p, ev, price)
            self.status_var.set(f"更新于 {datetime.now().strftime('%H:%M:%S')} · 持仓 {len(msg['results'])} 笔")
        elif t == "news_done":
            self.tab_news.refresh_news()
            self.status_var.set(f"新闻已更新，新增 {msg['inserted']} 条")
        elif t == "news_error":
            self.status_var.set(f"新闻采集失败：{msg['err'][:40]}")
        elif t == "watch_error":
            self.status_var.set(f"行情失败：{msg['err'][:40]}")
        elif t == "refresh":
            self.tab_positions.refresh_local()
            self.tab_news.refresh_news()

    def notify(self, p, ev, price):
        state = ev["state"]
        if state == "take_profit":
            title = "止盈信号"
            color = "#0a7a2f"
            head = f"标的 {p['name'] or p['code']} 已达目标价"
        else:
            title = "止损信号"
            color = "#c00000"
            head = f"标的 {p['name'] or p['code']} 跌破止损价"
        msg = (f"{head}\n\n"
               f"代码：{p['code']}    持仓成本：{p['buy_price']:.3f}   现价：{price:.3f}\n"
               f"保本价：{ev['breakeven']:.3f}   目标价：{ev['target']:.3f}   止损价：{ev['stop']:.3f}\n"
               f"扣费净盈亏：{ev['pnl']:.2f} 元（{ev['pnl_pct']:.2f}%）\n\n"
               f"{DISCLAIMER}")
        if self.cfg.sound_enabled:
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
        self._popup(title, msg, color)

    def _popup(self, title, msg, color):
        w = tk.Toplevel(self.root)
        w.title(title)
        w.geometry("480x260")
        w.attributes("-topmost", True)
        tk.Label(w, text=title, font=("Microsoft YaHei", 14, "bold"),
                 fg=color).pack(pady=(14, 4))
        tk.Label(w, text=msg, justify=tk.LEFT, wraplength=440,
                 font=("Microsoft YaHei", 10)).pack(padx=14, pady=6)
        ttk.Button(w, text="知道了",
                   command=w.destroy).pack(pady=8)

    def flash_status(self, text):
        self.status_var.set(text)

    # ---------- 生命周期 ----------
    def _on_close(self):
        self._running = False
        try:
            from core.config import save_config
            save_config(self.cfg)
        except Exception:
            pass
        try:
            db.backup_db()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()
