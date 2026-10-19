#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 每日自动签到脚本（幂等、零依赖、纯标准库）。

原理：
  1. 用 accessToken + uid 调状态接口查询今日签到状态
  2. 若 today_checked_in == false，再调签到接口领取积分
  3. 已签到则直接跳过，绝不重复领取

用法：
  python checkin.py

环境变量（由 GitHub Actions Secret 注入）：
  WORKBUDDY_ACCESS_TOKEN  登录态 accessToken
  WORKBUDDY_USER_ID       账号 uid
  WORKBUDDY_DOMAIN        接口域名，默认 www.workbuddy.cn（旧客户端为 www.codebuddy.cn）

输出：标准 JSON（供 push.py 消费），含 status/action/points/msg 字段。
退出码：0 = 成功或已签跳过；1 = 异常。
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime


# 接口域名需与实际登录态一致；不同客户端版本域名不同，务必核对
DOMAIN = os.environ.get("WORKBUDDY_DOMAIN", "www.workbuddy.cn")

STATUS_URL = "https://{domain}/v2/billing/meter/checkin-activity-status"
CHECKIN_URL = "https://{domain}/v2/billing/meter/daily-checkin"


def _mask(s: str) -> str:
    if not s:
        return "<空>"
    if len(s) <= 20:
        return "***"
    return s[:8] + "..." + s[-6:]


def _post(url: str, token: str, uid: str):
    req = urllib.request.Request(url, data=b"{}", method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("X-User-Id", uid)
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"code": -1, "msg": raw[:300]}
    except Exception as e:  # noqa: BLE001
        return None, {"code": -1, "msg": repr(e)}


def main() -> int:
    token = os.environ.get("WORKBUDDY_ACCESS_TOKEN", "")
    uid = os.environ.get("WORKBUDDY_USER_ID", "")
    if not token or not uid:
        result = {
            "status": "error",
            "action": "missing_config",
            "points": 0,
            "msg": "缺少 WORKBUDDY_ACCESS_TOKEN 或 WORKBUDDY_USER_ID 环境变量",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 1

    # 1. 查询今日签到状态
    code, status_body = _post(STATUS_URL.format(domain=DOMAIN), token, uid)
    if code != 200 or not isinstance(status_body, dict) or status_body.get("code") != 0:
        result = {
            "status": "error",
            "action": "status_failed",
            "points": 0,
            "msg": "状态查询失败: HTTP {} / {}"
            .format(code, status_body.get("msg") if isinstance(status_body, dict) else status_body),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 1

    data = status_body.get("data", {})
    active = data.get("active")
    checked = data.get("today_checked_in")
    streak = data.get("streak_days")
    total = data.get("total_credits")
    theme = data.get("theme_name", "")

    # 2. 活动未开启
    if active is False:
        result = {
            "status": "skip",
            "action": "inactive",
            "points": 0,
            "msg": "签到活动未开启",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # 3. 今日已签，跳过
    if checked is True:
        result = {
            "status": "ok",
            "action": "skip_already_signed",
            "points": 0,
            "msg": "今日已签到（连签 {} 天，本期累计 {} 分）".format(streak, total),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # 4. 执行签到
    code, checkin_body = _post(CHECKIN_URL.format(domain=DOMAIN), token, uid)
    if code == 200 and isinstance(checkin_body, dict) and checkin_body.get("code") == 0:
        d = checkin_body.get("data", {})
        points = d.get("credit") or d.get("daily_credit") or d.get("points") or 0
        result = {
            "status": "ok",
            "action": "checked_in",
            "points": points,
            "msg": "签到成功 +{} 积分（{}，连签 {} 天）".format(points, theme, streak if streak else "?"),
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # 5. 重复签到（幂等兜底）
    if checkin_body.get("code") == 10001:
        result = {
            "status": "ok",
            "action": "skip_already_signed",
            "points": 0,
            "msg": "今日已签到（幂等跳过）",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        print(json.dumps(result, ensure_ascii=False))
        return 0

    # 6. 其它异常
    result = {
        "status": "error",
        "action": "checkin_failed",
        "points": 0,
        "msg": "签到失败: HTTP {} / {}".format(
            code, checkin_body.get("msg") if isinstance(checkin_body, dict) else checkin_body),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 1


if __name__ == "__main__":
    sys.exit(main())
