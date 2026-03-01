"""
Woolworths 爬虫 — Playwright 版
使用无头浏览器，完全模拟真实用户，绕过 Bot 检测
"""
import re
import json
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Carnegie North store ID 通过 Cookie 传入
STORE_ID = "3298"

def get_price(product_id: str) -> dict | None:
    """
    用 Playwright 打开 Woolworths 商品页面，提取嵌入在 HTML 里的 JSON 价格数据。
    HTML 底部有类似这样的数据：
      &q;Price&q;:2.9,&q;WasPrice&q;:3.5,&q;IsOnSpecial&q;:true
    """
    url = f"https://www.woolworths.com.au/shop/productdetails/{product_id}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            # 设置澳洲 UA + 视窗，减少被识别为 Bot 的概率
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-AU",
            timezone_id="Australia/Melbourne",
        )
        # 设置 Carnegie North store cookie
        context.add_cookies([
            {
                "name": "wow-store-id",
                "value": STORE_ID,
                "domain": ".woolworths.com.au",
                "path": "/",
            },
            {
                "name": "wow-postcode",
                "value": "3163",
                "domain": ".woolworths.com.au",
                "path": "/",
            },
        ])

        page = context.new_page()
        result = None

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # 等待价格元素出现（CSS 选择器可能因版本不同而异，多试几个）
            try:
                page.wait_for_selector(
                    "shared-price, [class*='price'], [data-testid*='price']",
                    timeout=8_000,
                )
            except PlaywrightTimeout:
                pass  # 超时无所谓，继续从 HTML 提取

            html = page.content()

            # 方法1：提取 HTML 末尾的 &q; 编码 JSON（最可靠）
            cleaned = html.replace("&q;", '"').replace("&amp;", "&")
            result = _extract_from_encoded_json(cleaned, product_id)

            # 方法2：如果方法1没拿到，尝试提取 Next.js __NEXT_DATA__ JSON
            if not result:
                result = _extract_from_next_data(html, product_id)

            # 方法3：直接用 CSS 提取页面上可见的价格文字
            if not result:
                result = _extract_from_visible_price(page, product_id)

        except PlaywrightTimeout:
            print(f"  [WW] 页面加载超时: {product_id}")
        except Exception as e:
            print(f"  [WW] 意外错误: {e}")
        finally:
            browser.close()

        return result


def _extract_from_encoded_json(cleaned_html: str, product_id: str) -> dict | None:
    """从 &q; 编码的 JSON 中提取价格（Woolworths 的主要嵌入方式）"""
    price_m = re.search(r'"Price":([\d.]+)', cleaned_html)
    was_m = re.search(r'"WasPrice":([\d.]+)', cleaned_html)
    name_m = re.search(r'"Name":"([^"]{3,80})"', cleaned_html)
    special_m = re.search(r'"IsOnSpecial":(true|false)', cleaned_html)

    if price_m:
        return {
            "store": "Woolworths",
            "branch": "Carnegie North #3298",
            "name": name_m.group(1) if name_m else f"Product {product_id}",
            "price": float(price_m.group(1)),
            "was_price": float(was_m.group(1)) if was_m else None,
            "on_special": special_m and special_m.group(1) == "true",
            "source": "html_encoded_json",
        }
    return None


def _extract_from_next_data(html: str, product_id: str) -> dict | None:
    """从 Next.js __NEXT_DATA__ script 标签提取（较新页面结构）"""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
        # 路径会因页面版本不同而异，逐层找 price
        props = data.get("props", {}).get("pageProps", {})
        product = props.get("product") or props.get("initialData", {}).get("product")
        if not product:
            return None
        price = product.get("price") or product.get("Price")
        if price:
            return {
                "store": "Woolworths",
                "branch": "Carnegie North #3298",
                "name": product.get("name") or product.get("Name", f"Product {product_id}"),
                "price": float(price),
                "was_price": product.get("wasPrice") or product.get("WasPrice"),
                "on_special": product.get("isOnSpecial") or product.get("IsOnSpecial", False),
                "source": "next_data",
            }
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def _extract_from_visible_price(page, product_id: str) -> dict | None:
    """最后手段：直接读页面上可见的价格文字"""
    selectors = [
        "[data-testid='product-price']",
        "shared-price .price--large",
        "[class*='ProductPrice']",
        "span.price",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.count() > 0:
                text = el.inner_text(timeout=2000)
                m = re.search(r"\$?([\d]+\.[\d]{2})", text)
                if m:
                    return {
                        "store": "Woolworths",
                        "branch": "Carnegie North #3298",
                        "name": f"Product {product_id}",
                        "price": float(m.group(1)),
                        "was_price": None,
                        "on_special": False,
                        "source": "visible_text",
                    }
        except Exception:
            continue
    return None
