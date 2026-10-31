# -*- coding: utf-8 -*-
"""数据源：akshare 实时行情 / K线。东方财富主源 + 新浪备源自动降级 + 缓存兜底。
避免单源被限流导致断监控。"""
import time
import threading

import akshare as ak

_lock = threading.Lock()
_cache = {}        # code -> {"price","pct","name","ts"}
_sina_snap = {}    # {"data":{code:...},"ts":...}
KLINE_CACHE = {}

PUSH2_LIMIT_MSG = "Push2RateLimitError"


def _prefix(code):
    code = str(code)
    if code.startswith(("6", "9", "5")):
        return "sh" + code
    if code.startswith(("0", "3")):
        return "sz" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    return "sh" + code


def _strip(code):
    s = str(code)
    return s[2:] if s[:2] in ("sh", "sz", "bj") else s


# ---------- 东方财富主源 ----------
def _em_bid_ask(code):
    df = ak.stock_bid_ask_em(symbol=str(code))
    d = dict(zip(df["item"].astype(str), df["value"]))
    price = float(d.get("最新", 0) or 0)
    name = str(d.get("名称", "") or "")
    pct = float(d.get("涨幅", 0) or 0)
    return {"price": price, "name": name, "pct": pct}


# ---------- 新浪备源 ----------
def _sina_snapshot(force=False):
    """新浪全市场快照（带10秒缓存），降级用。"""
    global _sina_snap
    with _lock:
        if not force and _sina_snap and time.time() - _sina_snap.get("ts", 0) < 10:
            return _sina_snap["data"]
    df = ak.stock_zh_a_spot()
    data = {}
    for _, r in df.iterrows():
        code = _strip(r["代码"])
        data[code] = {
            "price": float(r.get("最新价", 0) or 0),
            "name": str(r.get("名称", "") or ""),
            "pct": float(r.get("涨跌幅", 0) or 0),
        }
    with _lock:
        _sina_snap = {"data": data, "ts": time.time()}
    return data


def _sina_daily_kline(code, days):
    df = ak.stock_zh_a_daily(symbol=_prefix(code), adjust="qfq")
    if df is None or df.empty:
        return None
    df = df.tail(days)
    out = []
    for _, r in df.iterrows():
        out.append({"date": str(r["date"])[:10], "open": float(r["open"]),
                    "high": float(r["high"]), "low": float(r["low"]),
                    "close": float(r["close"]), "volume": float(r.get("volume", 0) or 0)})
    return out


# ---------- 对外接口 ----------
def get_realtime(codes):
    """返回 {code:{"price","name","pct","ts"}}，东方财富→新浪→缓存兜底。"""
    result = {}
    for code in codes:
        code = str(code)
        # 优先取 5 秒内缓存
        with _lock:
            rec = _cache.get(code)
            if rec and time.time() - rec["ts"] < 5:
                result[code] = dict(rec)
                continue
        # 1) 东方财富单只
        try:
            em = _em_bid_ask(code)
            if em and em.get("price", 0) > 0:
                em["ts"] = time.time()
                with _lock:
                    _cache[code] = dict(em)
                result[code] = dict(em)
                continue
        except Exception:
            pass
        # 2) 新浪全市场快照兜底
        try:
            snap = _sina_snapshot()
            if code in snap and snap[code].get("price", 0) > 0:
                d = dict(snap[code]); d["ts"] = time.time()
                with _lock:
                    _cache[code] = dict(d)
                result[code] = dict(d)
                continue
        except Exception:
            pass
        # 3) 缓存旧值 / 空值
        with _lock:
            result[code] = dict(_cache[code]) if code in _cache else \
                {"price": 0, "name": code, "pct": 0, "ts": time.time()}
    return result


def get_kline(code, days=60):
    """日K（前复权）。东财主源→新浪备源。失败返回 None。"""
    code = str(code)
    try:
        import datetime as dt
        end = dt.date.today().strftime("%Y%m%d")
        start = (dt.date.today() - dt.timedelta(days=int(days * 1.8))).strftime("%Y%m%d")
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start,
                                end_date=end, adjust="qfq")
        if df is not None and not df.empty:
            df = df.tail(days)
            out = []
            for _, r in df.iterrows():
                out.append({"date": str(r["日期"]), "open": float(r["开盘"]),
                            "high": float(r["最高"]), "low": float(r["最低"]),
                            "close": float(r["收盘"]), "volume": float(r["成交量"])})
            return out
    except Exception:
        pass
    try:
        return _sina_daily_kline(code, days)
    except Exception:
        return None


def search_code(keyword):
    """按代码/名称搜索股票（用新浪全市场，避免东财限流）。"""
    try:
        df = ak.stock_zh_a_spot()
        df = df[df["代码"].astype(str).str.contains(keyword) |
                df["名称"].astype(str).str.contains(keyword)]
        return [{"code": _strip(r["代码"]), "name": str(r["名称"])}
                for _, r in df.head(20).iterrows()]
    except Exception:
        return []


# ---------- 大盘指数 ----------
MAIN_INDEXES = [
    ("sh000001", "上证指数"), ("sz399001", "深证成指"), ("sz399006", "创业板指"),
    ("sh000300", "沪深300"), ("sh000905", "中证500"), ("sh000688", "科创50"),
]


def get_index_realtime():
    """主要大盘指数实时（新浪），返回 {prefixed_code: {...}}。"""
    try:
        df = ak.stock_zh_index_spot_sina()
        out = {}
        for pref, default_name in MAIN_INDEXES:
            row = df[df["代码"].astype(str) == pref]
            if row.empty:
                continue
            r = row.iloc[0]
            out[pref] = {
                "code": pref, "name": str(r.get("名称", default_name)),
                "open": float(r.get("今开", 0) or 0),
                "pre_close": float(r.get("昨收", 0) or 0),
                "price": float(r.get("最新价", 0) or 0),
                "pct": float(r.get("涨跌幅", 0) or 0),
                "high": float(r.get("最高", 0) or 0),
                "low": float(r.get("最低", 0) or 0),
                "time": str(r.get("时间", ""))[:8],
            }
        return out
    except Exception:
        return {}


def get_index_kline(code, days=120):
    """指数历史日K（新浪），返回 [{date,open,high,low,close,volume}]。"""
    code = str(code)
    try:
        df = ak.stock_zh_index_daily(symbol=code)
        if df is None or df.empty:
            return None
        df = df.tail(days)
        out = []
        for _, r in df.iterrows():
            out.append({"date": str(r["date"])[:10], "open": float(r["open"]),
                        "high": float(r["high"]), "low": float(r["low"]),
                        "close": float(r["close"]),
                        "volume": float(r.get("volume", 0) or 0)})
        return out
    except Exception:
        return None
