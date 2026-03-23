"""
调试报告生成器 - 查看分类纠正情况
同时支持发送日报邮件
"""
import json, re, sys, os
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent))

import mailer
from 报告生成器 import generate_report

# ── 加载数据 ──────────────────────────────────────────────
today_str = datetime.now().strftime("%Y-%m-%d")
output_dir = Path(__file__).parent / "输出"
output_dir.mkdir(exist_ok=True)

# 优先用今天的数据，没有则用昨天
data_path = output_dir / f"热点数据_{today_str}.json"
if not data_path.exists():
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    data_path = output_dir / f"热点数据_{yesterday}.json"

if not data_path.exists():
    print(f"❌ 数据文件不存在，尝试: {data_path}")
    print("请先运行采集器生成热点数据")
    sys.exit(1)

with open(data_path, encoding="utf-8") as f:
    data = json.load(f)

articles = data["articles"]
print(f"已加载 {len(articles)} 篇文章")

# ── 生成 HTML 报告 ────────────────────────────────────────
html_path = output_dir / f"热点日报_{re.search(r'(\d{4}-\d{2}-\d{2})', data_path.name).group(1)}.html"

# 从文件名提取日期，如 "热点数据_2026-03-20.json" -> "2026年03月20日"
_date_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", data_path.name)
if _date_match:
    date_display = f"{_date_match.group(1)}年{_date_match.group(2)}月{_date_match.group(3)}日"
else:
    date_display = datetime.now().strftime("%Y年%m月%d日")
generate_report(
    articles=articles,
    output_path=str(html_path),
    hours=48,
    hot_topics=data.get("hot_topics"),
    ads=data.get("ads", []),
)
print(f"✅ 报告已生成: {html_path}")

# ── 发送邮件 ──────────────────────────────────────────────
print("\n📧 正在发送邮件...")

# 读取 HTML 内容
with open(html_path, encoding="utf-8") as f:
    html_content = f.read()

result = mailer.send_report(
    html_content=html_content,
    date_str=date_display,
    recipient="sally@17track.net",
)

if result["ok"]:
    print(f"✅ 邮件发送成功！收件人: {result['sent']}")
else:
    print(f"❌ 邮件发送失败: {result['error']}")
    print()
    print("请先配置邮件认证方式：")
    print("  方式1 - 环境变量:")
    print("    $env:SENDER_EMAIL='your-email@gmail.com'")
    print("    $env:SENDER_PASSWORD='xxxx xxxx xxxx xxxx'  # Gmail 应用专用密码")
    print()
    print("  方式2 - OAuth2 (推荐，更安全):")
    print("    编辑 mailer.py 中的 GMAIL_OAUTH2 配置")
    print()
    print("Gmail 应用专用密码获取:")
    print("  1. 访问 https://myaccount.google.com/security")
    print("  2. 开启两步验证")
    print("  3. 搜索 '应用专用密码' -> 创建新密码")
