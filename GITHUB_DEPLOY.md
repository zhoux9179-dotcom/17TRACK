# 把「热点追踪器」推到 GitHub 并自动跑日报

你的仓库：`https://github.com/zhoux9179-dotcom/17TRACK`

## 一、本地准备（只做一次）

### 1. 打开 PowerShell，进入项目目录

```powershell
cd "d:\【周】17TRACK\0310 AI 可读文件\07_项目代码\热点追踪器"
```

### 2. 配置 DeepSeek API（本地跑主程序需要）

在 PowerShell 里（**不要**把密钥写进代码里）：

```powershell
$env:DEEPSEEK_API_KEY = "你的DeepSeek-sk-xxx"
```

### 3. 初始化 Git 并提交

```powershell
git init
git add .
git commit -m "feat: 跨境热点追踪器 + GitHub Actions"
git branch -M main
git remote add origin https://github.com/zhoux9179-dotcom/17TRACK.git
git push -u origin main
```

若第一次推送要求登录，按 GitHub 提示用 **Personal Access Token** 或 **GitHub CLI** 登录。

---

## 二、在 GitHub 里配置密钥（云端自动跑）

打开仓库 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**，依次添加：

| Name | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 的 API Key（以 `sk-` 开头） |
| `SENDER_EMAIL` | 发件 Gmail，如 `zhoux9179@gmail.com` |
| `SENDER_PASSWORD` | Gmail **应用专用密码**（16 位，不是登录密码） |

收件人默认在 `mailer.py` 里为 `sally@17track.net`，若要改，可改仓库里的 `mailer.py` 再推送。

---

## 三、手动触发一次（测试）

在 GitHub 里：**Actions** → 选 **跨境热点日报** → **Run workflow** → Run。

成功后会在 **Actions** 里看到绿色勾号，邮箱会收到 HTML 日报。

---

## 四、定时说明

工作流文件：`.github/workflows/daily.yml`  
默认：**每天 UTC 0:30**（约北京时间 **8:30**）。

要改时间，编辑 `cron` 一行（UTC 时间）：

```yaml
- cron: "30 0 * * *"
```

---

## 五、常见问题

- **推送失败**：检查是否已 `git remote add origin`、是否已登录 GitHub。
- **Actions 失败**：看 **Actions** 里红色日志；多数是 `DEEPSEEK_API_KEY` 未填或错误。
- **邮件发不出**：检查 `SENDER_EMAIL` / `SENDER_PASSWORD`；Gmail 需开启两步验证并生成 **应用专用密码**。

---

## 六、在线看板（GitHub Pages）

**正确网址（项目仓库）：**

`https://zhoux9179-dotcom.github.io/17TRACK/`

（不是只有 `zhoux9179-dotcom.github.io`，后面要带 **`/17TRACK`**。）

### 设置步骤

1. 把本地最新代码推上去（含更新后的 `.github/workflows/daily.yml`）。
2. 在 GitHub：**Actions** → **跨境热点日报** → **Run workflow** 跑一次（成功后会自动创建 **`gh-pages`** 分支）。
3. 打开 **Settings** → **Pages**：
   - **Source**：**Deploy from a branch**
   - **Branch**：选 **`gh-pages`**，文件夹 **`/(root)`**（不要再用 `main` 根目录，因为日报在 CI 里生成，不在 main 上。）
4. 保存后等 1～2 分钟，再打开上面的网址即可看到当日 HTML 看板。

之后每次定时任务或手动跑 Actions，看板会随最新 `热点日报_*.html` 自动更新。
