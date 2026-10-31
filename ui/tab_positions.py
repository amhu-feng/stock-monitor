# -*- coding: utf-8 -*-
"""页签② 持仓交易记录：增删改、部分卖出、清仓、流水台账、实时刷新。"""
import math
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from core import db, fees


class PositionsTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self._page = 1
        self._pages = 1
        self._page_size = 30
        self._all_rows = []
        self._build()

    def _build(self):
        top = ttk.Frame(self.frame)
        top.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)
        for txt, cmd in [("新增持仓", self.add), ("编辑所选", self.edit),
                         ("删除所选", self.delete), ("部分卖出", self.sell_part),
                         ("全部清仓", self.sell_all), ("查看流水", self.show_trades),
                         ("刷新", self.refresh_local)]:
            ttk.Button(top, text=txt, command=cmd).pack(side=tk.LEFT, padx=2)
        ttk.Label(top, text="显示字号").pack(side=tk.LEFT, padx=(18, 2))
        self.font_size_var = tk.StringVar(value=str(self.app.cfg.font_size))
        fcb = ttk.Combobox(top, textvariable=self.font_size_var, width=4, state="readonly",
                           values=[str(i) for i in range(9, 19)])
        fcb.pack(side=tk.LEFT)
        fcb.bind("<<ComboboxSelected>>", lambda _e: self._apply_font())

        cols = ("code", "name", "btime", "buy", "shares", "cost", "price",
                "be", "target", "stop", "pnl", "pct", "state")
        heads = {"code": "代码", "name": "名称", "btime": "买入时间", "buy": "买入价",
                 "shares": "股数", "cost": "买入成本", "price": "现价", "be": "保本价",
                 "target": "目标价", "stop": "止损价", "pnl": "净盈亏(元)", "pct": "净盈亏%",
                 "state": "状态"}
        widths = {"code": 80, "name": 90, "btime": 120, "buy": 75, "shares": 70,
                  "cost": 90, "price": 80, "be": 85, "target": 85, "stop": 80,
                  "pnl": 95, "pct": 80, "state": 95}
        wrap = ttk.Frame(self.frame)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=4, pady=2)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=16)
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor=tk.CENTER)
        ys = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.tag_configure("profit", foreground="#0a7a2f")
        self.tree.tag_configure("loss", foreground="#c00000")
        self.tree.tag_configure("gray", foreground="#999999")
        self.tree.tag_configure("closed", foreground="#bbbbbb")

        # 分页栏
        pg = ttk.Frame(wrap)
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

    # ---------- 刷新 ----------
    def refresh_local(self):
        rows = db.get_positions("holding")
        rt = {}
        if rows:
            from core import datasource
            rt = datasource.get_realtime([str(p["code"]) for p in rows])
        results = []
        for p in rows:
            price = rt.get(str(p["code"]), {}).get("price", 0)
            ev = self.app.engine.evaluate(p, price, self.app.cfg, self.app.fee_cfg)
            results.append({"pos": p, "price": price, "ev": ev})
        self.update_positions(results)

    def update_positions(self, results):
        self._all_rows = []
        for item in results:
            p = item["pos"]
            ev = item["ev"]
            price = item["price"]
            from core import fees as _f
            b = _f.buy_cost(p["buy_price"], p["shares"], self.app.fee_cfg)
            vals = (p["code"], p["name"] or "", (p["buy_time"] or "")[:16],
                    f"{p['buy_price']:.3f}", p["shares"], f"{b['total']:.2f}",
                    f"{price:.3f}" if price > 0 else "-",
                    f"{ev['breakeven']:.3f}", f"{ev['target']:.3f}", f"{ev['stop']:.3f}",
                    f"{ev['pnl']:.2f}", f"{ev['pnl_pct']:.2f}",
                    self._state_text(ev["state"]))
            tag = "profit" if ev["pnl"] > 0 else ("loss" if ev["pnl"] < 0 else "gray")
            self._all_rows.append((vals, tag, p["id"]))
        # 已清仓记录
        for p in db.get_positions("closed"):
            from core import fees as _f
            b = _f.buy_cost(p["buy_price"], p["shares"] or 0, self.app.fee_cfg)
            vals = (p["code"], p["name"] or "", (p["buy_time"] or "")[:16],
                    f"{p['buy_price']:.3f}", 0, f"{b['total']:.2f}", "-", "-", "-", "-",
                    "-", "-", "已清仓")
            self._all_rows.append((vals, "closed", None))
        self._pages = max(1, math.ceil(len(self._all_rows) / self._page_size))
        if self._page > self._pages:
            self._page = self._pages
        self._render_page()

    def _render_page(self):
        self.tree.delete(*self.tree.get_children())
        self._row_map = {}
        start = (self._page - 1) * self._page_size
        for vals, tag, pid in self._all_rows[start:start + self._page_size]:
            iid = self.tree.insert("", tk.END, values=vals, tags=(tag,))
            if pid is not None:
                self._row_map[iid] = pid
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

    @staticmethod
    def _state_text(s):
        return {"holding": "持有中", "take_profit": "✓达标可卖", "stop_loss": "✗跌破止损",
                "breakeven": "·过保本线", "no_data": "无行情"}.get(s, s)

    def _sel_pid(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一条持仓", parent=self.frame)
            return None
        return self._row_map.get(sel[0])

    # ---------- 操作 ----------
    def add(self):
        data = self._form()
        if data is None:
            return
        pid = db.add_position(data["code"], data["name"], data["buy_price"],
                              data["shares"], comm_rate=data["comm_rate"],
                              min_profit_pct=data["min_profit_pct"],
                              stop_loss=data["stop_loss"], note=data["note"])
        self.app.engine.reset()
        self.refresh_local()
        self.app.flash_status(f"已新增持仓 {data['code']}")

    def edit(self):
        pid = self._sel_pid()
        if pid is None:
            return
        rows = db.get_all_positions()
        pos = next((r for r in rows if r["id"] == pid), None)
        if pos is None:
            return
        data = self._form(pos)
        if data is None:
            return
        db.update_position(pid,
                           code=data["code"], name=data["name"],
                           buy_price=data["buy_price"], shares=data["shares"],
                           comm_rate=data["comm_rate"], min_profit_pct=data["min_profit_pct"],
                           stop_loss=data["stop_loss"], note=data["note"])
        self.app.engine.reset()
        self.refresh_local()
        self.app.flash_status("已更新持仓")

    def delete(self):
        pid = self._sel_pid()
        if pid is None:
            return
        if messagebox.askyesno("确认", "删除该持仓及其流水？（不会影响你的真实账户）", parent=self.frame):
            db.delete_position(pid)
            self.refresh_local()

    def sell_part(self):
        pid = self._sel_pid()
        if pid is None:
            return
        rows = db.get_all_positions()
        pos = next((r for r in rows if r["id"] == pid), None)
        if pos is None or pos["shares"] <= 0:
            return
        s = simpledialog.askinteger("部分卖出", f"卖出股数（当前持有 {pos['shares']} 股）：",
                                    parent=self.frame, minvalue=1, maxvalue=pos["shares"])
        if s is None:
            return
        price = simpledialog.askfloat("卖出价", "成交价（可留空用现价）", parent=self.frame,
                                      initialvalue=0)
        price = price or self._latest_price(pos["code"])
        self._do_sell(pos, "sell_part", price, s)

    def sell_all(self):
        pid = self._sel_pid()
        if pid is None:
            return
        rows = db.get_all_positions()
        pos = next((r for r in rows if r["id"] == pid), None)
        if pos is None or pos["shares"] <= 0:
            messagebox.showinfo("提示", "该持仓无可卖股数", parent=self.frame)
            return
        if not messagebox.askyesno("确认", f"清仓 {pos['name'] or pos['code']} 全部 {pos['shares']} 股？",
                                   parent=self.frame):
            return
        price = self._latest_price(pos["code"])
        self._do_sell(pos, "sell_all", price, pos["shares"])

    def _latest_price(self, code):
        from core import datasource
        try:
            rt = datasource.get_realtime([code])
            return rt.get(str(code), {}).get("price", 0)
        except Exception:
            return 0

    def _do_sell(self, pos, action, price, shares):
        from core import fees as _f
        eff = self._eff_fee(pos)
        sf = _f.sell_fee(price, shares, eff)
        b = _f.buy_cost(pos["buy_price"], pos["shares"], eff)
        # 已实现盈亏（按总成本摊到本次卖出）
        ratio = shares / pos["shares"] if pos["shares"] else 1
        net = sf["amount"] - b["total"] * ratio - sf["total"]
        db.record_sell(pos["id"], pos["code"], action, price, shares,
                       sf["total"], net, b["total"], sf["amount"])
        self.app.engine.reset()
        self.refresh_local()
        self.app.flash_status(f"已卖出 {shares} 股，实现净盈亏 {net:.2f} 元")

    def _eff_fee(self, pos):
        c = self.app.fee_cfg
        comm = pos.get("comm_rate", -1)
        if comm and comm > 0:
            return fees.FeeConfig(comm_rate=comm, min_comm=c.min_comm,
                                  transfer_rate=c.transfer_rate, stamp_rate=c.stamp_rate,
                                  use_min_comm=c.use_min_comm)
        return c

    def show_trades(self):
        pid = self._sel_pid()
        rows = db.get_trades(pid) if pid else db.get_trades()
        w = tk.Toplevel(self.frame)
        w.title(f"交易流水（{len(rows)} 条）")
        w.geometry("760x420")
        cols = ("id", "action", "price", "shares", "amount", "fee", "pnl", "time")
        heads = {"id": "ID", "action": "操作", "price": "价格", "shares": "股数",
                 "amount": "金额", "fee": "手续费", "pnl": "净盈亏", "time": "时间"}
        t = ttk.Treeview(w, columns=cols, show="headings")
        for c in cols:
            t.heading(c, text=heads[c])
            t.column(c, width=80, anchor=tk.CENTER)
        for r in rows:
            act = {"buy": "买入", "sell_part": "部分卖出", "sell_all": "清仓"}.get(r["action"], r["action"])
            t.insert("", tk.END, values=(r["id"], act, f"{r['price']:.3f}", r["shares"],
                                         f"{r['amount']:.2f}", f"{r['fee']:.2f}",
                                         f"{r['net_pnl']:.2f}", r["trade_time"]))
        t.pack(fill=tk.BOTH, expand=True)

    # ---------- 表单 ----------
    def _form(self, pos=None):
        w = tk.Toplevel(self.frame)
        w.title("编辑持仓" if pos else "新增持仓")
        w.geometry("420x420")
        w.transient(self.frame)
        w.grab_set()
        var = {}
        fields = [
            ("code", "股票代码*", pos["code"] if pos else ""),
            ("name", "股票名称", pos["name"] if pos else ""),
            ("buy_price", "买入价*", pos["buy_price"] if pos else ""),
            ("shares", "股数*", pos["shares"] if pos else ""),
            ("comm_rate", "佣金率(留空用全局)", pos["comm_rate"] if pos and pos["comm_rate"] > 0 else ""),
            ("min_profit_pct", "最小盈利阈值(留空用全局)", pos["min_profit_pct"] if pos and pos["min_profit_pct"] > 0 else ""),
            ("stop_loss", "止损价(留空用默认)", pos["stop_loss"] if pos and pos["stop_loss"] > 0 else ""),
            ("note", "备注", pos["note"] if pos else ""),
        ]
        for i, (k, label, val) in enumerate(fields):
            ttk.Label(w, text=label).grid(row=i, column=0, sticky="w", padx=10, pady=5)
            var[k] = tk.StringVar(value=str(val))
            ttk.Entry(w, textvariable=var[k], width=28).grid(row=i, column=1, padx=10, pady=5)
        result = {}

        def ok():
            try:
                result["code"] = var["code"].get().strip()
                result["name"] = var["name"].get().strip()
                result["buy_price"] = float(var["buy_price"].get())
                result["shares"] = int(var["shares"].get())
                if result["shares"] <= 0:
                    raise ValueError
                result["comm_rate"] = float(var["comm_rate"].get()) if var["comm_rate"].get() else -1
                result["min_profit_pct"] = float(var["min_profit_pct"].get()) if var["min_profit_pct"].get() else -1
                result["stop_loss"] = float(var["stop_loss"].get()) if var["stop_loss"].get() else -1
                result["note"] = var["note"].get().strip()
            except Exception:
                messagebox.showerror("输入错误", "请检查必填项：代码、买入价、股数（股数为正整数）", parent=w)
                return
            w.destroy()

        ttk.Button(w, text="保存", command=ok).grid(row=len(fields), column=0, columnspan=2, pady=14)
        ttk.Label(w, text="带*为必填；佣金率、盈利阈值、止损可留空用全局默认。",
                  foreground="#888").grid(row=len(fields)+1, column=0, columnspan=2, padx=10)
        w.wait_window()
        return result or None
