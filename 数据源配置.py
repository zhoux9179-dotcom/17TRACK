"""
数据源配置 — 跨境热点追踪器
覆盖跨境物流、全球电商、出海DTC品牌方向，共 30+ 个媒体源
"""

# ── RSS 订阅源（稳定可用，优先采集）────────────────────────────────────────────
RSS_SOURCES = [
    # ── 国内出海/跨境媒体 ──
    {
        "name": "白鲸出海",
        "url": "https://baijingapp.com/feed",
        "lang": "zh",
        "category": "出海品牌",
        "priority": 1,
    },
    {
        "name": "36氪出海",
        "url": "https://36kr.com/feed",
        "lang": "zh",
        "category": "出海综合",
        "priority": 1,
    },
    # ── 国外电商/DTC媒体 ──
    {
        "name": "Modern Retail",
        "url": "https://modernretail.co/feed",
        "lang": "en",
        "category": "DTC零售",
        "priority": 1,
    },
    {
        "name": "Digiday",
        "url": "https://digiday.com/feed",
        "lang": "en",
        "category": "数字营销",
        "priority": 1,
    },
    {
        "name": "Glossy",
        "url": "https://glossy.co/feed",
        "lang": "en",
        "category": "DTC品牌",
        "priority": 1,
    },
    {
        "name": "Shopify Blog",
        "url": "https://www.shopify.com/blog/rss",
        "lang": "en",
        "category": "独立站平台",
        "priority": 1,
    },
    # ── 国外物流/供应链媒体 ──
    {
        "name": "FreightWaves",
        "url": "https://freightwaves.com/feed",
        "lang": "en",
        "category": "跨境物流",
        "priority": 1,
    },
    {
        "name": "Supply Chain Dive",
        "url": "https://www.supplychaindive.com/feeds/news/",
        "lang": "en",
        "category": "供应链",
        "priority": 1,
    },
    {
        "name": "Retail Dive",
        "url": "https://www.retaildive.com/feeds/news/",
        "lang": "en",
        "category": "零售行业",
        "priority": 2,
    },
    {
        "name": "Digital Commerce 360",
        "url": "https://www.digitalcommerce360.com/feed/",
        "lang": "en",
        "category": "电商数据",
        "priority": 2,
    },
    # ── 新增：国外物流/电商媒体 ──
    {
        "name": "The Loadstar",
        "url": "https://theloadstar.com/feed/",
        "lang": "en",
        "category": "跨境物流",
        "priority": 1,
    },
    {
        "name": "JOC",
        "url": "https://www.joc.com/rss.xml",
        "lang": "en",
        "category": "海运物流",
        "priority": 1,
    },
    {
        "name": "Logistics Management",
        "url": "https://www.logisticsmgmt.com/rss/",
        "lang": "en",
        "category": "物流管理",
        "priority": 2,
    },
    {
        "name": "Practical Ecommerce",
        "url": "https://www.practicalecommerce.com/feed",
        "lang": "en",
        "category": "电商运营",
        "priority": 1,
    },
    {
        "name": "Multichannel Merchant",
        "url": "https://multichannelmerchant.com/feed/",
        "lang": "en",
        "category": "多渠道零售",
        "priority": 2,
    },
    {
        "name": "Ecommerce News Europe",
        "url": "https://ecommercenews.eu/feed/",
        "lang": "en",
        "category": "欧洲电商",
        "priority": 1,
    },
    {
        "name": "Internet Retailing",
        "url": "https://internetretailing.net/feed/",
        "lang": "en",
        "category": "英国电商",
        "priority": 2,
    },
]

