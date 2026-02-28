"""
ALDI Carnegie — 全国统一价，无需门店 ID。
通过爬取 aldi.com.au 商品分类页面获取价格。

Carnegie Central 和 Glen Huntly 两家 ALDI 价格完全相同，
爬一次即可。
"""
import requests
import re
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-AU,en;q=0.9",
}

# ALDI 分类页面 URL 映射（关键词 -> 分类 URL）
# 在 aldi.com.au 找到对应分类页面后填写
CATEGORY_URLS = {
    "milk":        "https://www.aldi.com.au/en/groceries/dairy-eggs-chilled/milk/",
    "eggs":        "https://www.aldi.com.au/en/groceries/dairy-eggs-chilled/eggs/",
    "bread":       "https://www.aldi.com.au/en/groceries/bakery/bread/",
    "butter":      "https://www.aldi.com.au/en/groceries/dairy-eggs-chilled/butter-spreads/",
    "chicken":     "https://www.aldi.com.au/en/groceries/meat-seafood/",
}


def get_price(keyword: str) -> dict | None:
    """
    根据关键词在对应分类页面查找 ALDI 价格。
    keyword 示例: "full cream milk", "eggs", "white bread", "butter"
    """
    # 找匹配的分类 URL
    category_url = None
    kw_lower = keyword.lower()
    for key, url in CATEGORY_URLS.items():
        if key in kw_lower:
            category_url = url
            break

    if not category_url:
        print(f"  [ALDI] 未找到 '{keyword}' 的分类 URL，请在 aldi.py 中添加")
        return None

    return _scrape(category_url, keyword)


def _scrape(url: str, keyword: str) -> dict | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # ALDI 商品卡片 — 选择器可能随网站更新而变化
        # 优先尝试新版结构，再尝试旧版
        product_cards = (
            soup.select(".ft-product-tile")
            or soup.select(".product-tile")
            or soup.select("[class*='ProductTile']")
            or soup.select("article")
        )

        kw_lower = keyword.lower()
        for card in product_cards:
            # 提取商品名
            name_el = (
                card.select_one("[class*='name']")
                or card.select_one("h3")
                or card.select_one("h2")
            )
            if not name_el:
                continue
            name = name_el.get_text(strip=True)

            # 关键词匹配（任意词匹配即可）
            kw_words = kw_lower.split()
            if not any(w in name.lower() for w in kw_words):
                continue

            # 提取价格
            price_el = card.select_one("[class*='price']") or card.select_one("[class*='Price']")
            if not price_el:
                continue
            price_text = price_el.get_text(strip=True)
            price_match = re.search(r"\$\s*([\d]+\.[\d]{2})", price_text)
            if price_match:
                return {
                    "store": "ALDI",
                    "branch": "Carnegie Central / Glen Huntly (统一价)",
                    "name": name,
                    "price": float(price_match.group(1)),
                    "was_price": None,
                    "on_special": False,
                    "note": "全国统一价",
                }

        print(f"  [ALDI] 页面中未匹配到 '{keyword}'（CSS 结构可能已更新）")
        return None

    except Exception as e:
        print(f"  [ALDI] 抓取失败 ({url}): {e}")
        return None
