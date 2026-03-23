"""
采集器 — RSS + 网页爬虫统一采集模块
输入：数据源配置
输出：统一格式文章列表 [{title, source, url, pub_date, excerpt, lang, source_category}]
"""

import re
import time
import calendar
import feedparser          # pip install feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from typing import Optional

from 数据源配置 import RSS_SOURCES, SCRAPE_SOURCES, KEYWORDS_ZH, KEYWORDS_EN

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

MAX_PER_SOURCE = 20
REQUEST_TIMEOUT = 15


# ─────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────

def collect_all(hours: int = 48) -> list[dict]:
    """
    从所有 RSS + 爬虫源采集文章。
    返回关键词预筛后的统一格式文章列表。
    """
    all_articles: list[dict] = []
    seen_urls: set[str] = set()

    print(f"\n{'='*55}")
    print(f"  开始采集（覆盖最近 {hours} 小时）")
    print(f"{'='*55}")

    # ── RSS 源 ──────────────────────────────────────────────────
    for source in RSS_SOURCES:
        print(f"\n[RSS] {source['name']} ...", end=" ", flush=True)
        try:
            articles = fetch_rss(source, hours=hours)
            new = _dedup(articles, seen_urls)
            all_articles.extend(new)
            print(f"OK {len(new)} pcs")
        except Exception as e:
            print(f"FAIL {e}")
        time.sleep(0.5)

    # ── 网页爬虫源 ──────────────────────────────────────────────
    for source in SCRAPE_SOURCES:
        print(f"\n[crawl] {source['name']} ...", end=" ", flush=True)
        try:
            articles = fetch_scrape(source)
            new = _dedup(articles, seen_urls)
            all_articles.extend(new)
            print(f"OK {len(new)} pcs")
        except Exception as e:
            print(f"FAIL {e}")
        time.sleep(1.5)

    # ── 关键词预筛 ──────────────────────────────────────────────
    filtered = _keyword_filter(all_articles)
    print(f"\n{'='*55}")
    print(f"  采集完成：{len(all_articles)} 篇原始 → 关键词筛选后 {len(filtered)} 篇")
    print(f"{'='*55}\n")

    return filtered


# ─────────────────────────────────────────────────────────────
# RSS 采集
# ─────────────────────────────────────────────────────────────

