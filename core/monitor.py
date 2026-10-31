# -*- coding: utf-8 -*-
"""后台数据拉取监测：防主线程卡死 + 状态(流畅/卡顿/无法获取) + 延迟 + 超时停止 + 间隔重试 + 三次失败原因。"""
import threading
import time

SMOOTH_S = 4.0    # 低于此秒数判为流畅
TIMEOUT_S = 12.0  # 超过此秒数判为超时
MAX_RETRY = 3     # 最多尝试次数
RETRY_WAIT = 3.0  # 失败后间隔重试秒数


class FetchMonitor:
    """在后台线程执行拉取，主线程永不阻塞；通过 app 的队列回传状态给 UI。"""

    def __init__(self, app):
        self.app = app
        self.history = {}  # label -> {state, ms, reason, ok}

    def run(self, label, fn, on_done=None, timeout=TIMEOUT_S,
            max_retries=MAX_RETRY, retry_wait=RETRY_WAIT):
        def worker():
            last_err = ""
            any_timeout = False
            for attempt in range(1, max_retries + 1):
                self._emit(label, "读取中", 0, f"正在拉取信息 · 第{attempt}次")
                t0 = time.time()
                res, err = None, None
                try:
                    res = fn()
                except Exception as e:  # noqa: BLE001
                    err = str(e) or type(e).__name__
                el = time.time() - t0
                ms = int(el * 1000)

                if res is not None:
                    state = "流畅" if el <= SMOOTH_S else ("卡顿" if el <= timeout else "超时")
                    note = f"读取成功，状态：{state}，网络延迟：{ms}ms"
                    self.history[label] = {"state": state, "ms": ms, "reason": "", "ok": True}
                    self._emit(label, state, ms, note)
                    if on_done:
                        self.app.q.put({"type": "fetch_done", "label": label,
                                        "result": res, "cb": on_done})
                    return

                # 失败：记录原因并重试
                if err:
                    last_err = err
                if el >= timeout:
                    any_timeout = True
                    self._emit(label, "无法获取", ms,
                               f"读取超时({ms}ms)，停止本次 · {retry_wait}秒后重试")
                else:
                    self._emit(label, "无法获取", ms,
                               f"未取得数据{('：' + err[:40]) if err else ''} · {retry_wait}秒后重试")
                time.sleep(retry_wait)

            # 已尝试 max_retries 次仍未成功：判定原因
            if last_err:
                reason = "网站信息拦截或数据源异常"
            elif any_timeout:
                reason = "网络延迟"
            else:
                reason = "网站信息拦截或无数据"
            self.history[label] = {"state": "无法获取", "ms": 0, "reason": reason, "ok": False}
            self._emit(label, "无法获取", 0, f"因{reason}无法获取（已尝试{max_retries}次）")
            if on_done:
                self.app.q.put({"type": "fetch_fail", "label": label,
                                "reason": reason, "cb": on_done})

        threading.Thread(target=worker, daemon=True).start()

    def _emit(self, label, state, ms, note):
        self.app.q.put({"type": "monitor", "label": label, "state": state,
                        "ms": ms, "note": note})