# ── 网页爬取源（按站点结构定制）──────────────────────────────────────────────
SCRAPE_SOURCES = [
    # ── 国内媒体 ──
    {
        "name": "雨果网",
        "url": "https://www.cifnews.com/",
        "lang": "zh",
        "category": "跨境综合",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".article-item", ".news-item", ".list-item", "li.item"],
            "title": ["h2 a", "h3 a", ".title a", "a.title", "a[href*='/article/']"],
            "date": ["time", ".time", ".date", ".pub-time", ".publish-time"],
            "excerpt": [".desc", ".summary", ".excerpt", ".intro", "p"],
        },
        "base_url": "https://www.cifnews.com",
        "link_contains": "/article/",
    },
    {
        "name": "AMZ123",
        "url": "https://www.amz123.com/",
        "lang": "zh",
        "category": "亚马逊/跨境",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".news-item", ".post-item", ".list-item", ".item"],
            "title": ["h2 a", "h3 a", ".title a", "a.news-title", "a.post-title"],
            "date": ["time", ".time", ".date", ".pub-date"],
            "excerpt": [".desc", ".summary", ".intro", "p"],
        },
        "base_url": "https://www.amz123.com",
        "link_contains": None,
    },
    {
        "name": "亿邦动力",
        "url": "https://www.ebrun.com/",
        "lang": "zh",
        "category": "跨境综合",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".article-item", ".news-item", ".list-item", ".info-item"],
            "title": ["h2 a", "h3 a", ".title a", "a[href*='/ebrun/']", "a[href*='/article/']"],
            "date": ["time", ".time", ".date", ".pub-date", ".pubtime"],
            "excerpt": [".desc", ".summary", ".intro", ".detail", "p"],
        },
        "base_url": "https://www.ebrun.com",
        "link_contains": None,
    },
    {
        "name": "亿恩网",
        "url": "https://www.enewoo.com/",
        "lang": "zh",
        "category": "跨境综合",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".post", ".news-item", "li[class*='item']", ".article"],
            "title": ["h2 a", "h3 a", ".title a", "a.post-title", "a.article-title"],
            "date": ["time", ".time", ".date", ".post-date", ".entry-date"],
            "excerpt": [".excerpt", ".summary", ".intro", ".entry-summary", "p"],
        },
        "base_url": "https://www.enewoo.com",
        "link_contains": None,
    },
    {
        "name": "虎嗅",
        "url": "https://www.huxiu.com/",
        "lang": "zh",
        "category": "商业科技",
        "priority": 2,
        "selectors": {
            "article_list": ["article", ".article-item", ".story-item", ".mob-ctt", ".article-wrap"],
            "title": ["h2 a", "h3 a", ".title a", "a[href*='/article/']", "a.article-title"],
            "date": ["time", ".time", ".pub-time", ".article-time"],
            "excerpt": [".summary", ".description", ".article-summary", "p"],
        },
        "base_url": "https://www.huxiu.com",
        "link_contains": "/article/",
    },
    {
        "name": "霞光社",
        "url": "https://www.xiaguangshe.com/",
        "lang": "zh",
        "category": "出海品牌",
        "priority": 2,
        "selectors": {
            "article_list": ["article", ".post", ".news-item", ".article-card", ".card"],
            "title": ["h2 a", "h3 a", ".title a", "a.post-title"],
            "date": ["time", ".date", ".post-date"],
            "excerpt": [".excerpt", ".summary", "p"],
        },
        "base_url": "https://www.xiaguangshe.com",
        "link_contains": None,
    },
    # ── 新增国内出海/跨境媒体 ──
    {
        "name": "百晓网",
        "url": "https://www.kjwlbxs.com/hydt/hyzx.html",
        "lang": "zh",
        "category": "跨境综合",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".news-item", ".article-item", ".list-item", ".item"],
            "title": ["h2 a", "h3 a", ".title a", "a[href*='/article/']"],
            "date": ["time", ".time", ".date", ".pub-time"],
            "excerpt": [".desc", ".summary", ".excerpt", ".intro", "p"],
        },
        "base_url": "https://www.kjwlbxs.com",
        "link_contains": "/article/",
    },
    {
        "name": "品牌方舟BrandArk",
        "url": "https://www.brandark.com/",
        "lang": "zh",
        "category": "出海品牌",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".news-item", ".article-item", ".post", ".card"],
            "title": ["h2 a", "h3 a", ".title a", "a.post-title", "a[href*='/article/']"],
            "date": ["time", ".date", ".post-date", ".pub-time"],
            "excerpt": [".excerpt", ".summary", ".desc", "p"],
        },
        "base_url": "https://www.brandark.com",
        "link_contains": None,
    },
    {
        "name": "艾瑞咨询",
        "url": "https://news.iresearch.cn/",
        "lang": "zh",
        "category": "行业数据",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".news-item", ".article-item", ".report-item", ".item"],
            "title": ["h2 a", "h3 a", ".title a", "a[href*='/article/']", "a[href*='/report/']"],
            "date": ["time", ".date", ".pub-time", ".time"],
            "excerpt": [".desc", ".summary", ".excerpt", ".intro", "p"],
        },
        "base_url": "https://news.iresearch.cn",
        "link_contains": None,
    },
    {
        "name": "晚点LatePost",
        "url": "https://www.latepost.com/",
        "lang": "zh",
        "category": "商业科技",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".news-item", ".article-item", ".list-item", ".item"],
            "title": ["h2 a", "h3 a", ".title a", "a.article-title"],
            "date": ["time", ".date", ".pub-time"],
            "excerpt": [".desc", ".summary", ".excerpt", "p"],
        },
        "base_url": "https://www.latepost.com",
        "link_contains": "/article/",
    },
    # ── 国外媒体 ──
    {
        "name": "AfterShip Blog",
        "url": "https://www.aftership.com/blog",
        "lang": "en",
        "category": "竞品动态",
        "priority": 1,
        "selectors": {
            "article_list": ["article", ".blog-post", ".post-card", ".card", "[class*='post']"],
            "title": ["h2 a", "h3 a", ".post-title a", "a.card-title", "a[href*='/blog/']"],
            "date": ["time", ".date", ".post-date", ".published"],
            "excerpt": [".excerpt", ".summary", ".description", ".post-excerpt", "p"],
        },
        "base_url": "https://www.aftership.com",
        "link_contains": "/blog/",
    },
    {
        "name": "Parcel Monitor Insights",
        "url": "https://www.parcelmonitor.com/insights/",
        "lang": "en",
        "category": "包裹追踪数据",
        "priority": 2,
        "selectors": {
            "article_list": ["article", ".insight-item", ".post", ".card", "[class*='insight']"],
            "title": ["h2 a", "h3 a", ".title a", "a[href*='/insights/']"],
            "date": ["time", ".date", ".post-date"],
            "excerpt": [".excerpt", ".description", "p"],
        },
        "base_url": "https://www.parcelmonitor.com",
        "link_contains": "/insights/",
    },
]

