# 17TRACK · 跨境热点追踪器

采集 RSS + 网页 → DeepSeek 分析 → 生成 HTML 日报，可选邮件推送。

## 本地运行

```powershell
$env:DEEPSEEK_API_KEY = "sk-你的密钥"
python 主程序.py
```

带邮件推送：

```powershell
$env:SENDER_EMAIL = "你的@gmail.com"
$env:SENDER_PASSWORD = "应用专用密码"
python 主程序.py --no-open --email
```

## 部署到 GitHub Actions（云端每天自动跑）

**完整图文步骤见：[GITHUB_DEPLOY.md](./GITHUB_DEPLOY.md)**

仓库地址示例：`https://github.com/zhoux9179-dotcom/17TRACK`
