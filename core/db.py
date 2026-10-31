# -*- coding: utf-8 -*-
"""SQLite 数据层：持仓、交易流水、新闻。"""
import os
import shutil
import sqlite3
import time
from datetime import datetime
from .paths import DATA_DIR

DB_FILE = os.path.join(DATA_DIR, "stock.db")


def _conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    c = _conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        name TEXT DEFAULT '',
        buy_time TEXT,
        buy_price REAL NOT NULL,
        shares INTEGER NOT NULL,
        comm_rate REAL DEFAULT -1,      -- -1 表示用全局
        min_profit_pct REAL DEFAULT -1, -- -1 表示用全局
        stop_loss REAL DEFAULT -1,      -- -1 表示按默认比例
        note TEXT DEFAULT '',
        status TEXT DEFAULT 'holding',  -- holding 持有中 / closed 已清仓
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position_id INTEGER,
        code TEXT,
        action TEXT,           -- buy / sell_part / sell_all
        price REAL,
        shares INTEGER,
        amount REAL,
        fee REAL DEFAULT 0,
        net_pnl REAL DEFAULT 0,
        trade_time TEXT
    );
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        news_url TEXT UNIQUE,
        publish_time TEXT,
        fetch_time TEXT,
        title TEXT,
        summary TEXT DEFAULT '',
        source TEXT DEFAULT '',
        related_code TEXT DEFAULT '',
        industry_tag TEXT DEFAULT '',
        news_type TEXT DEFAULT 'stock', -- macro / industry / stock
        sentiment_tag TEXT DEFAULT '',  -- 利好/中性/利空
        sentiment_note TEXT DEFAULT '',
        read_flag INTEGER DEFAULT 0,
        user_mark TEXT DEFAULT '',
        note TEXT DEFAULT ''
    );
    """)
    c.commit()
    c.close()


# ---------- 持仓 ----------
def add_position(code, name, buy_price, shares, buy_time=None, comm_rate=-1,
                 min_profit_pct=-1, stop_loss=-1, note=""):
    c = _conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = c.execute(
        "INSERT INTO positions(code,name,buy_time,buy_price,shares,comm_rate,min_profit_pct,stop_loss,note,status,created_at)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (code, name, buy_time or now, buy_price, shares, comm_rate,
         min_profit_pct, stop_loss, note, "holding", now))
    pid = cur.lastrowid
    c.execute("INSERT INTO trades(position_id,code,action,price,shares,amount,fee,net_pnl,trade_time) VALUES(?,?,?,?,?,?,0,0,?)",
              (pid, code, "buy", buy_price, shares, buy_price * shares, now))
    c.commit()
    c.close()
    return pid


def update_position(pid, **kw):
    c = _conn()
    fields = {k: v for k, v in kw.items() if v is not None}
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields)
        c.execute(f"UPDATE positions SET {sets} WHERE id=?", (*fields.values(), pid))
        c.commit()
    c.close()


def delete_position(pid):
    c = _conn()
    c.execute("DELETE FROM positions WHERE id=?", (pid,))
    c.execute("DELETE FROM trades WHERE position_id=?", (pid,))
    c.commit()
    c.close()


def get_positions(status="holding"):
    c = _conn()
    rows = c.execute("SELECT * FROM positions WHERE status=? ORDER BY id DESC", (status,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_all_positions():
    c = _conn()
    rows = c.execute("SELECT * FROM positions ORDER BY id DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


# ---------- 交易流水 ----------
def record_sell(position_id, code, action, price, shares, fee, net_pnl, buy_total, sell_amount):
    """记录卖出流水，并更新持仓剩余股数与状态。"""
    c = _conn()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO trades(position_id,code,action,price,shares,amount,fee,net_pnl,trade_time)"
              " VALUES(?,?,?,?,?,?,?,?,?)",
              (position_id, code, action, price, shares, sell_amount, fee, net_pnl, now))
    row = c.execute("SELECT shares,status FROM positions WHERE id=?", (position_id,)).fetchone()
    if row:
        remain = row["shares"] - shares
        if remain <= 0:
            c.execute("UPDATE positions SET shares=0, status='closed' WHERE id=?", (position_id,))
        else:
            c.execute("UPDATE positions SET shares=? WHERE id=?", (remain, position_id))
    c.commit()
    c.close()


def get_trades(position_id=None):
    c = _conn()
    if position_id:
        rows = c.execute("SELECT * FROM trades WHERE position_id=? ORDER BY id", (position_id,)).fetchall()
    else:
        rows = c.execute("SELECT * FROM trades ORDER BY id DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


# ---------- 新闻 ----------
def upsert_news(item):
    """按 news_url 去重插入。item: dict"""
    c = _conn()
    try:
        c.execute("""INSERT OR IGNORE INTO news
            (news_url,publish_time,fetch_time,title,summary,source,related_code,industry_tag,news_type)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (item.get("url",""), item.get("publish_time",""), datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             item.get("title",""), item.get("summary",""), item.get("source",""),
             item.get("related_code",""), item.get("industry_tag",""), item.get("news_type","stock")))
        c.commit()
    finally:
        c.close()


