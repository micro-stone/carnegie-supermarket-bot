import requests
import json

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.coles.com.au",
    "Referer": "https://www.coles.com.au/",
}

# Coles Carnegie Central 的 store ID
# 通过 https://www.coles.com.au/api/2.0/stores/search?latitude=-37.884&longitude=145.058&radius=1000
# 查询后硬编码（如果下面的 ID 不对会自动回退到无 store ID 查询）
COLES_CARNEGIE_STORE_ID = "7724"


def get_price(query: str) -> dict | None:
    """搜索 Coles 商品，返回 Carnegie Central 门店价格"""
    # 先尝试带 store ID 查询
    result = _search(query, store_id=COLES_CARNEGIE_STORE_ID)
    if result:
        return result
    # 如果 store ID 不对导致无结果，fallback 到无 store ID
    print(f"  [Coles] store ID {COLES_CARNEGIE_STORE_ID} 查询无结果，使用通用查询")
    return _search(query, store_id=None)


def _search(query: str, store_id: str | None) -> dict | None:
    url = "https://www.coles.com.au/api/2.0/market/products"
    params = {"q": query, "page": 1, "pageSize": 5}
    if store_id:
        params["storeId"] = store_id

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            return None

        item = results[0]
        pricing = item.get("pricing", {})
        price = pricing.get("now")
        if not price:
            return None

        return {
            "store": "Coles",
            "branch": "Carnegie Central",
            "name": item.get("name", ""),
            "price": float(price),
            "was_price": pricing.get("was"),
            "unit_price": pricing.get("unit", {}).get("ofMeasurePrice", ""),
            "on_special": pricing.get("promotionType") is not None,
        }
    except Exception as e:
        print(f"  [Coles] 搜索 '{query}' 失败: {e}")
        return None
