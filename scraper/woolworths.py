"""
Woolworths 爬虫 — cloudscraper 版
模拟浏览器 TLS 指纹绕过 Cloudflare，完全不需要安装浏览器。

三级降级策略（自动切换）：
  1. JSON API  (/apis/ui/product/detail)  — 最快
  2. HTML &q;  编码 JSON                  — API 被拦时的备用
  3. Next.js __NEXT_DATA__ script 标签   — 最后手段
"""
import re
import json
import cloudscraper

STORE_ID = "3298"   # Woolworths Carnegie North
POSTCODE = "3163"

# 全局复用同一个 scraper 实例（复用 session，减少握手次数）
_scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "darwin", "mobile": False}
)

_BASE_HEADERS = {
    "Accept":          "application/json, text/html, */*",
    "Accept-Language": "en-AU,en;q=0.9",
    "Referer":         "https://www.woolworths.com.au/",
    # Cookie 把门店设为 Carnegie North，使 Specials 显示该门店价格
    "Cookie":          f"wow-store-id={STORE_ID}; wow-postcode={POSTCODE}",
}


def get_price(product_id: str) -> dict | None:
    result = _try_api(product_id)
    if result:
        return result
    print(f"    [WW] JSON API 无数据，降级到 HTML 提取…")
    return _try_html(product_id)


# ── 策略 1：JSON API ──────────────────────────────────────────────────────────

def _try_api(product_id: str) -> dict | None:
    url = f"https://www.woolworths.com.au/apis/ui/product/detail/{product_id}"
    try:
        r = _scraper.get(url, headers=_BASE_HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        data = r.json()
        p = data.get("Product") or (data[0] if isinstance(data, list) else data)
        price = p.get("Price")
        if not price:
            return None
        return _build(
            name=p.get("Name", ""),
            price=float(price),
            was=p.get("WasPrice"),
            special=bool(p.get("IsOnSpecial")),
            cup=p.get("CupString", ""),
            src="json_api",
        )
    except Exception as e:
        print(f"    [WW] API 异常: {e}")
        return None


# ── 策略 2 + 3：HTML 页面 ─────────────────────────────────────────────────────

def _try_html(product_id: str) -> dict | None:
    url = f"https://www.woolworths.com.au/shop/productdetails/{product_id}"
    try:
        r = _scraper.get(
            url,
            headers={**_BASE_HEADERS, "Accept": "text/html"},
            timeout=20,
        )
        html = r.text
        return _parse_encoded(html, product_id) or _parse_next_data(html, product_id)
    except Exception as e:
        print(f"    [WW] HTML 异常: {e}")
        return None


def _parse_encoded(html: str, pid: str) -> dict | None:
    """&q;Price&q;:2.9 这种 HTML 转义 JSON（Woolworths 常见嵌入方式）"""
    c = html.replace("&q;", '"').replace("&amp;", "&")
    pm = re.search(r'"Price"\s*:\s*([\d.]+)', c)
    if not pm:
        return None
    return _build(
        name=_rx(r'"Name"\s*:\s*"([^"]{3,100})"', c, f"WW-{pid}"),
        price=float(pm.group(1)),
        was=float(_rx(r'"WasPrice"\s*:\s*([\d.]+)', c) or 0) or None,
        special=_rx(r'"IsOnSpecial"\s*:\s*(true|false)', c) == "true",
        cup=_rx(r'"CupString"\s*:\s*"([^"]*)"', c, ""),
        src="html_encoded",
    )


def _parse_next_data(html: str, pid: str) -> dict | None:
    """Next.js __NEXT_DATA__ 嵌入 JSON"""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.+?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        props = data.get("props", {}).get("pageProps", {})
        p = props.get("product") or props.get("initialData", {}).get("product")
        if not p:
            return None
        price = p.get("price") or p.get("Price")
        if not price:
            return None
        return _build(
            name=p.get("name") or p.get("Name", f"WW-{pid}"),
            price=float(price),
            was=p.get("wasPrice") or p.get("WasPrice"),
            special=bool(p.get("isOnSpecial") or p.get("IsOnSpecial")),
            cup="",
            src="next_data",
        )
    except Exception:
        return None


# ── 工具 ──────────────────────────────────────────────────────────────────────

def _rx(pattern: str, text: str, default=None):
    m = re.search(pattern, text)
    return m.group(1) if m else default


def _build(name, price, was, special, cup, src) -> dict:
    return {
        "store":      "Woolworths",
        "branch":     "Carnegie North #3298",
        "name":       name,
        "price":      price,
        "was_price":  was,
        "unit_price": cup,
        "on_special": special,
        "source":     src,
    }
