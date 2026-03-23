# 跨境热点日报 - 完整工作流程文档

本文档描述「跨境热点日报」系统的完整架构、工作流程和关键技术要点。供其他 AI 或开发者在复现/维护本系统时参考。

---

## 一、系统概述

| 项目 | 说明 |
|------|------|
| 仓库 | https://github.com/zhoux9179-dotcom/17TRACK |
| 在线看板 | https://zhoux9179-dotcom.github.io/17TRACK/ |
| 定时运行 | 每天 UTC 0:30（约北京时间 8:30） |
| 核心功能 | 自动采集跨境电商/物流/AI 领域的 RSS 热门文章 → DeepSeek AI 分析 → 生成可视化 HTML 日报 → 推送到 GitHub Pages + 邮件推送 |

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          数据流向图                                   │
└─────────────────────────────────────────────────────────────────────┘

   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
   │  RSS 数据源   │ ──▶ │  DeepSeek AI │ ──▶ │  HTML 报告   │
   │ (采集器.py)   │     │  (分析器.py)  │     │ (报告生成器)  │
   └──────────────┘     └──────────────┘     └──────────────┘
                                                      │
                              ┌───────────────────────┼───────────────┐
                              │                       │               │
                              ▼                       ▼               ▼
                      ┌──────────────┐       ┌──────────────┐  ┌──────────┐
                      │ GitHub Pages │       │  QQ 邮箱 SMTP │  │  本地预览 │
                      │  (gh-pages)  │       │  (mailer.py)  │  │ (浏览器)  │
                      └──────────────┘       └──────────────┘  └──────────┘
```

### 模块说明

| 文件 | 职责 |
|------|------|
| `主程序.py` | 入口，协调各模块，命令行参数 `--hours`(采集窗口) `--email`(发邮件) `--no-open`(不打开浏览器) |
| `采集器.py` | 从预设 RSS 源抓取最近 N 小时的跨境电商/物流/AI 文章 |
| `分析器.py` | 调用 DeepSeek API 对文章做 AI 摘要、分类标签、趋势洞察 |
| `报告生成器.py` | 将分析结果渲染为带 CSS 样式的 HTML 看板 |
| `mailer.py` | SMTP 邮件发送模块，支持 HTML 邮件正文渲染 |
| `.github/workflows/daily.yml` | GitHub Actions 自动化脚本，定时运行+部署+邮件 |

---

## 三、关键配置

### 3.1 GitHub Secrets (仓库 → Settings → Secrets and variables → Actions)

| Secret 名称 | 用途 | 示例值 |
|------------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 认证（必填） | `sk-xxxxxxxx` |
| `SENDER_EMAIL` | 发件人邮箱 | `286590856@qq.com` |
| `SENDER_PASSWORD` | QQ 邮箱「授权码」而非登录密码 | `xxxxxxxxxxxx` |

> **获取 QQ 邮箱授权码**：QQ 邮箱 → 设置 → 账户 → 开启「IMAP/SMTP服务」→ 生成授权码（16 位）

### 3.2 GitHub Pages 配置（关键！）

- **正确配置**：Source 选 **`gh-pages` 分支** + **`/(root)` 目录**
- **错误配置**：选 `main` 分支 → GitHub 会默认展示 README.md，而非 CI 生成的日报 HTML
- **配置路径**：仓库 → Settings → Pages → Branch: `gh-pages` / `/(root)` → Save
- **CDN 刷新**：修改后通常 1-5 分钟生效；可用 `gh api repos/{owner}/{repo}/pages/builds -X POST` 强制重建

---

## 四、工作流程（从代码到上线）

### 4.1 本地开发调试

```bash
# 1. 克隆仓库
git clone https://github.com/zhoux9179-dotcom/17TRACK.git
cd 17TRACK

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 3. 配置 DeepSeek API（不要写死在代码里）
$env:DEEPSEEK_API_KEY = "sk-xxxx"

# 4. 运行主程序
.venv\Scripts\python 主程序.py --hours 48
# 生成文件：输出/热点日报_YYYY-MM-DD.html
```

### 4.2 GitHub Actions 自动化

1. **定时触发**：每天 UTC 0:30 自动运行
2. **手动触发**：仓库 → Actions → 「跨境热点日报」→ Run workflow

**Actions 流程**：
```
Checkout → Set up Python → Install deps → Check API key →
Run 主程序.py (采集+分析+生成HTML+发邮件) →
Prepare GitHub Pages → Deploy to gh-pages
```

### 4.3 邮件推送逻辑

**发件流程**（`mailer.py`）：
1. 从 `gh-pages` 分支拉取最新 `index.html`（约 12-17KB）
2. 提取 `<style>` 块（保留 CSS 样式）
3. 提取 `<body>` 内容（去掉 DOCTYPE/html/head 冗余标签）
4. 在顶部插入「打开看板」醒目横幅按钮
5. 使用 `multipart/alternative` 发送：纯文本 + HTML 双版本
6. 邮件头使用 RFC2047 编码（`Header(...).encode()`）避免 QQ 邮箱拒绝

**发件函数调用**：
```python
from mailer import send_report
result = send_report(html_content="<body>...</body>", date_str="2026-03-23")
```

---

## 五、常见问题排查

### 5.1 打开看板链接却是 README/项目说明

**原因**：GitHub Pages 源配错（配在 `main` 而非 `gh-pages`）

**排查**：
```bash
# 检查当前 Pages 配置
gh api repos/zhoux9179-dotcom/17TRACK/pages --jq '.source'

