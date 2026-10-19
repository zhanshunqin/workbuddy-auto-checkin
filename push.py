#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
签到结果推送脚本（纯标准库，零依赖）。

消费 checkin.py 输出的 JSON，把结果推送到微信（Server 酱 / PushPlus / 企业微信机器人）。

渠道优先级（按已配置的环境变量自动选择）：
  1. PUSHPLUS_TOKEN          PushPlus（推荐，个人微信，免费）
  2. SERVERCHAN_SENDKEY      Server 酱 / Server酱³
  3. WECOM_WEBHOOK_URL       企业微信群机器人

"每次都提醒"：成功与失败都会推送一条摘要。
"""

import json
import os
import sys
import urllib.parse
import urllib.request


def _post(url: str, payload: dict):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return "推送异常: " + repr(e)


def _fmt(r: dict) -> str:
    icon = {"ok": "✅", "skip": "⏭️", "error": "❌"}.get(r.get("status"), "❓")
    lines = [
        "{} WorkBuddy 自动签到".format(icon),
        "时间：{}".format(r.get("time", "")),
        "结果：{}".format(r.get("msg", "")),
    ]
    if r.get("points"):
        lines.append("积分：+{}".format(r.get("points")))
    return "\n".join(lines)


def main() -> int:
    raw = sys.stdin.read().strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"status": "error", "action": "parse_failed", "msg": raw[:200] or "无输出", "time": ""}

    text = _fmt(result)

    # PushPlus
    token = os.environ.get("PUSHPLUS_TOKEN")
    if token:
        payload = {
            "token": token,
            "title": "WorkBuddy 签到",
            "content": text,
            "template": "txt",
        }
        resp = _post("http://www.pushplus.plus/send", payload)
        print("[pushplus]", resp[:200])
        return 0

    # Server 酱
    sendkey = os.environ.get("SERVERCHAN_SENDKEY")
    if sendkey:
        url = "https://sctapi.ftqq.com/{}.send".format(sendkey)
        data = urllib.parse.urlencode({"title": "WorkBuddy 签到", "desp": text}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        try:
            resp = urllib.request.urlopen(req, timeout=15)
            print("[serverchan]", resp.read().decode("utf-8", "replace")[:200])
        except Exception as e:  # noqa: BLE001
            print("[serverchan] 推送异常:", repr(e))
        return 0

    # 企业微信机器人
    webhook = os.environ.get("WECOM_WEBHOOK_URL")
    if webhook:
        payload = {"msgtype": "text", "text": {"content": text}}
        resp = _post(webhook, payload)
        print("[wecom]", resp[:200])
        return 0

    # 未配置任何推送渠道：仅打印到日志
    print("[push] 未配置推送渠道，结果仅记录于日志：")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
