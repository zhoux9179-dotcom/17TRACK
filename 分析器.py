"""
分析器 v2 — DeepSeek AI 编辑思维分析模块

重构要点（相比 v1）：
  1. 事件级聚合：用 story_label 替代碎片关键词，热搜 = 事件，不是词
  2. 编辑思维摘要：双段式（事实段 + 分析段），附编辑视角
  3. 全局编辑简报：AI 综合当日高分文章，输出 TOP 事件与趋势判断（可选调用）
  4. 完全向后兼容：旧版 主程序.py / 报告生成器.py 无需改动即可运行
  5. 广告过滤：URL域名 + 追踪参数 + 标题话术 + AI标记 综合判定

向后兼容说明：
  - hot_keywords 字段保留（从 story_label 自动派生）
  - build_hot_topics 返回格式不变（topic/count/avg_score/heat/articles）
  - analyze_articles 接口签名和返回类型不变
  - 新增字段（story_label/editorial_angle/is_promotional）被旧报告生成器自动忽略
"""

import re
import json
import time
import os
from collections import defaultdict
from difflib import SequenceMatcher
from urllib.parse import urlparse
from openai import OpenAI
import httpx

from 数据源配置 import TOPIC_CATEGORIES

# 优先从环境变量读取（GitHub Actions / 本地勿提交密钥到仓库）
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip() or os.environ.get(
    "OPENAI_API_KEY", ""
).strip()
BATCH_SIZE = 12        # 每批处理文章数
MIN_RELEVANCE = 6      # 低于此分值不纳入报告（放宽到6分，扩大候选池）
DEEP_SUMMARY_MIN = 7   # 高于此分值才生成深度摘要


# ═════════════════════════════════════════════════════════════
# 广告 / 软文过滤
# ═════════════════════════════════════════════════════════════

# 已知的工具 / 服务商域名（非新闻站点）
_AD_DOMAINS = {
    "ziniao.com", "sellersprite.com", "lingxing.com", "solaip.com",
    "cnseller.miravia.com", "junglescout.com", "helium10.com",
    "tool4seller.com", "pacvue.com", "sellermotor.com",
    "buildmostly.com", "mayidata.com", "amztracker.com",
    "sellerapp.com", "keepa.com", "sorftime.com",
}

# URL 中典型的广告追踪参数
_AD_URL_RE = [
    re.compile(r"[?&](invite|from)=\w+"),           # invite=xxx / from=xxx
    re.compile(r"application\?source="),              # 平台招商落地页
    re.compile(r"[?&]utm_source=amz123", re.I),      # AMZ123 广告投放
    re.compile(r"[?&]utm_medium=\w+ad", re.I),       # 广告类 utm_medium
]

# 标题中的推销话术信号
_AD_TITLE_RE = [
    re.compile(r"\d+[wW万].*[卖家用户].*都在用"),
    re.compile(r"市占率第一"),
    re.compile(r"代入驻.*就选"),
    re.compile(r"现成R标"),
    re.compile(r"必备.*安全.*高效.*运营"),
    re.compile(r"每年\d+万?单免费"),
    re.compile(r"终身售后"),
    re.compile(r"免费(试用|体验|领取)"),
    re.compile(r"限时(免费|优惠|折扣)"),
    re.compile(r"立即(注册|入驻|体验|开通)"),
]

# ── 雨果网（cifnews.com）特殊过滤：平台自办活动报道 ──────────────
# 雨果网经常办峰会/训练营/直播，如果文章是它自身组织的活动报道 → 过滤
_CIFNEWS_ACTIVITY_RE = [
    re.compile(r"雨果网主办|雨果网承办|雨果网举办|雨果网协办|雨果网×"),
    re.compile(r"×\s*雨果网"),
    re.compile(r"雨果网.*报名|雨果网.*直播|雨果网.*峰会"),
    re.compile(r"报名.*雨果网|直播.*雨果网|峰会.*雨果网"),
]

# 新闻站文章路径特征（URL中包含这些则更可能是新闻）
_NEWS_PATH_SIGS = [
    "/article/", "/p/", "/newsflashes/", "/202",
    "/insights/", "/blog/", "/news/", "/feed/",
]


