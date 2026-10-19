# WorkBuddy 每日自动签到

在 GitHub Actions 云端每天自动完成 WorkBuddy「Buddy 加油站」签到领积分，电脑关机也能签，签到结果推送微信。

## 工作原理

签到本质是一次带登录态的 HTTP 请求。脚本用你账号的 `accessToken` + `uid` 直接调用官方接口，不碰任何图形界面。

| 用途 | 方法 | 地址 |
| ---- | ---- | ---- |
| 查今日签到状态 | POST | `https://{domain}/v2/billing/meter/checkin-activity-status` |
| 执行签到 | POST | `https://{domain}/v2/billing/meter/daily-checkin` |

脚本**幂等**：先查状态，今天已签就跳过，绝不重复领取。

## 目录结构

```
.
├── checkin.py                  # 签到脚本（纯标准库，零依赖）
├── push.py                     # 结果推送脚本（PushPlus / Server酱 / 企业微信机器人）
├── README.md
└── .github/workflows/checkin.yml  # 定时触发（每天 09:10，可手动触发）
```

## 上线步骤（只需 4 步）

### 第 1 步：准备两个密钥

> ⚠️ 这是你 WorkBuddy 账号的「钥匙」，等同于登录密码。**只填进 GitHub Secret，绝不贴进任何公开代码、群聊或公开仓库。**

在已登录 WorkBuddy 客户端的电脑上，打开登录态文件（明文 JSON）：

- **macOS**：`~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info`
- **Windows**：`%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info`

记下两个字段：

| 字段 | 位置 | 对应 Secret |
| ---- | ---- | ---- |
| `auth.accessToken` | 一长串 `eyJ...` 开头 | `WORKBUDDY_ACCESS_TOKEN` |
| `account.uid` | 形如 `xxxx-xxxx-...` | `WORKBUDDY_USER_ID` |

> **注意**：新版本客户端（2026-10 起）的 token 字段已加密存储（`$wbEncrypted` 结构），
> 直接读文件拿不到明文。若你机器上的 `workbuddy-desktop.info` 里 `accessToken` 是加密结构，
> 可查看同目录下**历史备份文件**（形如 `workbuddy-desktop.<时间戳>.<id>.info`），
> 较早的备份往往是明文；或退出客户端重新登录后，第一时间抓取最新明文。
> 域名也需要核对：`auth.domain` 是 `www.workbuddy.cn` 还是 `www.codebuddy.cn`，务必与 Secret 一致。

### 第 2 步：建私有仓库并上传

1. 在 GitHub 新建一个 **Private（私有）** 仓库。
2. 把本目录全部文件上传进去（`checkin.py`、`push.py`、`.github/workflows/checkin.yml`、`README.md`）。

> 仓库必须私有——运行时会保存 token 用于自动续期，公开仓库等于把账号送人。

### 第 3 步：配置 Secret

在仓库页面：**Settings → Secrets and variables → Actions → New repository secret**，添加：

| Secret 名 | 值 | 必填 |
| --------- | -- | ---- |
| `WORKBUDDY_ACCESS_TOKEN` | 你的 accessToken | ✅ |
| `WORKBUDDY_USER_ID` | 你的 uid | ✅ |
| `WORKBUDDY_DOMAIN` | `www.workbuddy.cn` 或 `www.codebuddy.cn`（与登录态一致） | ✅ |
| `PUSHPLUS_TOKEN` | PushPlus 的 token（见下） | 推送才需 |

### 第 4 步：配置推送（可选，推荐）

「每次都提醒」已内置，任选一个渠道，填对应 Secret：

- **PushPlus（推荐，免费，推个人微信）**：
  1. 打开 [pushplus.plus](http://www.pushplus.plus)，微信扫码登录。
  2. 复制「一对多」或「一对一」的 `token`。
  3. 填入 Secret `PUSHPLUS_TOKEN`。
- **Server 酱**：`SERVERCHAN_SENDKEY`
- **企业微信群机器人**：`WECOM_WEBHOOK_URL`

## 验证与运行

- **手动测试**：仓库 **Actions → WorkBuddy Daily Checkin → Run workflow → Run workflow**，立即跑一次。
- **自动运行**：每天北京时间 09:10 自动触发（GitHub 免费额度足够日常使用）。
- **查看结果**：Actions 每次运行日志里，`Run checkin` 步骤会输出 JSON；`Push result` 步骤会推送微信。

## 常见返回结果

| status | action | 含义 |
| ------ | ------ | ---- |
| `ok` | `checked_in` | 签到成功，+N 积分 |
| `ok` | `skip_already_signed` | 今天已签，跳过 |
| `skip` | `inactive` | 活动未开启 |
| `error` | `status_failed` / `checkin_failed` | 接口异常，需排查 |
| `error` | `missing_config` | Secret 没配好 |

## 安全红线（务必遵守）

1. token 只进 GitHub Secret，绝不进公开仓库、群聊、日志截图。
2. 仓库保持 **Private**。
3. 若在客户端里「退出登录」，token 会立即失效，需按第 1 步重新抓取并更新 Secret。
4. accessToken 有效期内，脚本每天跑会持续刷新；连续 60 天没跑成功，链路会断，需重取 token。