# ── 关键词过滤（预筛相关性，减少 AI token 消耗）────────────────────────────────
KEYWORDS_ZH = [
    # 物流相关
    "跨境物流", "国际快递", "配送", "物流", "快递", "运费", "仓储",
    "清关", "海关", "关税", "头程", "尾程", "供应链", "揽收", "派送",
    "时效", "包裹", "追踪", "物流信息", "末端配送", "最后一公里",
    # 电商相关
    "跨境电商", "跨境", "出海", "独立站", "DTC", "品牌出海",
    "shopify", "亚马逊", "Amazon", "eBay", "Temu", "TikTok Shop",
    "平台", "卖家", "转化", "用户体验", "购物", "消费者",
    # 售后/退货相关
    "退货", "退款", "售后", "客服", "差评", "投诉", "纠纷",
    "包裹丢失", "延误", "赔付", "理赔", "逆向物流",
    # 品牌/营销
    "品牌", "营销", "内容营销", "增长", "获客", "留存",
]

KEYWORDS_EN = [
    # Logistics
    "shipping", "logistics", "delivery", "carrier", "freight", "parcel",
    "customs", "cross-border", "international shipping", "last mile",
    "supply chain", "fulfillment", "warehouse", "tracking", "shipment",
    # E-commerce
    "ecommerce", "e-commerce", "DTC", "direct-to-consumer", "shopify",
    "amazon", "marketplace", "seller", "brand", "omnichannel", "checkout",
    # Returns / post-purchase
    "returns", "return policy", "refund", "post-purchase", "customer experience",
    "customer service", "lost package", "delayed", "reverse logistics",
    # Trends
    "trend", "report", "data", "growth", "consumer behavior", "retail",
]

# ── 产品线关键词映射 ──────────────────────────────────────────────────────────
PRODUCT_KEYWORDS = {
    "API": [
        "API", "webhook", "integration", "developer", "接口", "开发者",
        "数据对接", "系统集成", "自动化", "automation", "SDK", "plugin",
    ],
    "Tracking Page": [
        "tracking page", "track order", "branded tracking", "品牌追踪页",
        "追踪页面", "order status", "shipment tracking", "package tracking",
        "post-purchase page", "delivery tracking", "物流追踪",
    ],
    "Returns": [
        "returns", "return management", "return portal", "退货管理",
        "退货流程", "reverse logistics", "return policy", "refund",
        "逆向物流", "退货率", "return experience", "返品",
    ],
}

# ── 话题分类 ──────────────────────────────────────────────────────────────────
# 分类定义须与四大板块严格对应
TOPIC_CATEGORIES = [
    "电商平台动态",   # 亚马逊、Temu、TikTok Shop、速卖通、SHEIN、Shopee等全球平台政策/动态
    "跨境物流动态",   # 跨境物流、仓储、清关、最后一公里；不包含纯船公司并购/运力报道
    "行业报告数据",   # 行业报告、调研数据、市场洞察
    "AI技术新应用",   # AI新技术在各行业（不限电商）的应用；大模型、Agent、数字化工具
    "出海DTC观察",   # 中国品牌出海、独立站、DTC品牌建设；不等于电商平台
]
