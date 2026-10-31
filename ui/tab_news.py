# -*- coding: utf-8 -*-
"""页签⑤ 新闻舆情中心：宏观/行业/个股新闻，筛选、检索、批注、导出。"""
import math
import os
import urllib.parse
import webbrowser
from datetime import datetime

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from core import db


class NewsTab:
    def __init__(self, parent, app):
        self.app = app
        self.frame = ttk.Frame(parent)
        self._page = 1
        self._page_size = 30
        self._pages = 1
        self._total = 0
        self._build()

    def _build(self):
        # 筛选栏
        bar = ttk.Frame(self.frame)
        bar.pack(side=tk.TOP, fill=tk.X, padx=6, pady=4)

        ttk.Label(bar, text="类型").pack(side=tk.LEFT)
        self.var_type = tk.StringVar(value="all")
        cb = ttk.Combobox(bar, textvariable=self.var_type, state="readonly", width=8,
                          values=["all", "macro", "industry", "stock"])
        cb.pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(bar, text="代码").pack(side=tk.LEFT)
        self.var_code = tk.StringVar()
        ttk.Entry(bar, textvariable=self.var_code, width=10).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(bar, text="关键词").pack(side=tk.LEFT)
        self.var_kw = tk.StringVar()
        ttk.Entry(bar, textvariable=self.var_kw, width=16).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Button(bar, text="查询", command=self.refresh_news).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="立即拉取", command=self.fetch_now).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="标记已读", command=self.mark_read).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="批注", command=self.annotate).pack(side=tk.LEFT, padx=2)
        ttk.Button(bar, text="导出", command=self.export).pack(side=tk.LEFT, padx=2)
        ttk.Label(bar, text="显示字号").pack(side=tk.LEFT, padx=(18, 2))
        self.font_size_var = tk.StringVar(value=str(self.app.cfg.font_size))
        fcb = ttk.Combobox(bar, textvariable=self.font_size_var, width=4, state="readonly",
                           values=[str(i) for i in range(9, 19)])
        fcb.pack(side=tk.LEFT)
        fcb.bind("<<ComboboxSelected>>",
                 lambda _e: self.app.set_font(self.font_size_var.get()))

        wrap = ttk.Frame(self.frame)
        wrap.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=6, pady=2)
        cols = ("time", "type", "sent", "title", "source", "read")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", height=18)
        heads = {"time": "时间", "type": "类型", "sent": "情绪", "title": "标题",
                 "source": "来源", "read": "已读"}
        widths = {"time": 140, "type": 60, "sent": 60, "title": 520, "source": 90, "read": 50}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor=tk.W if c in ("title",) else tk.CENTER)
        ys = ttk.Scrollbar(wrap, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<Double-1>", self._open)
        self.tree.tag_configure("unread", font=("Microsoft YaHei", 9, "bold"))
        self.tree.tag_configure("keynews", foreground="#b30000", font=("Microsoft YaHei", 9, "bold"))
        self.tree.tag_configure("lihao", foreground="#0a7a2f")
        self.tree.tag_configure("likong", foreground="#c00000")
        self.tree.tag_configure("zhongxing", foreground="#555555")
        self.tree.tag_configure("rel_child", foreground="#0a7a2f")
        self._row_map = {}

        # 分页栏：分批显示，一页最多 N 条，防止信息量过大卡死
        pg = ttk.Frame(self.frame)
        pg.pack(side=tk.TOP, fill=tk.X, padx=6, pady=2)
        ttk.Button(pg, text="◀ 上一页", command=self._prev_page).pack(side=tk.LEFT)
        self.page_var = tk.StringVar(value="第 1 / 1 页 · 共 0 条")
        ttk.Label(pg, textvariable=self.page_var).pack(side=tk.LEFT, padx=10)
        ttk.Button(pg, text="下一页 ▶", command=self._next_page).pack(side=tk.LEFT)
        ttk.Label(pg, text="每页").pack(side=tk.LEFT, padx=(16, 2))
        self.page_size_var = tk.StringVar(value="30")
        cb = ttk.Combobox(pg, textvariable=self.page_size_var, width=5, state="readonly",
                          values=["30", "60", "100"])
        cb.pack(side=tk.LEFT)
        cb.bind("<<ComboboxSelected>>", lambda _e: self._set_page_size())
        ttk.Label(pg, text="条（信息分批编译显示）").pack(side=tk.LEFT, padx=(2, 0))

        self.refresh_news()

    def _prev_page(self):
        if self._page > 1:
            self._page -= 1
            self.refresh_news()

    def _next_page(self):
        if self._page < self._pages:
            self._page += 1
            self.refresh_news()

    def _set_page_size(self):
        try:
            self._page_size = int(self.page_size_var.get())
        except Exception:
            self._page_size = 30
        self._page = 1
        self.refresh_news()

    def fetch_now(self):
        from core import news as news_mod
        codes = [str(p["code"]) for p in db.get_positions("holding")]
        self.app.flash_status("正在拉取新闻…")

        def _do():
            ins = news_mod.fetch_all_news(codes)
            db.cleanup_old_news(self.app.cfg.news_retain_days)
            return ins

        def _done(ins):
            self.refresh_news()
            self.app.flash_status(f"新闻拉取完成，新增 {ins or 0} 条" if ins else "新闻拉取完成")

        self.app.run_task("新闻", _do, _done)

    KEY_WORDS = ["规划", "政策", "国常会", "国务院", "发改委", "央行", "证监会",
                 "发布", "重磅", "意见", "通知", "中央", "政治局", "审议", "部署"]

    def _is_key(self, source, title):
        s = (source or "") + (title or "")
        if "央视" in s or "cctv" in s.lower():
            return True
        return any(w in s for w in self.KEY_WORDS)

    def _match_positions(self, title, summary):
        """返回命中该新闻的持仓列表（按名称/代码匹配）。"""
        matched = []
        text = (title or "") + (summary or "")
        try:
            positions = db.get_positions("holding")
        except Exception:
            return matched
        for p in positions:
            code = str(p["code"])
            name = p.get("name") or ""
            if (name and name in text) or (code and code in text):
                matched.append(p)
        return matched

    def refresh_news(self):
        nt = self.var_type.get() if hasattr(self, "var_type") else "all"
        code = self.var_code.get().strip() if hasattr(self, "var_code") else ""
        kw = self.var_kw.get().strip() if hasattr(self, "var_kw") else ""
        rows, total = db.query_news(news_type=None if nt == "all" else nt,
                                    related_code=code or None, keyword=kw or None,
                                    days=self.app.cfg.news_retain_days,
                                    page=self._page, page_size=self._page_size)
        self._total = total
        self._pages = max(1, math.ceil(total / self._page_size))
        if self._page > self._pages:
            self._page = self._pages
            rows, total = db.query_news(news_type=None if nt == "all" else nt,
                                        related_code=code or None, keyword=kw or None,
                                        days=self.app.cfg.news_retain_days,
                                        page=self._page, page_size=self._page_size)
            self._total = total
        if hasattr(self, "page_var"):
            self.page_var.set(f"第 {self._page} / {self._pages} 页 · 共 {total} 条")
        self.tree.delete(*self.tree.get_children())
        self._row_map = {}
        for r in rows:
            sent = r["sentiment_tag"] or "待标注"
            tags = ["unread"] if not r["read_flag"] else []
            sent_tag = "lihao" if sent == "利好" else ("likong" if sent == "利空" else "zhongxing")
            tags.append(sent_tag)
            title = r["title"]
            is_key = self._is_key(r.get("source", ""), title)
            if is_key:
                title = "【重点】" + title
                tags.append("keynews")
            typ = {"macro": "宏观", "industry": "行业", "stock": "个股"}.get(r["news_type"], r["news_type"])
            iid = self.tree.insert("", tk.END, values=(
                (r["publish_time"] or "")[:16], typ, sent, title,
                r["source"], "已读" if r["read_flag"] else "未读"),
                tags=tuple(tags))
            self._row_map[iid] = r["id"]
            # 关联持仓子项（绿色）
            for p in self._match_positions(r["title"], r["summary"]):
                child_text = (f"↳ 关联持仓 {p['code']} {p['name'] or ''} ｜ "
                              f"当前购入价 {p['buy_price']:.2f} 元")
                child = self.tree.insert(iid, tk.END, values=("", "", "", child_text, "", ""),
                                         tags=("rel_child",))
                self._row_map[child] = r["id"]

    def mark_read(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请选择新闻", parent=self.frame)
            return
        for iid in sel:
            nid = self._row_map.get(iid)
            if nid:
                db.update_news_meta(nid, read_flag=1)
        self.refresh_news()

    def annotate(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请选择新闻", parent=self.frame)
            return
        nid = self._row_map.get(sel[0])
        if not nid:
            return
        from tkinter import simpledialog
        note = simpledialog.askstring("批注", "写一句笔记（如：政策利好，明日观察）",
                                      parent=self.frame)
        if note is not None:
            db.update_news_meta(nid, note=note, user_mark="已标注")
            self.refresh_news()

    def _open(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        nid = self._row_map.get(sel[0])
        rows = db.query_news(days=self.app.cfg.news_retain_days)
        r = next((x for x in rows if x["id"] == nid), None)
        if r:
            url = (r.get("news_url") or "").strip()
            if url:
                webbrowser.open(url)
            elif r.get("title"):
                # 无原文链接：用浏览器搜索标题查详情
                q = urllib.parse.quote(r["title"])
                webbrowser.open(f"https://www.bing.com/search?q={q}")
            db.update_news_meta(nid, read_flag=1)
        self.refresh_news()

    def export(self):
        path = filedialog.asksaveasfilename(parent=self.frame, defaultextension=".md",
                                            filetypes=[("Markdown", "*.md"), ("CSV", "*.csv")])
        if not path:
            return
        nt = self.var_type.get()
        rows = db.query_news(news_type=None if nt == "all" else nt,
                             related_code=self.var_code.get().strip() or None,
                             days=self.app.cfg.news_retain_days)
        if path.lower().endswith(".csv"):
            import csv
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["时间", "类型", "情绪", "标题", "来源", "链接", "批注"])
                for r in rows:
                    w.writerow([r["publish_time"], r["news_type"], r["sentiment_tag"],
                                r["title"], r["source"], r["news_url"], r["note"]])
        else:
            lines = ["# 新闻舆情导出", f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
            for r in rows:
                lines.append(f"## {r['title']}")
                lines.append(f"- 时间：{r['publish_time']}   类型：{r['news_type']}   情绪：{r['sentiment_tag'] or '待标注'}")
                lines.append(f"- 来源：{r['source']}")
                if r["summary"]:
                    lines.append(f"- 摘要：{r['summary'][:200]}")
                if r["note"]:
                    lines.append(f"- 我的批注：{r['note']}")
                lines.append("")
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        self.app.flash_status(f"已导出 {len(rows)} 条新闻")
