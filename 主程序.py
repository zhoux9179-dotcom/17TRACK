"""
主程序 — 跨境热点追踪器入口
用法：python 主程序.py [--hours 48]

流程：采集(48h) → AI分析 → 热搜聚合 → 保存JSON → 生成HTML报告 → 自动打开
"""

# 清除 SSL 密钥日志相关环境变量，避免部分环境 NSS 权限报错
import os
for _k in ("SSLKEYLOGFILE", "SSL_KEYLOGFILE"):
    os.environ.pop(_k, None)

import sys
import json
import argparse
import webbrowser
from datetime import datetime
from pathlib import Path

from 采集器 import collect_all
from 分析器 import analyze_articles, build_hot_topics
from 报告生成器 import generate_report

OUTPUT_DIR = Path(__file__).parent / "输出"
OUTPUT_DIR.mkdir(exist_ok=True)

# 固定采集窗口
DEFAULT_HOURS = 48


def main():
    parser = argparse.ArgumentParser(description="跨境热点追踪器")
    parser.add_argument("--hours", type=int, default=DEFAULT_HOURS,
                        help=f"采集时间窗口（小时），默认 {DEFAULT_HOURS}")
    parser.add_argument("--no-open", action="store_true", help="生成后不自动打开浏览器")
    parser.add_argument(
        "--email",
        action="store_true",
        help="生成后将 HTML 日报发到邮箱（需环境变量 SENDER_EMAIL、SENDER_PASSWORD）",
    )
    args = parser.parse_args()

    date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"   17TRACK Cross-Border Hot Topics Tracker   {date_str}")
    print(f"{'='*60}")

    # ── 步骤 1：采集 ──────────────────────────────────────────
    articles = collect_all(hours=args.hours)
    if not articles:
        print("[WARN] 未采集到相关文章，请检查网络连接或数据源配置")
        sys.exit(1)

    # ── 步骤 2：AI 分析（含深度摘要）────────────────────────
    enriched = analyze_articles(articles)
    if not enriched:
        print("[WARN] AI 分析后无高相关文章（尝试放宽关键词或延长时间窗口）")
        sys.exit(1)

    # ── 步骤 3：热搜话题聚合 ──────────────────────────────────
    hot_topics = build_hot_topics(enriched)
    print(f"  [OK] 热搜话题聚合完成，共 {len(hot_topics)} 个话题")

    # ── 步骤 4：保存原始数据 ──────────────────────────────────
    json_path = OUTPUT_DIR / f"热点数据_{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"articles": enriched, "hot_topics": hot_topics}, f, ensure_ascii=False, indent=2)
    print(f"  [OK] 原始数据已保存: {json_path.name}")

    # ── 步骤 5：生成 HTML 报告 ────────────────────────────────
    html_path = OUTPUT_DIR / f"热点日报_{date_str}.html"
    generate_report(enriched, str(html_path), hours=args.hours, hot_topics=hot_topics)

    # ── 步骤 6：打印摘要 ──────────────────────────────────────
    from collections import Counter
    cat_dist = Counter(a.get("topic_category", "其他") for a in enriched)

    print(f"\n{'─'*60}")
    print(f"  采集完成摘要")
    print(f"{'─'*60}")
    print(f"  高相关文章：{len(enriched)} 篇  (8分以上：{sum(1 for a in enriched if a.get('relevance',0)>=8)} 篇)")
    print(f"\n  话题分布：")
    for cat, cnt in cat_dist.most_common():
        bar = "#" * cnt + "-" * max(0, 10 - cnt)
        print(f"    {cat:<12} {bar} {cnt}")
    print(f"\n  今日热搜 TOP 5：")
    for i, t in enumerate(hot_topics[:5], 1):
        print(f"    {i}. {t['topic']}  ({t['count']}篇 / 热度{t['heat']})")
    print(f"\n  报告路径: {html_path}")
    print(f"{'='*60}\n")

    # ── 步骤 7：自动打开报告 ──────────────────────────────────
    if not args.no_open:
        webbrowser.open(str(html_path))

    # ── 步骤 8：邮件推送（可选，如云服务器 / GitHub Actions）────────
    if args.email:
        import mailer

        y, m, d = date_str.split("-")
        date_display = f"{y}年{m}月{d}日"
        html_content = html_path.read_text(encoding="utf-8")
        result = mailer.send_report(html_content, date_display)
        if result.get("ok"):
            print(f"  [OK] 邮件已发送: {result.get('sent')}")
        else:
            print(f"  [WARN] 邮件发送失败: {result.get('error')}")


if __name__ == "__main__":
    main()
