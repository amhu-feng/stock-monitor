# -*- coding: utf-8 -*-
"""新闻采集：宏观财经 / 个股新闻 / 板块。全部公开资讯，本地入库。"""
import akshare as ak
from . import db


def fetch_stock_news(code):
    """个股新闻（东方财富为主，标注来源媒体）。"""
    out = []
    try:
        df = ak.stock_news_em(symbol=str(code))
        if df is not None and not df.empty:
            for _, r in df.iterrows():
                src = str(r.get("文章来源", "")).strip() or "东方财富"
                out.append({
                    "url": str(r.get("新闻链接", "")),
                    "publish_time": str(r.get("发布时间", "")),
                    "title": str(r.get("新闻标题", "")),
                    "summary": str(r.get("新闻内容", ""))[:300],
                    "source": src,
                    "related_code": str(code),
                    "news_type": "stock",
                })
    except Exception:
        pass
    return out


def fetch_macro_news():
    """宏观/政策财经新闻（百度财经快讯）。"""
    out = []
    try:
        df = ak.stock_info_global_em()  # 全球财经快讯
        if df is not None and not df.empty:
            for _, r in df.head(50).iterrows():
                out.append({
                    "url": str(r.get("链接", "") or r.get("url", "") or ""),
                    "publish_time": str(r.get("发布时间", "")),
                    "title": str(r.get("标题", "")),
                    "summary": str(r.get("摘要", ""))[:300],
                    "source": "东方财富快讯",
                    "related_code": "macro",
                    "news_type": "macro",
                })
    except Exception:
        try:
            df = ak.stock_info_global_sina()
            if df is not None and not df.empty:
                for _, r in df.head(50).iterrows():
                    out.append({
                        "url": str(r.get("链接", "") or r.get("url", "") or ""),
                        "publish_time": str(r.get("日期", "")),
                        "title": str(r.get("标题", "")),
                        "summary": str(r.get("内容", ""))[:300],
                        "source": "新浪财经",
                        "related_code": "macro",
                        "news_type": "macro",
                    })
        except Exception:
            pass
    return out


def fetch_all_news(codes):
    """聚合拉取：宏观 + 各持仓/自选个股新闻。返回新入库条数。"""
    items = []
    items.extend(fetch_macro_news())
    for code in codes:
        if not str(code).strip():
            continue
        items.extend(fetch_stock_news(str(code)))
    inserted = 0
    for it in items:
        if not it.get("url") and not it.get("title"):
            continue
        before = len(db.query_news(keyword=it["title"][:20], days=30))
        if before > 0:
            continue
        db.upsert_news(it)
        inserted += 1
    return inserted
