"""
Coles 爬虫 — Playwright + 网络拦截版

Coles 的 API BASE_URL 是动态轮换的（如 https://xxx.coles.com.au），
无法硬编码。解决方案：让 Playwright 打开搜索页，拦截真实的 XHR 请求，
直接从响应里拿价格数据，不需要知道 BASE_URL。
"""
import json
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Coles Carnegie Central store ID（影响特价显示）
# 如果搜索结果为空，会自动降级为无 store ID
COLES_STORE_ID = "7724"


def get_price(query: str) -> dict | None:
    """
    打开 Coles 搜索页，拦截商品 JSON API 响应，提取第一个匹配商品的价格。
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-AU",
            timezone_id="Australia/Melbourne",
        )
        page = context.new_page()
        captured = []

        def handle_response(response):
            """拦截所有 XHR/Fetch 响应，找包含商品数据的那个"""
            url = response.url
            # Coles 商品搜索响应的 URL 特征
            if "products.json" in url or "products/search" in url or (
                "coles.com.au" in url and "product" in url and response.request.method == "GET"
            ):
                try:
                    data = response.json()
                    if data:
                        captured.append(data)
                except Exception:
                    pass

        page.on("response", handle_response)

        search_url = (
            f"https://www.coles.com.au/search?q={query.replace(' ', '+')}"
        )
        if COLES_STORE_ID:
            # 通过 Cookie 设置门店
            context.add_cookies([{
                "name": "coles_store_id",
                "value": COLES_STORE_ID,
                "domain": ".coles.com.au",
                "path": "/",
            }])

        result = None
        try:
            page.goto(search_url, wait_until="networkidle", timeout=30_000)

            # 等待商品卡片渲染
            try:
                page.wait_for_selector(
                    "[data-testid='product-tile'], [class*='ProductTile'], article[class*='product']",
                    timeout=10_000,
                )
            except PlaywrightTimeout:
                pass

            # 先尝试从拦截到的 XHR 数据提取
            for data in captured:
                result = _parse_coles_api_response(data)
                if result:
                    break

            # 如果 XHR 没拦截到，直接从页面 HTML 提取
            if not result:
                result = _extract_from_page(page)

        except PlaywrightTimeout:
            print(f"  [Coles] 搜索页超时: '{query}'")
        except Exception as e:
            print(f"  [Coles] 意外错误: {e}")
        finally:
            browser.close()

        return result


def _parse_coles_api_response(data: dict) -> dict | None:
    """解析 Coles API JSON 响应（多种结构格式）"""
    # 格式 1: {"results": [...]}
    results = data.get("results") or data.get("products") or []
    if isinstance(results, list) and results:
        item = results[0]
        pricing = item.get("pricing", {})
        price = pricing.get("now") or item.get("price") or item.get("Price")
        if price:
            return {
                "store": "Coles",
                "branch": "Carnegie Central",
                "name": item.get("name") or item.get("Name", ""),
                "price": float(price),
                "was_price": pricing.get("was"),
                "on_special": pricing.get("promotionType") is not None,
                "source": "xhr_intercept",
            }
    return None


def _extract_from_page(page) -> dict | None:
    """从 Coles 搜索结果页直接提取第一个商品的价格"""
    selectors_price = [
        "[data-testid='product-pricing'] .price__value",
        "[class*='price'] .price__value",
        "[data-testid='list-item-price']",
        "span[class*='price--']",
    ]
    selectors_name = [
        "[data-testid='product-name']",
        "h2[class*='ProductTitle']",
        "[class*='product-name']",
        "h2.product__title",
    ]

    name = None
    for sel in selectors_name:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                name = el.inner_text(timeout=2000).strip()
                break
        except Exception:
            continue

    for sel in selectors_price:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                text = el.inner_text(timeout=2000)
                m = re.search(r"\$?([\d]+\.[\d]{2})", text)
                if m:
                    return {
                        "store": "Coles",
                        "branch": "Carnegie Central",
                        "name": name or "Unknown",
                        "price": float(m.group(1)),
                        "was_price": None,
                        "on_special": False,
                        "source": "page_dom",
                    }
        except Exception:
            continue
    return None
