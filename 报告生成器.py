"""
报告生成器 v2 — 跨境热点追踪 HTML 日报

用户关注四大板块：
  1. 电商平台动态   — 各大平台政策、卖家动态
  2. 区域物流趋势   — 全球各区域物流、航线、仓储变化
  3. AI技术与新应用 — 大模型、Agent、数字化在电商物流的应用
  4. 出海DTC观察   — 中国品牌出海、独立站、DTC模式

特点：
  - 去掉无用的热搜排名和分布图表
  - 去掉所有评分标签（受众不需要看分数）
  - 每条内容有要点、有分析，不堆砌碎片
  - 标题即为事件，摘要即为洞察
  - 每板块最多展示6条高相关文章
"""

import json
import re
from html import escape
from collections import defaultdict
from datetime import datetime

from 数据源配置 import TOPIC_CATEGORIES

# ─────────────────────────────────────────────────────────────
# 板块映射配置
# ─────────────────────────────────────────────────────────────

# AI 分类 → 板块名称（展示顺序）
SECTION_ORDER = [
    ("电商平台动态",    "E-Commerce Platforms"),
    ("区域物流趋势",    "Regional Logistics"),
    ("AI技术与新应用",  "AI & Digital"),
    ("出海DTC观察",    "Cross-border DTC"),
]

# 话题分类 → 对应板块（一个分类可能映射到多个板块）
CAT_TO_SECTION = {
    "电商平台动态":    "电商平台动态",
    "跨境物流动态":    "区域物流趋势",
    "行业报告数据":    "区域物流趋势",
    "AI技术新应用":    "AI技术与新应用",
    "出海DTC观察":     "出海DTC观察",
    "其他":            None,   # 未分类文章不展示
}

# 板块配色
SECTION_COLORS = {
    "电商平台动态":    "#2563eb",
    "区域物流趋势":    "#0ea5e9",
    "AI技术与新应用":  "#10b981",
    "出海DTC观察":    "#f59e0b",
}

# ─────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────