def filter_ads(articles: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    将文章列表拆分为 (正常新闻, 广告/软文)。
    判定依据：URL 域名 + URL 参数 + 标题话术 + AI 标记，综合打分。
    """
    news, ads = [], []
    for a in articles:
        if _is_ad(a):
            a["is_ad"] = True
            ads.append(a)
        else:
            news.append(a)
    return news, ads


def _is_ad(article: dict) -> bool:
    """综合打分判定是否为广告；>= 3 分即判定为广告"""
    url = article.get("url", "")
    title = article.get("title", "")
    score = 0

    # ① 域名命中已知工具 / 服务商
    try:
        domain = urlparse(url).netloc.lower()
        if any(d in domain for d in _AD_DOMAINS):
            score += 3
    except Exception:
        pass

    # ② URL 含广告追踪参数
    for pat in _AD_URL_RE:
        if pat.search(url):
            score += 2
            break

    # ③ URL 路径过短且不含文章路径特征（很可能是产品首页/落地页）
    try:
        path = urlparse(url).path
        if not any(s in path for s in _NEWS_PATH_SIGS) and len(path) < 20:
            score += 1
    except Exception:
        pass

    # ④ 标题含推销话术
    for pat in _AD_TITLE_RE:
        if pat.search(title):
            score += 2
            break

    # ⑤ 雨果网自办活动报道（平台自身办的峰会/直播等）
    try:
        domain = urlparse(url).netloc.lower()
        if "cifnews.com" in domain or "雨果网" in title:
            for pat in _CIFNEWS_ACTIVITY_RE:
                if pat.search(title):
                    score += 3
                    break
    except Exception:
        pass

    # ⑥ AI 在批量分析中已标记为推广
    if article.get("is_promotional"):
        score += 3

    return score >= 3


# ═════════════════════════════════════════════════════════════
# 主入口
# ═════════════════════════════════════════════════════════════

def analyze_articles(articles: list[dict], client: OpenAI = None) -> list[dict]:
    """
    批量 AI 分析文章，返回相关性 >= MIN_RELEVANCE 的富化列表。

    每篇文章新增字段：
      relevance / ai_summary_zh / deep_summary / editorial_angle /
      product_tags / topic_category / key_insight /
      story_label / hot_keywords（向后兼容）/ is_promotional
    """
    if not articles:
        return []

    if client is None:
        client = get_client()

    enriched: list[dict] = []
    total_batches = (len(articles) + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"[AI] 开始分析（共 {len(articles)} 篇，分 {total_batches} 批）")

    # ── 第一遍：批量快速分析 ─────────────────────────────
    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i : i + BATCH_SIZE]
        batch_no = i // BATCH_SIZE + 1
        print(f"  批次 {batch_no}/{total_batches}（{len(batch)} 篇）...", end=" ", flush=True)

        results = _analyze_batch(client, batch)

        kept = 0
        for article, result in zip(batch, results):
            if result.get("relevance", 0) >= MIN_RELEVANCE:
                enriched.append({**article, **result})
                kept += 1

        print(f"保留 {kept} 篇")

        if i + BATCH_SIZE < len(articles):
            time.sleep(1)

    # 按相关性降序
    enriched.sort(key=lambda x: x.get("relevance", 0), reverse=True)

    # ── 跨批次：事件标签合并 ─────────────────────────────
    _merge_story_labels(client, enriched)

    # ── 第二遍：高分文章编辑思维深度摘要 ─────────────────
    high_score = [a for a in enriched if a.get("relevance", 0) >= DEEP_SUMMARY_MIN]
    if high_score:
        print(f"[AI] 对 {len(high_score)} 篇高分文章生成编辑思维深度摘要...")
        _batch_deep_summary(client, high_score)

    print(f"  -> AI 筛选完成，保留 {len(enriched)} 篇高相关文章\n")
    return enriched


def get_client() -> OpenAI:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError(
            "未设置 DEEPSEEK_API_KEY。请在环境变量中配置 DeepSeek API Key，"
            "或在 GitHub 仓库 Secrets 中添加同名变量。"
        )
    proxies = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None
    http_client = None
    if proxies:
        http_client = httpx.Client(proxy=proxies, timeout=60.0)
    return OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com", http_client=http_client)


# ═════════════════════════════════════════════════════════════
# 第一遍：批量快速分析（事件标签 + 评分 + 摘要 + 广告标记）
# ═════════════════════════════════════════════════════════════

def _analyze_batch(client: OpenAI, batch: list[dict]) -> list[dict]:
    """调用一次 DeepSeek API 分析一批文章"""
    lines = []
    for idx, a in enumerate(batch):
        title = a.get("title", "")
        excerpt = (a.get("excerpt") or "")[:300]
        source = a.get("source", "")
        url = a.get("url", "")
        lang_hint = "（英文）" if a.get("lang") == "en" else ""
        lines.append(f"[{idx}] {source}{lang_hint} | {title} | {excerpt} | URL: {url}")

    cat_str = "、".join(TOPIC_CATEGORIES)

    prompt = f"""你是跨境物流与电商领域的资深内容编辑。请分析以下 {len(batch)} 篇文章。

分析视角：
- 这篇文章报道了什么事件/趋势？
- 它与跨境物流、电商售后、包裹追踪领域的相关性如何？
- 它对行业有什么意义？
- 它是正常新闻报道还是工具/服务商的推广软文？

【重要分类规则】—— 严格按照以下说明分类：
  · 电商平台动态：仅限亚马逊、Temu、TikTok Shop、速卖通、SHEIN、Shopee、Walmart等**全球电商平台**的政策与动态。
    纯跨境物流仓储新闻 → 归入"跨境物流动态"。
    DTC品牌报道（独立站、Shopify品牌） → 归入"出海DTC观察"。
    Temu不是DTC品牌，是平台，归入"电商平台动态"。
  · 跨境物流动态：跨境运输、仓储、清关、最后一公里配送、快递公司动态。
    **船公司**（马士基、中远、赫伯罗特、达飞等）的运力/并购/财报报道严格限制，不超过1条。
    **物流巨头**（DHL、FedEx、UPS）动态优先收录。
  · 行业报告数据：行业白皮书、调研数据、市场规模报告。
  · AI技术新应用：AI新技术（不限电商行业）、大模型、Agent、数字工具在各行业的落地。
  · 出海DTC观察：**中国品牌出海**、独立站、Shopify品牌、DTC品牌建设与增长。
    电商平台本身的政策 ≠ DTC品牌新闻。

文章列表：
{chr(10).join(lines)}

话题分类选项：{cat_str}

返回 JSON 数组，每篇文章一项：
- index: 序号（从0开始）
- relevance: 1-10分（与跨境物流/电商售后的相关性；1=完全无关，6=一般相关，9+=高度相关）
  ⚠️ 评分校准规则：
  · 9-10分：重大政策变动、行业格局性事件 —— 每批次通常不超过2条
  · 7-8分：有实质影响的行业动态
  · 5-6分：一般性行业信息、教程指南
  · 3-4分：边缘相关、间接影响
  · 广告/软文/工具推广类文章，相关度上限为 5 分
- ai_summary_zh: 中文摘要，2-3句，不超过100字（英文文章务必翻译为中文；需包含核心事件、关键数据和行业影响）
- product_tags: 涉及的产品方向，从 ["API","Tracking Page","Returns"] 中选，无关为 []
- topic_category: 从话题分类中选最匹配的一个
- key_insight: 这条新闻最核心的一句话洞察，20字以内
- story_label: ⚠️最重要字段——这篇文章报道的核心事件/趋势名称（8-25字）
  要求：
  ① 描述具体事件本身，不是抽象关键词堆叠
  ② 好的例子："FedEx因关税代收面临50亿美元集体诉讼"  "中东局势推高全球空运价格"  "百世跨境推出大件物流全链路方案"  "Prologis与GIC成立16亿美元美国物流合资企业"
  ③ 坏的例子："FedEx"  "关税"  "物流"  "空运价格"（太碎片，禁止）
  ④ 如果本批次中多篇文章报道同一事件，必须使用完全相同的 story_label
- is_promotional: 布尔值。true = 该文章本质是工具/服务/平台的推广广告或招商软文（如"XXX工具N万卖家都在用""平台入驻通道已开启""现成R标包备案"等）；false = 正常新闻报道。判断标准：文章主要目的是推销产品/服务而非报道事件或分析趋势

只返回 JSON 数组，不要其他文字：
[{{"index":0,"relevance":7,"ai_summary_zh":"...","product_tags":["API"],"topic_category":"跨境物流动态","key_insight":"...","story_label":"...","is_promotional":false}}]"""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4000,
        )
        content = _strip_fence(resp.choices[0].message.content.strip())
        raw_list = json.loads(content)

        result_map = {
            item["index"]: item
            for item in raw_list
            if isinstance(item, dict)
        }
        results = []
        for idx in range(len(batch)):
            item = result_map.get(idx, {})
            results.append(_normalize(item))
        return results

    except json.JSONDecodeError as e:
        print(f"\n  [WARN] JSON 解析失败: {e}")
    except Exception as e:
        print(f"\n  [WARN] API 调用失败: {e}")

    return [_empty_result() for _ in batch]


# ═════════════════════════════════════════════════════════════
# 跨批次：事件标签合并
# ═════════════════════════════════════════════════════════════

def _merge_story_labels(client: OpenAI, articles: list[dict]):
    """
    合并跨批次产生的相似事件标签，直接修改 articles（in-place）。
    策略：先尝试 AI 合并（更准确），失败时降级为模糊匹配。
    """
    unique_labels = list(set(
        a.get("story_label", "") for a in articles if a.get("story_label")
    ))

    if len(unique_labels) <= 1:
        return

    print(f"  [合并] 发现 {len(unique_labels)} 个事件标签，正在跨批次合并...", end=" ", flush=True)

    # AI 合并（内部已含降级逻辑）
    merge_map = _ai_merge_labels(client, unique_labels)

    if not merge_map:
        print("无需合并")
        return

    # 应用合并
    merged_count = 0
    for a in articles:
        old_label = a.get("story_label", "")
        if old_label in merge_map:
            new_label = merge_map[old_label]
            a["story_label"] = new_label
            a["hot_keywords"] = [new_label]  # 同步向后兼容字段
            merged_count += 1

    print(f"合并 {len(merge_map)} 组 → 影响 {merged_count} 篇")


def _ai_merge_labels(client: OpenAI, labels: list[str]) -> dict[str, str]:
    """用 AI 识别并合并指向同一事件的标签"""
    labels_text = "\n".join(f"  {i}. {l}" for i, l in enumerate(labels, 1))

    prompt = f"""以下是从多篇跨境电商/物流文章中提取的事件标签列表。
请识别指向同一事件的不同表述，输出合并映射。

标签列表：
{labels_text}

规则：
- 描述同一事件的不同表述应合并（保留最完整、最准确的那个作为目标标签）
- 不相关的事件不要强行合并
- 只返回需要合并的标签对，不需要合并的无需列出

返回 JSON 对象，key = 要被替换的标签，value = 保留的目标标签：
{{"需要被替换的标签": "保留的目标标签"}}

如果所有标签都指向不同事件，返回空对象 {{}}"""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )
        content = _strip_fence(resp.choices[0].message.content.strip())
        result = json.loads(content)
        if isinstance(result, dict):
            # 过滤掉自映射
            return {k: v for k, v in result.items() if k != v and k in labels}
        return {}
    except Exception as e:
        print(f"\n  [WARN] AI 标签合并失败，降级为模糊匹配: {e}")
        return _fuzzy_merge_labels(labels)


def _fuzzy_merge_labels(labels: list[str]) -> dict[str, str]:
    """基于字符串相似度的 fallback 合并"""
    merge_map = {}
    # 按长度降序，长标签优先作为主标签（通常更完整）
    sorted_labels = sorted(labels, key=len, reverse=True)
    canonicals = []  # 已确定的主标签

    for label in sorted_labels:
        merged = False
        for canonical in canonicals:
            # 子串包含
            if label in canonical or canonical in label:
                merge_map[label] = canonical
                merged = True
                break
            # 字符级相似度
            if SequenceMatcher(None, label, canonical).ratio() >= 0.55:
                merge_map[label] = canonical
                merged = True
                break

        if not merged:
            canonicals.append(label)

    return {k: v for k, v in merge_map.items() if k != v}


# ═════════════════════════════════════════════════════════════
# 第二遍：编辑思维深度摘要
# ═════════════════════════════════════════════════════════════

def _batch_deep_summary(client: OpenAI, articles: list[dict]):
    """对高分文章生成编辑思维双段式深度摘要 + 编辑视角（in-place）"""
    DEEP_BATCH = 6
    for i in range(0, len(articles), DEEP_BATCH):
        batch = articles[i : i + DEEP_BATCH]
        lines = []
        for idx, a in enumerate(batch):
            title = a.get("title", "")
            excerpt = (a.get("excerpt") or "")[:500]
            source = a.get("source", "")
            lang_hint = "（英文）" if a.get("lang") == "en" else ""
            lines.append(f"[{idx}] {source}{lang_hint}\n标题：{title}\n内容：{excerpt}")

        prompt = f"""你是跨境电商/物流领域的资深内容编辑。请对以下 {len(batch)} 篇文章逐一生成编辑级深度摘要。

要求：

1. deep_summary — 双段式摘要（总计 120-180 字）：
   第一段（事实）：核心事件经过、关键数据、涉及的公司/机构。60-90字。
   第二段（分析）：这件事对跨境电商/物流行业意味着什么？反映了什么趋势？可能带来什么后续影响？60-90字。
   两段之间用换行符分隔。英文文章必须翻译为中文。

2. editorial_angle — 编辑视角（不超过 40 字）：
   从内容编辑的角度，一句话点明这个热点为什么值得深度关注，它触及了行业的什么深层矛盾或趋势。
   好的例子："关税政策不确定性正在重塑跨境物流的成本结构与合规边界"
   好的例子："头部船司的并购扩张正在改变全球航运的竞争格局与定价权分配"
   坏的例子："这篇文章很重要"  "值得关注"（空洞，禁止）

文章列表：
{chr(10).join(lines)}

返回 JSON 数组：
[{{"index":0,"deep_summary":"第一段事实...\\n\\n第二段分析...","editorial_angle":"..."}}]"""

        try:
            resp = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=3000,
            )
            content = _strip_fence(resp.choices[0].message.content.strip())
            raw_list = json.loads(content)
            result_map = {item["index"]: item for item in raw_list if isinstance(item, dict)}
            for idx, a in enumerate(batch):
                if idx in result_map:
                    a["deep_summary"] = str(result_map[idx].get("deep_summary", ""))
                    a["editorial_angle"] = str(result_map[idx].get("editorial_angle", ""))[:80]
        except Exception as e:
            print(f"\n  [WARN] 深度摘要生成失败: {e}")

        if i + DEEP_BATCH < len(articles):
            time.sleep(1)


# ═════════════════════════════════════════════════════════════
# 第三遍（可选）：全局编辑简报
# ═════════════════════════════════════════════════════════════

def generate_editor_brief(articles: list[dict], hot_topics: list[dict] = None,
                          client: OpenAI = None) -> str:
    """
    综合当日全部高分文章，生成 200-300 字的编辑简报。

    内容：今日最重要的 3 个事件/趋势 + 宏观趋势观察。

    ⚠️ 此函数为可选功能。当前 主程序.py 不调用它，日报照常生成。
    后续升级 主程序.py 和 报告生成器.py 时再接入即可。

    调用示例：
        brief = generate_editor_brief(enriched, hot_topics)
    """
    if client is None:
        client = get_client()

    high = [a for a in articles if a.get("relevance", 0) >= DEEP_SUMMARY_MIN]
    if not high:
        return ""

    # 构建文章摘要列表
    summaries = []
    for a in high[:15]:
        title = a.get("title", "")
        summary = a.get("deep_summary") or a.get("ai_summary_zh", "")
        source = a.get("source", "")
        score = a.get("relevance", 0)
        summaries.append(f"[{score}分][{source}] {title}\n{summary}")

    # 热搜事件
    top_events = ""
    if hot_topics:
        top5 = hot_topics[:5]
        top_events = "\n\n今日热搜 TOP5 事件：\n" + "\n".join(
            f"  {i}. {t['topic']}（{t['count']}篇报道，均分{t['avg_score']}）"
            for i, t in enumerate(top5, 1)
        )

    prompt = f"""你是跨境电商/物流领域的资深主编。基于今天采集到的重要文章，请撰写一份"今日编辑简报"。

今日高分文章：
{chr(10).join(summaries)}
{top_events}

要求：
1. 提炼今日最重要的 3 个事件/趋势，每个用 2-3 句话概括核心和行业影响
2. 最后用 1-2 句话指出贯穿今日热点的宏观趋势或值得持续关注的方向
3. 总字数 200-300 字
4. 语言简洁、专业、有洞察，像资深编辑的晨会发言
5. 不要用"首先/其次/最后"等模板化过渡词

直接输出简报文本，不要 JSON 包装："""

    try:
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=1000,
        )
        brief = resp.choices[0].message.content.strip()
        print(f"  [OK] 编辑简报已生成（{len(brief)}字）")
        return brief
    except Exception as e:
        print(f"  [WARN] 编辑简报生成失败: {e}")
        return ""


# ═════════════════════════════════════════════════════════════
# 热搜话题聚合（事件级）
# ═════════════════════════════════════════════════════════════

def build_hot_topics(articles: list[dict]) -> list[dict]:
    """
    按事件级 story_label 聚合热搜话题。

    核心变化（v1 → v2）：
      v1 按碎片关键词聚合 → 一篇文章拆成 4 个"话题"
      v2 按事件标签聚合   → 同一事件的多篇报道归为一个话题

    返回格式与 v1 完全兼容：
    [{"topic": str, "count": int, "avg_score": float, "heat": float, "articles": [...]}]
    """
    story_articles = defaultdict(list)

    for a in articles:
        label = a.get("story_label", "").strip()
        if not label:
            # 降级兼容：没有 story_label 时用 hot_keywords（旧数据）
            for kw in a.get("hot_keywords", []):
                kw = kw.strip()
                if kw:
                    story_articles[kw].append(a)
            continue
        story_articles[label].append(a)

    # 构建话题列表
    topics = []
    for label, arts in story_articles.items():
        # 按 URL 去重（同一文章可能因旧数据重复出现）
        seen_urls = set()
        unique_arts = []
        for a in arts:
            url = a.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique_arts.append(a)

        if not unique_arts:
            continue

        avg_score = sum(a.get("relevance", 0) for a in unique_arts) / len(unique_arts)
        heat = len(unique_arts) * 0.6 + avg_score * 0.4

        topics.append({
            "topic": label,
            "count": len(unique_arts),
            "avg_score": round(avg_score, 1),
            "heat": round(heat, 2),
            "articles": sorted(unique_arts, key=lambda x: x.get("relevance", 0), reverse=True),
        })

    topics.sort(key=lambda x: x["heat"], reverse=True)

    # 二次安全网：合并残留的相似话题
    merged = _merge_similar_topics(topics)

    return merged[:20]


def _merge_similar_topics(topics: list[dict]) -> list[dict]:
    """最后一道安全网：合并文本相似的话题"""
    if not topics:
        return []

    merged = []
    used = set()

    for i, t in enumerate(topics):
        if i in used:
            continue

        current = dict(t)
        current["articles"] = list(t["articles"])

        for j in range(i + 1, len(topics)):
            if j in used:
                continue

            other = topics[j]
            should_merge = (
                t["topic"] in other["topic"]
                or other["topic"] in t["topic"]
                or SequenceMatcher(None, t["topic"], other["topic"]).ratio() >= 0.55
            )

            if should_merge:
                existing_urls = {a.get("url") for a in current["articles"]}
                for a in other["articles"]:
                    if a.get("url") not in existing_urls:
                        current["articles"].append(a)
                used.add(j)

        # 重算统计
        current["count"] = len(current["articles"])
        current["avg_score"] = round(
            sum(a.get("relevance", 0) for a in current["articles"]) / current["count"], 1
        )
        current["heat"] = round(current["count"] * 0.6 + current["avg_score"] * 0.4, 2)
        merged.append(current)

    merged.sort(key=lambda x: x["heat"], reverse=True)
    return merged


# ═════════════════════════════════════════════════════════════
# 工具函数
# ═════════════════════════════════════════════════════════════

def _normalize(item: dict) -> dict:
    """规范化单条分析结果"""
    valid_tags = {"API", "Tracking Page", "Returns"}
    tags = item.get("product_tags", [])
    safe_tags = [t for t in tags if t in valid_tags] if isinstance(tags, list) else []

    cat = item.get("topic_category", "")
    safe_cat = cat if cat in TOPIC_CATEGORIES else "其他"

    # story_label —— v2 核心字段
    story_label = str(item.get("story_label", ""))[:50]

    # 向后兼容：hot_keywords 从 story_label 自动派生
    hot_keywords = [story_label] if story_label else []

    return {
        "relevance":       max(0, min(10, int(item.get("relevance", 0)))),
        "ai_summary_zh":   str(item.get("ai_summary_zh", ""))[:250],
        "deep_summary":    "",   # 后续由深度摘要步骤填充
        "editorial_angle": "",   # 后续由深度摘要步骤填充
        "product_tags":    safe_tags,
        "topic_category":  safe_cat,
        "key_insight":     str(item.get("key_insight", ""))[:60],
        "story_label":     story_label,
        "hot_keywords":    hot_keywords,   # 向后兼容 v1
        "is_promotional":  bool(item.get("is_promotional", False)),
    }


def _empty_result() -> dict:
    return {
        "relevance": 0,
        "ai_summary_zh": "",
        "deep_summary": "",
        "editorial_angle": "",
        "product_tags": [],
        "topic_category": "其他",
        "key_insight": "",
        "story_label": "",
        "hot_keywords": [],
        "is_promotional": False,
    }


def _strip_fence(text: str) -> str:
    """去除 Markdown 代码块标记"""
    if "```json" in text:
        text = text.split("```json", 1)[1].rsplit("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].rsplit("```", 1)[0]
    return text.strip()