def query_news(news_type=None, related_code=None, sentiment=None, keyword=None, days=None,
               page=None, page_size=30):
    """查询新闻。page=None 返回全量 list（兼容旧调用）；page 为整数时返回 (rows, total)，分批取当前页。"""
    c = _conn()
    where = "1=1"
    args = []
    if news_type:
        where += " AND news_type=?"
        args.append(news_type)
    if related_code:
        where += " AND (related_code LIKE ? OR title LIKE ?)"
        args.append(f"%{related_code}%")
        args.append(f"%{related_code}%")
    if sentiment:
        where += " AND sentiment_tag=?"
        args.append(sentiment)
    if keyword:
        where += " AND (title LIKE ? OR summary LIKE ?)"
        args.append(f"%{keyword}%")
        args.append(f"%{keyword}%")
    if days:
        where += " AND fetch_time >= datetime('now', ?)"
        args.append(f"-{days} days")
    if page is None:
        rows = c.execute(f"SELECT * FROM news WHERE {where} ORDER BY publish_time DESC LIMIT 500",
                         args).fetchall()
        c.close()
        return [dict(r) for r in rows]
    total = c.execute(f"SELECT COUNT(*) FROM news WHERE {where}", args).fetchone()[0]
    offset = (int(page) - 1) * int(page_size)
    rows = c.execute(f"SELECT * FROM news WHERE {where} ORDER BY publish_time DESC LIMIT ? OFFSET ?",
                     args + [int(page_size), offset]).fetchall()
    c.close()
    return [dict(r) for r in rows], total


def update_news_meta(nid, **kw):
    c = _conn()
    fields = {k: v for k, v in kw.items() if v is not None}
    if fields:
        sets = ", ".join(f"{k}=?" for k in fields)
        c.execute(f"UPDATE news SET {sets} WHERE id=?", (*fields.values(), nid))
        c.commit()
    c.close()


def get_recent_news(codes, days=7):
    """供 AI/预案 使用：拉取指定标的相关新闻。"""
    c = _conn()
    rows = []
    for code in codes:
        r = c.execute(
            "SELECT * FROM news WHERE (related_code=? OR title LIKE ?) AND fetch_time >= datetime('now',?) "
            "ORDER BY publish_time DESC LIMIT 20",
            (code, f"%{code}%", f"-{days} days")).fetchall()
        rows.extend([dict(x) for x in r])
    c.close()
    return rows


def cleanup_old_news(days):
    c = _conn()
    c.execute("DELETE FROM news WHERE fetch_time < datetime('now', ?)", (f"-{days} days",))
    c.commit()
    c.close()


def backup_db():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        bak = os.path.join(DATA_DIR, f"backup_{datetime.now().strftime('%Y%m%d')}.db")
        shutil.copy2(DB_FILE, bak)
    except Exception:
        pass