def generate_report(articles: list[dict], output_path: str, hours: int = 48,
                    hot_topics: list[dict] = None, ads: list[dict] = None):
    """生成 HTML 日报并写入文件"""
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")
    gen_at = now.strftime("%Y-%m-%d %H:%M")
    ads = ads or []

    total = len(articles)
    sources = list(dict.fromkeys(a["source"] for a in articles))
    source_count = len(sources)

    # ── 辅助函数（定义在开头，避免 UnboundLocalError）──────────

    def _dedup_by_story(arts: list[dict]) -> list[dict]:
        best = {}
        for a in arts:
            label = a.get("story_label", "") or a.get("url", "")
            score = a.get("relevance", 0)
            if label not in best or score > best[label].get("relevance", 0):
                best[label] = a
        return list(best.values())

    def _fix_misclass(arts: list[dict]) -> list[dict]:
        """纠正 AI 分错的分类，返回 (可能被重新归类的文章列表)"""
        high_priority = [
            (re.compile(r"暴雷|资金盘|骗局|卷款|跑路|诈骗|黑帽玩法"), "跨境物流动态"),
            (re.compile(r"AMR|仓储机器人|黑灯仓库|自动化仓储|仓库自动化"), "跨境物流动态"),
            (re.compile(r"品牌方舟早报|速来围观"), "出海DTC观察"),
            (re.compile(r"龙虾|OpenClaw|openclaw"), "AI技术新应用"),
        ]
        normal_rules = [
            # 已移除：电商平台动态的过滤现在由 _is_real_platform_news() 函数处理
        ]
        fixed = []
        for a in arts:
            text = (a.get("title", "") + " " + (a.get("ai_summary_zh", "") or "")).lower()
            orig_cat = a.get("topic_category", "")
            matched = False
            for pattern, correct_cat in high_priority:
                if pattern.search(text):
                    correct_sec = CAT_TO_SECTION.get(correct_cat)
                    a = dict(a)
                    a["topic_category"] = correct_cat
                    a["_fixed_sec"] = correct_sec
                    matched = True
                    break
            if not matched:
                for pattern, correct_cat in normal_rules:
                    if orig_cat == "电商平台动态" and pattern.search(text):
                        correct_sec = CAT_TO_SECTION.get(correct_cat)
                        a = dict(a)
                        a["topic_category"] = correct_cat
                        a["_fixed_sec"] = correct_sec
                        matched = True
                        break
            if not matched:
                a["_fixed_sec"] = CAT_TO_SECTION.get(orig_cat)
            fixed.append(a)
        return fixed

    def _is_ocean_news(a: dict) -> bool:
        ocean_kws = ["海运", "集装箱船", "船公司", "马士基", "Maersk", "CMA CGM",
                     "Cosco", "中远", "赫伯罗特", "Hapag", "Hapag-Lloyd", "ONE", "Evergreen",
                     "Yang Ming", "阳明", "长荣", "ULCV", "ocean carrier"]
        text = (a.get("title", "") + a.get("ai_summary_zh", "")).lower()
        return any(kw.lower() in text for kw in ocean_kws)

    def _is_real_platform_news(a: dict) -> bool:
        """判断是否为真正的平台动态（财报、托管、报告、新平台等），排除运营指南"""
        text = (a.get("title", "") + " " + (a.get("ai_summary_zh", "") or "")).lower()
        
        # 排除运营指南类内容
        exclude_patterns = [
            r"新卖家必读|新手卖家必看|卖家必读|必看|必读",
            r"账户运营红线|运营红线|账户红线",
            r"注册信息填写|注册.*卡住|注册.*易错",
            r"全攻略|入门指南|新手.*指南|新手.*攻略",
            r"如何.*开店|如何.*入驻|开店.*指南",
            r"商标.*tro|tro.*案|侵权.*风险",
        ]
        for pattern in exclude_patterns:
            if re.search(pattern, text):
                return False
        
        # 平台列表
        platforms = [
            r"亚马逊|amazon", r"tiktok.*shop|tk.*shop", r"temu", r"ebay", 
            r"shopee", r"shopify", r"lazada", r"希音|shein", r"速卖通|aliexpress",
            r"walmart", r"京东.*国际|joybuy"
        ]
        
        # 平台动向关键词
        platform_news_keywords = [
            r"财报|财务报告|earnings|financial.*report|revenue|营收|利润",
            r"托管|fba.*托管|托管.*服务",
            r"报告|market.*report|行业报告|平台报告",
            r"新平台|新.*电商平台|launch|上线|推出.*平台",
            r"战略|strategy|扩张|expansion|增长|growth",
            r"收购|acquisition|合并|merger",
            r"上市|ipo|上市计划",
            r"政策.*调整|政策.*变化|新政策|policy",
            r"佣金.*调整|费率.*变化|commission|fee.*change",
        ]
        
        # 必须同时包含平台名和动向关键词
        has_platform = any(re.search(p, text, re.I) for p in platforms)
        has_news_keyword = any(re.search(k, text, re.I) for k in platform_news_keywords)
        
        return has_platform and has_news_keyword

    def _has_sufficient_summary(a: dict) -> bool:
        """检查文章摘要是否超过100字"""
        deep = a.get("deep_summary", "").strip()
        basic = a.get("ai_summary_zh", "").strip()
        summary = deep if deep else basic
        return len(summary) >= 100

    # ── 路由到四大板块（包含纠正后的重新归类）───────────────
    sections: dict[str, list] = {name: [] for name, _ in SECTION_ORDER}
    for a in _fix_misclass(articles):
        sec = a.get("_fixed_sec")
        if sec:
            # 电商平台动态板块：只保留真正的平台动向
            if sec == "电商平台动态":
                if _is_real_platform_news(a):
                    sections[sec].append(a)
            else:
                sections[sec].append(a)

    # ── 板块内去重 + 船运限流 + 摘要过滤 + 截断 ───────────────────────
    for sec_name in sections:
        arts = _dedup_by_story(sections[sec_name])
        # 过滤掉摘要少于100字的文章
        arts = [a for a in arts if _has_sufficient_summary(a)]
        
        if sec_name == "区域物流趋势":
            ocean = [a for a in arts if _is_ocean_news(a)]
            non_ocean = [a for a in arts if not _is_ocean_news(a)]
            sections[sec_name] = (non_ocean + ocean[:1])[:6]
        else:
            arts.sort(key=lambda x: x.get("relevance", 0), reverse=True)
            sections[sec_name] = arts[:6]

    html = _build_html(
        date_str=date_str,
        gen_at=gen_at,
        hours=hours,
        total=total,
        source_count=source_count,
        sections=sections,
        sources=sources,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  [OK] 报告已生成: {output_path}")


# ─────────────────────────────────────────────────────────────
# HTML 构建
# ─────────────────────────────────────────────────────────────

def _build_html(**ctx) -> str:
    date_str = ctx["date_str"]
    gen_at = ctx["gen_at"]
    hours = ctx["hours"]

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>跨境热点日报 · {date_str}</title>
<style>
:root {{
  --navy:  #0f2044;
  --navy2: #1a3a6b;
  --blue:  #2563eb;
  --sky:   #0ea5e9;
  --green: #10b981;
  --amber: #f59e0b;
  --red:   #ef4444;
  --gray:  #f0f4f8;
  --card:  #ffffff;
  --text:  #1a2744;
  --muted: #6b7280;
  --border:#e5e7eb;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--gray); color:var(--text); line-height:1.6; }}

/* ── 头部 ── */
.header {{
  background:linear-gradient(135deg,#0a1628 0%,#1a3a6b 60%,#0d5eaf 100%);
  color:#fff; padding:40px 0 36px;
}}
.h-inner {{ max-width:1100px; margin:0 auto; padding:0 48px; }}
.h-badge {{ display:inline-flex; align-items:center; gap:6px; background:rgba(14,165,233,0.15); border:1px solid rgba(14,165,233,0.35); border-radius:20px; padding:3px 14px; margin-bottom:12px; font-size:11px; font-weight:700; color:#38bdf8; letter-spacing:1.5px; }}
.header h1 {{ font-size:28px; font-weight:800; margin-bottom:4px; }}
.header h1 span {{ color:#38bdf8; }}
.h-meta {{ font-size:13px; color:rgba(255,255,255,0.45); }}
.h-stats {{ display:flex; gap:40px; margin-top:18px; }}
.h-stat {{ text-align:center; }}
.h-stat-val {{ font-size:24px; font-weight:800; color:#fff; line-height:1; }}
.h-stat-lbl {{ font-size:11px; color:rgba(255,255,255,0.4); margin-top:3px; text-transform:uppercase; letter-spacing:0.8px; }}

/* ── 主内容 ── */
.container {{ max-width:1100px; margin:0 auto; padding:36px 48px 64px; }}

/* ── 板块 ── */
.section {{
  background:var(--card); border-radius:16px;
  box-shadow:0 2px 8px rgba(0,0,0,0.07);
  margin-bottom:20px; overflow:hidden;
}}
.section-header {{
  display:flex; align-items:center; gap:12px;
  padding:20px 28px 18px; border-bottom:1px solid var(--border);
}}
.section-icon {{ font-size:20px; }}
.section-name {{ font-size:17px; font-weight:800; color:var(--navy); }}
.section-count {{ font-size:12px; color:var(--muted); margin-left:auto; background:#f3f4f6; padding:2px 10px; border-radius:9999px; }}
.section-en {{ font-size:11px; color:var(--muted); font-weight:500; letter-spacing:0.5px; margin-left:6px; }}

.section-body {{ padding:4px 0; }}

/* ── 文章卡片 ── */
.article {{
  padding:22px 28px 20px;
  border-bottom:1px solid var(--border);
  transition:background .12s;
}}
.article:last-child {{ border-bottom:none; }}
.article:hover {{ background:#fafbff; }}

.article-title {{
  font-size:16px; font-weight:800; color:var(--navy);
  line-height:1.4; margin-bottom:8px;
}}
.article-title a {{ color:inherit; text-decoration:none; }}
.article-title a:hover {{ color:var(--blue); }}

.article-summary {{
  font-size:14px; color:#374151; line-height:1.9; margin-bottom:10px;
}}

.article-insight {{
  font-size:13.5px; color:#1e3a5f; line-height:1.75;
  background:#f8faff; border-left:3px solid var(--blue);
  padding:8px 14px; border-radius:0 6px 6px 0; margin-bottom:10px;
}}

.article-footer {{
  display:flex; align-items:center; justify-content:space-between; margin-top:10px;
}}
.article-source {{ font-size:12px; color:var(--muted); font-weight:600; }}
.article-tags {{ display:flex; gap:6px; }}
.tag {{
  display:inline-block; padding:2px 9px; border-radius:9999px;
  font-size:11px; font-weight:600;
}}
.tag-api    {{ background:#e0f2fe; color:#0369a1; }}
.tag-tp     {{ background:#dcfce7; color:#15803d; }}
.tag-ret    {{ background:#fce7f3; color:#9d174d; }}
.tag-more   {{ background:#f3f4f6; color:#6b7280; }}

.no-data {{ text-align:center; padding:28px; color:var(--muted); font-size:13px; background:var(--card); border-radius:12px; }}

/* ── 底部 ── */
.footer {{
  text-align:center; padding:28px 20px; color:var(--muted);
  font-size:12px; border-top:1px solid var(--border); margin-top:8px;
}}
</style>
</head>
<body>

<div class="header">
  <div class="h-inner">
    <div class="h-badge">CROSS-BORDER INTELLIGENCE</div>
    <h1>跨境热点日报 <span>·</span> {date_str}</h1>
    <div class="h-meta">数据覆盖最近 {hours} 小时 · 生成于 {gen_at}</div>
    <div class="h-stats">
      <div class="h-stat"><div class="h-stat-val">{ctx["total"]}</div><div class="h-stat-lbl">收录文章</div></div>
      <div class="h-stat"><div class="h-stat-val">{ctx["source_count"]}</div><div class="h-stat-lbl">数据来源</div></div>
    </div>
  </div>
</div>

<div class="container">
{_sections_html(ctx["sections"])}
</div>

<div class="footer">
  由 <strong>17TRACK 跨境热点追踪器</strong> 自动生成 &nbsp;·&nbsp;
  数据来源：{escape("、".join(ctx["sources"][:8]) + ("..." if len(ctx["sources"]) > 8 else ""))} &nbsp;·&nbsp; AI 分析：DeepSeek
</div>

</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# 四大板块 HTML
# ─────────────────────────────────────────────────────────────

def _sections_html(sections: dict[str, list]) -> str:
    parts = []
    icons = {
        "电商平台动态":    "🏪",
        "区域物流趋势":    "🌐",
        "AI技术与新应用":  "🤖",
        "出海DTC观察":    "✨",
    }
    for sec_name, sec_en in SECTION_ORDER:
        articles = sections.get(sec_name, [])[:6]   # 每板块最多6条
        color = SECTION_COLORS.get(sec_name, "#6b7280")
        icon = icons.get(sec_name, "📌")

        if not articles:
            body_html = '<div class="no-data">暂无相关内容</div>'
        else:
            body_html = '<div class="section-body">' + "\n".join(
                _article_html(a, color) for a in articles
            ) + '</div>'

        parts.append(f"""
<div class="section">
  <div class="section-header">
    <span class="section-icon">{icon}</span>
    <span class="section-name">{escape(sec_name)}</span>
    <span class="section-en">{sec_en}</span>
    <span class="section-count">{len(articles)} 条</span>
  </div>
  {body_html}
</div>""")

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────
# 文章卡片 HTML
# ─────────────────────────────────────────────────────────────

def _article_html(a: dict, accent_color: str) -> str:
    title = escape(a.get("title", ""))
    url = escape(a.get("url", ""))

    title_html = (
        f'<div class="article-title"><a href="{url}" target="_blank">{title}</a></div>'
        if url and url != "#" else
        f'<div class="article-title">{title}</div>'
    )

    # 正文优先用深度摘要，否则用AI摘要
    deep = a.get("deep_summary", "").strip()
    basic = a.get("ai_summary_zh", "").strip()
    summary = deep if deep else basic
    summary_html = (
        f'<div class="article-summary">{escape(summary)}</div>'
        if summary else ""
    )

    # 洞察
    insight = a.get("editorial_angle", "").strip()
    if not insight:
        insight = a.get("key_insight", "").strip()
    insight_html = (
        f'<div class="article-insight">{escape(insight)}</div>'
        if insight else ""
    )

    # 来源 + 标签
    source = escape(a.get("source", ""))
    tags = a.get("product_tags", [])
    tags_html = _tags_html(tags)

    return f"""<div class="article">
  {title_html}
  {summary_html}
  {insight_html}
  <div class="article-footer">
    <span class="article-source">来源：{source}</span>
    <div class="article-tags">{tags_html}</div>
  </div>
</div>"""


def _tags_html(tags: list) -> str:
    cls_map = {"API": "tag-api", "Tracking Page": "tag-tp", "Returns": "tag-ret"}
    parts = []
    for tag in tags:
        css = cls_map.get(tag)
        if css:
            parts.append(f'<span class="tag {css}">{escape(tag)}</span>')
    if not parts:
        return ""
    return "".join(parts)