def fetch_rss(source: dict, hours: int = 48) -> list[dict]:
    """解析 RSS Feed，返回统一格式文章列表"""
    # 用 requests 抓内容，绕过 feedparser 内置 HTTP 的 SSL 限制
    resp = requests.get(source["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    feed = feedparser.parse(resp.content)

    if feed.bozo and not feed.entries:
        exc = getattr(feed, "bozo_exception", None)
        raise ValueError(f"RSS 解析失败: {exc}")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []

    for entry in feed.entries[:MAX_PER_SOURCE]:
        pub_date = _parse_entry_date(entry)

        # 有明确日期且超出时间窗口则跳过
        if pub_date and pub_date.tzinfo and pub_date < cutoff:
            continue

        title = _clean(entry.get("title", ""))
        url = entry.get("link", "").strip()
        if not title or not url:
            continue

        articles.append({
            "title": title,
            "source": source["name"],
            "url": url,
            "pub_date": pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else "",
            "excerpt": _rss_excerpt(entry),
            "lang": source["lang"],
            "source_category": source["category"],
        })

    return articles


# ─────────────────────────────────────────────────────────────
# 网页爬虫采集
# ─────────────────────────────────────────────────────────────

def fetch_scrape(source: dict) -> list[dict]:
    """爬取网页文章列表，返回统一格式文章列表"""
    resp = requests.get(source["url"], headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    articles = _extract_by_selectors(soup, source)

    # Fallback：若 selector 未命中，用通用提取
    if len(articles) < 3:
        articles = _generic_extract(soup, source)

    return articles[:MAX_PER_SOURCE]


def _extract_by_selectors(soup: BeautifulSoup, source: dict) -> list[dict]:
    """按配置的 CSS selector 提取文章列表"""
    selectors = source.get("selectors", {})
    base_url = source.get("base_url", "")
    articles = []

    for container_sel in selectors.get("article_list", []):
        containers = soup.select(container_sel)
        if len(containers) < 3:
            continue

        for container in containers[:MAX_PER_SOURCE]:
            article = _extract_one(container, selectors, base_url, source)
            if article:
                articles.append(article)

        if articles:
            break

    return articles


def _extract_one(
    container, selectors: dict, base_url: str, source: dict
) -> Optional[dict]:
    """从单个容器元素中提取一篇文章"""
    title, url = "", ""

    # 标题 + 链接
    for sel in selectors.get("title", []):
        el = container.select_one(sel)
        if not el:
            continue
        title = _clean(el.get_text())
        href = el.get("href", "")
        if not href and el.name != "a":
            a = el.find("a", href=True)
            href = a["href"] if a else ""
        if href:
            url = _abs_url(href, base_url)
        if title and url:
            break

    # 链接 fallback
    if not url:
        a = container.find("a", href=True)
        if a:
            title = title or _clean(a.get_text())
            url = _abs_url(a["href"], base_url)

    if not title or not url or len(title) < 6:
        return None

    # 过滤 link_contains 约束
    link_contains = source.get("link_contains")
    if link_contains and link_contains not in url:
        return None

    # 日期
    pub_date = ""
    for sel in selectors.get("date", []):
        el = container.select_one(sel)
        if el:
            pub_date = el.get("datetime") or _clean(el.get_text())
            if pub_date:
                break

    # 摘要
    excerpt = ""
    for sel in selectors.get("excerpt", []):
        el = container.select_one(sel)
        if el:
            text = _clean(el.get_text())
            if len(text) > 15:
                excerpt = text[:300]
                break

    return {
        "title": title,
        "source": source["name"],
        "url": url,
        "pub_date": pub_date,
        "excerpt": excerpt,
        "lang": source["lang"],
        "source_category": source["category"],
    }


def _generic_extract(soup: BeautifulSoup, source: dict) -> list[dict]:
    """通用 fallback：从页面所有链接中提取标题像文章的条目"""
    base_url = source.get("base_url", "")
    source_domain = urlparse(source["url"]).netloc
    link_contains = source.get("link_contains")
    articles = []
    seen: set[str] = set()

    for a in soup.find_all("a", href=True):
        title = _clean(a.get_text())
        if len(title) < 10 or len(title) > 200:
            continue

        href = a["href"]
        url = _abs_url(href, base_url)
        if not url or url in seen:
            continue

        parsed = urlparse(url)
        if parsed.netloc and source_domain not in parsed.netloc:
            continue
        if len(parsed.path) < 8:   # 路径太短 = 导航链接
            continue
        if link_contains and link_contains not in url:
            continue

        seen.add(url)
        articles.append({
            "title": title,
            "source": source["name"],
            "url": url,
            "pub_date": "",
            "excerpt": "",
            "lang": source["lang"],
            "source_category": source["category"],
        })

        if len(articles) >= MAX_PER_SOURCE:
            break

    return articles


# ─────────────────────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────────────────────

def _dedup(articles: list[dict], seen: set[str]) -> list[dict]:
    """去重，同时更新 seen 集合"""
    new = [a for a in articles if a["url"] not in seen]
    seen.update(a["url"] for a in new)
    return new


def _keyword_filter(articles: list[dict]) -> list[dict]:
    """关键词预筛：保留与跨境电商/物流相关的文章"""
    filtered = []
    for a in articles:
        text = (a.get("title", "") + " " + a.get("excerpt", "")).lower()
        kws = KEYWORDS_ZH if a.get("lang") == "zh" else KEYWORDS_EN
        if any(kw.lower() in text for kw in kws):
            filtered.append(a)
    return filtered


def _parse_entry_date(entry) -> Optional[datetime]:
    """解析 feedparser entry 的发布时间"""
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        t = getattr(entry, field, None)
        if t:
            try:
                return datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc)
            except Exception:
                continue
    return None


def _rss_excerpt(entry) -> str:
    """从 RSS entry 提取纯文本摘要"""
    raw = entry.get("summary", "")
    if not raw and entry.get("content"):
        raw = entry["content"][0].get("value", "")
    if raw:
        text = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)
        return text[:400]
    return ""


def _abs_url(href: str, base_url: str) -> str:
    """将相对路径转为绝对 URL"""
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return href
    if href.startswith("//"):
        return "https:" + href
    if base_url:
        return urljoin(base_url, href)
    return href


def _clean(text: str) -> str:
    """去除多余空白"""
    return re.sub(r"\s+", " ", text or "").strip()
