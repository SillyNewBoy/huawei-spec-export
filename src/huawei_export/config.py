"""站点、品类与系列归类的集中配置。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchQueryConfig:
    keyword: str
    category_id: int | None = None
    allowed_category_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CategoryConfig:
    key: str
    name: str
    keyword: str
    category_id: int | None = None
    search_queries: tuple[SearchQueryConfig, ...] = ()

    @property
    def queries(self) -> tuple[SearchQueryConfig, ...]:
        if self.search_queries:
            return self.search_queries
        return (
            SearchQueryConfig(
                keyword=self.keyword,
                category_id=self.category_id,
            ),
        )


@dataclass(frozen=True)
class SearchProduct:
    product_id: str
    product_name: str
    sku_code: str
    sku_name: str
    category_code: str | None
    raw: dict

    @property
    def product_url(self) -> str:
        return f"https://www.vmall.com/product/{self.product_id}.html"


# ---------------------------------------------------------------------------
# 华为商城 VMALL（国内）品类
# ---------------------------------------------------------------------------
VMALL_CATEGORY_PRESETS = {
    "phones": {"name": "手机", "keyword": "手机", "category_id": 100507},
    "tablets": {"name": "平板电脑", "keyword": "平板", "category_id": 100515},
    "wearables": {
        "name": "手表",
        "keyword": "手表",
        "category_id": None,
        "search_queries": (
            SearchQueryConfig(keyword="手表", category_id=100523, allowed_category_codes=("290101",)),
            SearchQueryConfig(keyword="手环", category_id=100525, allowed_category_codes=("290102",)),
            SearchQueryConfig(keyword="儿童手表", category_id=102292, allowed_category_codes=("290103",)),
        ),
    },
    "audio": {
        "name": "耳机音箱",
        "keyword": "耳机音箱",
        "category_id": None,
        "search_queries": (
            SearchQueryConfig(keyword="耳机", category_id=100559, allowed_category_codes=("310205",)),
            SearchQueryConfig(keyword="智能音箱", category_id=100561, allowed_category_codes=("310206",)),
            SearchQueryConfig(keyword="智能眼镜", category_id=100620, allowed_category_codes=("310218",)),
            SearchQueryConfig(keyword="有线耳机", category_id=100591, allowed_category_codes=("310213",)),
        ),
    },
    "laptops": {"name": "笔记本电脑", "keyword": "笔记本", "category_id": 100519},
    "routers": {
        "name": "路由器",
        "keyword": "路由",
        "category_id": None,
        "search_queries": (
            SearchQueryConfig(keyword="路由", category_id=100529, allowed_category_codes=("300101",)),
            SearchQueryConfig(keyword="随行WiFi", category_id=100533, allowed_category_codes=("300103",)),
            SearchQueryConfig(keyword="移动路由", category_id=100533, allowed_category_codes=("300103",)),
            SearchQueryConfig(keyword="移动路由", category_id=101800, allowed_category_codes=("640101",)),
        ),
    },
    "smart_screens": {"name": "智慧屏", "keyword": "智慧屏", "category_id": 100636},
    "printers": {"name": "打印机", "keyword": "打印机", "category_id": 101086},
    "monitors": {"name": "显示器", "keyword": "显示器", "category_id": 100848},
    "cars": {"name": "汽车", "keyword": "汽车", "category_id": None},
}

# ---------------------------------------------------------------------------
# 华为消费者官网 consumer.huawei.com 品类（path 为官网栏目路径）
# ---------------------------------------------------------------------------
CONSUMER_CATEGORY_PRESETS = {
    "phones": {"name": "手机", "path": "phones"},
    "tablets": {"name": "平板电脑", "path": "tablets"},
    "wearables": {"name": "穿戴设备", "path": "wearables"},
    "laptops": {"name": "笔记本电脑", "path": "laptops"},
    "headphones": {"name": "耳机", "path": "headphones"},
    "speakers": {"name": "音箱", "path": "speakers"},
    "routers": {"name": "路由器", "path": "routers"},
    "monitors": {"name": "显示器", "path": "monitors"},
    "printers": {"name": "打印机", "path": "printers"},
    "visions": {"name": "智慧屏", "path": "visions"},
}

# consumer 官网产品名 -> 系列归类规则（按顺序匹配，命中即止，不区分大小写）
CONSUMER_SERIES_RULES: tuple[tuple[str, str], ...] = (
    ("mate xt", "Mate XT 系列"),
    ("mate xs", "Mate X 系列"),
    ("mate x", "Mate X 系列"),
    ("matebook", "MateBook 系列"),
    ("matepad", "MatePad 系列"),
    ("matestation", "MateStation 系列"),
    ("mateview", "MateView 系列"),
    ("mate ", "Mate 系列"),
    ("pura", "Pura 系列"),
    ("nova", "nova 系列"),
    ("enjoy", "畅享系列"),
    ("畅享", "畅享系列"),
    ("智选", "智选系列"),
    ("擎云", "擎云系列"),
    ("watch gt", "WATCH GT 系列"),
    ("watch fit", "WATCH FIT 系列"),
    ("watch d", "WATCH D 系列"),
    ("watch ultimate", "WATCH ULTIMATE 系列"),
    ("watch kids", "儿童手表系列"),
    ("watch", "WATCH 系列"),
    ("band", "手环系列"),
    ("freebuds", "FreeBuds 系列"),
    ("freeclip", "FreeClip 系列"),
    ("freearc", "FreeArc 系列"),
    ("freelace", "FreeLace 系列"),
    ("sound", "Sound 系列"),
    ("vision", "智慧屏系列"),
    ("pixlab", "打印机系列"),
    ("wifi", "路由系列"),
)

CONSUMER_DEFAULT_SERIES_NAME = "其他"
