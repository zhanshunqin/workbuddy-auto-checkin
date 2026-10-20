#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把签到结果追加/更新为一条日历日程，生成 checkin-calendar.ics 供 iPhone 订阅。

设计：
  - 每天一条「全天事件」，标题含签到状态。
  - 同一天重复运行则覆盖当天那条（用 UID 固定为当天日期）。
  - 只保留最近 30 天的事件，避免文件无限膨胀。
  - ICS 由 WorkBuddy 客户端域名的签到接口结果驱动。

用法：
  cat checkin_result.json | python ics.py

输出：
  重写 ./checkin-calendar.ics
"""

import json
import re
import sys
from datetime import datetime, timedelta

CAL_NAME = "WorkBuddy 签到"
OUT = "checkin-calendar.ics"
KEEP_DAYS = 30


def _fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d")


def _escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    return s


def _parse_events(raw: str):
    """从已有 ICS 文本中解析出 (uid, dtstart, summary) 列表。"""
    events = []
    blocks = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", raw, re.S)
    for b in blocks:
        uid = re.search(r"^UID:(.+)$", b, re.M)
        dt = re.search(r"^DTSTART;VALUE=DATE:(\d{8})$", b, re.M)
        summary = re.search(r"^SUMMARY:(.+)$", b, re.M)
        if uid and dt:
            events.append({
                "uid": uid.group(1).strip(),
                "dt": dt.group(1).strip(),
                "summary": summary.group(1).strip() if summary else "",
            })
    return events


def build_ics(result: dict) -> str:
    now = datetime.now()
    today = _fmt_dt(now)
    status = result.get("status", "error")
    action = result.get("action", "")
    points = result.get("points", 0)
    msg = result.get("msg", "")

    if status == "ok" and action == "checked_in":
        title = "✅ WorkBuddy 签到成功 +{} 积分".format(points)
        desc = msg
    elif status == "ok" and action == "skip_already_signed":
        title = "✅ WorkBuddy 今日已签到"
        desc = msg
    elif status == "skip":
        title = "⏭️ WorkBuddy 签到活动未开启"
        desc = msg
    else:
        title = "❌ WorkBuddy 签到异常"
        desc = msg

    # 读取旧事件（若存在）
    old_events = []
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            old_events = _parse_events(f.read())
    except (OSError, FileNotFoundError):
        old_events = []

    # 过滤：只保留 KEEP_DAYS 内、且不是今天的旧事件
    cutoff = (now - timedelta(days=KEEP_DAYS)).strftime("%Y%m%d")
    events = [e for e in old_events if e["dt"] >= cutoff and e["uid"] != "wb-checkin-" + today]

    # 追加今天的事件
    events.append({
        "uid": "wb-checkin-" + today,
        "dt": today,
        "summary": _escape(title),
    })
    events.sort(key=lambda e: e["dt"])

    # 生成 ICS
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//WorkBuddy Auto Checkin//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:" + _escape(CAL_NAME),
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    for e in events:
        lines += [
            "BEGIN:VEVENT",
            "UID:" + e["uid"],
            "DTSTAMP:" + now.strftime("%Y%m%dT%H%M%SZ"),
            "DTSTART;VALUE=DATE:" + e["dt"],
            "DTEND;VALUE=DATE:" + _fmt_dt(datetime.strptime(e["dt"], "%Y%m%d") + timedelta(days=1)),
            "SUMMARY:" + e["summary"],
            "DESCRIPTION:" + _escape(desc if e["dt"] == today else ""),
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"status": "error", "action": "parse_failed", "msg": raw[:200], "time": ""}

    ics = build_ics(result)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(ics)
    print("[ics] 已生成", OUT, "共", ics.count("BEGIN:VEVENT"), "条事件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