# 正确应返回：{"branch":"gh-pages","path":"/"}
# 错误返回：{"branch":"main","path":"/"}
```

**解决**：
```bash
# 通过 API 修改 Pages 源（需 repo 管理权限）
gh api repos/{owner}/{repo}/pages -X PUT -f 'source[branch]=gh-pages' -f 'source[path]=/'

# 或手动：Settings → Pages → Branch: gh-pages → Save
# 强制重建：gh api repos/{owner}/{repo}/pages/builds -X POST
```

### 5.2 邮件正文显示为源码/乱码/无样式

**原因**：
- 发送时用了 `MIMEMultipart` 但 `html` 部分未正确 attach
- 未保留原始 `<style>` 块
- From/Subject 头未用 RFC2047 编码

**解决**（参考 `mailer.py`）：
```python
# 1. 提取原始 CSS
styles = _extract_style_blocks(html_content)

# 2. 保留完整文档结构
full_html = f"<!DOCTYPE html><html><head>{styles}</head><body>{body}</body></html>"

# 3. RFC2047 编码发件头
from email.header import Header
msg["From"] = Header("发件人名称", "utf-8").encode() + " <user@example.com>"
msg["Subject"] = Header("邮件标题", "utf-8").encode()

# 4. 使用 multipart/alternative
msg = MIMEMultipart("alternative")
msg.attach(MIMEText(plain_text, "plain", "utf-8"))
msg.attach(MIMEText(full_html, "html", "utf-8"))
```

### 5.3 Actions 失败：DEEPSEEK_API_KEY 未配置

**解决**：仓库 → Settings → Secrets and variables → Actions → New repository secret → 添加 `DEEPSEEK_API_KEY`

### 5.4 本地运行报 `PermissionError: [Errno 13]`

**原因**：NSS 安全软件/代理试图写入 SSL 密钥日志文件但无权限

**解决**：
```python
import os
for _k in ("SSLKEYLOGFILE", "SSL_KEYLOGFILE"):
    os.environ.pop(_k, None)
```

---

## 六、常用调试命令

### 手动触发 CI/CD

```bash
# 触发 GitHub Actions（自动发邮件+部署）
gh workflow run 跨境热点日报 --repo zhoux9179-dotcom/17TRACK

# 查看最近一次运行状态
gh run list --repo zhoux9179-dotcom/17TRACK --limit 1

# 取消正在进行的 workflow
gh run cancel {run_id} --repo zhoux9179-dotcom/17TRACK
```

### 手动发送邮件

```python
# 临时脚本 _send_now.py（从 gh-pages 拉页面发邮件）
import requests
from mailer import send_report

r = requests.get("https://zhoux9179-dotcom.github.io/17TRACK/")
send_report(r.text, "2026-03-23")
```

### 检查 Pages 状态

```bash
# 查看 Pages 构建历史
gh api repos/{owner}/{repo}/pages/builds --jq '.[0].status'

# 强制重建
gh api repos/{owner}/{repo}/pages/builds -X POST
```

---

## 七、文件清单

```
17TRACK/
├── 主程序.py              # 入口
├── 采集器.py              # RSS 采集
├── 分析器.py              # DeepSeek AI 分析
├── 报告生成器.py          # HTML 渲染
├── mailer.py             # 邮件发送
├── requirements.txt      # 依赖
├── 数据源配置.py          # RSS 源列表
├── .github/workflows/
│   └── daily.yml         # CI/CD 自动化
├── GITHUB_DEPLOY.md      # 部署说明（用户视角）
└── 输出/                  # 生成的 HTML 报告
    └── 热点日报_2026-03-23.html
```

---

## 八、技术要点总结

1. **GitHub Pages 必须用 `gh-pages` 分支**：`main` 分支只有源码和 README，日报是 CI 推送到 `gh-pages` 的
2. **邮件 HTML 渲染关键**：保留 `<style>` + RFC2047 编码发件头 + 使用 `multipart/alternative`
3. **SSL 权限问题**：在导入 `smtplib`/`requests` 前清理 `SSL_KEYLOGFILE` 环境变量
4. **QQ 邮箱授权码**：不是登录密码，是「授权码」16 位字符串
5. **强制刷新 CDN**：修改 Pages 配置后，用 API 触发重建确保生效

---

本文档由 AI 生成，最后更新：2026-03-23
