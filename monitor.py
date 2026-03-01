#!/usr/bin/env python3
"""
Carnegie 3163 超市价格监控主程序
门店：Woolworths Carnegie North (3298) | Coles Carnegie Central | ALDI Carnegie
"""
import json
import time
import random
from datetime import datetime
from pathlib import Path

from scraper.woolworths import get_price as ww_get
from scraper.coles import get_price as coles_get
from scraper.aldi import get_price as aldi_get
from scraper.notify import send, price_change_message, daily_summary_message

WATCHLIST_FILE = Path("watchlist.json")
PRICES_FILE = Path("data/prices.json")


def load_watchlist() -> list:
    return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))


def load_prices() -> dict:
    if PRICES_FILE.exists():
        return json.loads(PRICES_FILE.read_text(encoding="utf-8"))
    return {}


def save_prices(prices: dict):
    PRICES_FILE.parent.mkdir(exist_ok=True)
    PRICES_FILE.write_text(
        json.dumps(prices, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def fetch_prices(watchlist: list) -> dict:
    """获取所有监控商品的当前价格"""
    snapshot = {}

    for item in watchlist:
        name = item["name"]
        stores = {}
        print(f"  → {name}")

        # Woolworths Carnegie North
        if item.get("woolworths_id"):
            r = ww_get(item["woolworths_id"])
            if r:
                stores["Woolworths"] = {
                    "price": r["price"],
                    "was_price": r.get("was_price"),
                    "on_special": r.get("on_special", False),
                    "branch": r["branch"],
                }
                print(f"    WW:    ${r['price']:.2f}" + (" 🏷️" if r.get("on_special") else ""))

        time.sleep(random.uniform(0.8, 1.8))

        # Coles Carnegie Central
        if item.get("coles_query"):
            r = coles_get(item["coles_query"])
            if r:
                stores["Coles"] = {
                    "price": r["price"],
                    "was_price": r.get("was_price"),
                    "on_special": r.get("on_special", False),
                    "branch": r["branch"],
                }
                print(f"    Coles: ${r['price']:.2f}" + (" 🏷️" if r.get("on_special") else ""))

        time.sleep(random.uniform(0.8, 1.8))

        # ALDI（全国统一价）
        if item.get("monitor_aldi") and item.get("aldi_keyword"):
            r = aldi_get(item["aldi_keyword"])
            if r:
                stores["ALDI"] = {
                    "price": r["price"],
                    "was_price": None,
                    "on_special": False,
                    "branch": r["branch"],
                }
                print(f"    ALDI:  ${r['price']:.2f}")

        snapshot[name] = stores

    return snapshot


def detect_changes(old: dict, new: dict, watchlist: list) -> list:
    threshold_map = {item["name"]: item.get("alert_threshold", 0.10) for item in watchlist}
    alerts = []

    for name, stores in new.items():
        threshold = threshold_map.get(name, 0.10)
        old_stores = old.get(name, {})

        for store_name, data in stores.items():
            new_price = data.get("price")
            old_price = old_stores.get(store_name, {}).get("price")

            if new_price is None or old_price is None:
                continue

            change = new_price - old_price
            if abs(change) >= threshold:
                alerts.append({
                    "item": name,
                    "store": store_name,
                    "branch": data.get("branch", ""),
                    "old_price": old_price,
                    "new_price": new_price,
                    "change": change,
                    "on_special": data.get("on_special", False),
                })

    return alerts


def main():
    now = datetime.now()
    print(f"[{now:%Y-%m-%d %H:%M AEST}] Carnegie 3163 价格监控启动")
    print("门店: Woolworths Carnegie North #3298 | Coles Carnegie Central | ALDI Carnegie\n")

    watchlist = load_watchlist()
    old_prices = load_prices()

    print("正在获取价格...")
    new_prices = fetch_prices(watchlist)

    # 检测变动
    alerts = detect_changes(old_prices, new_prices, watchlist)

    if alerts:
        print(f"\n检测到 {len(alerts)} 条价格变动，发送 Telegram 通知...")
        msg = price_change_message(alerts)
        send(msg)
    else:
        print("\n无价格变动")

    # 每天 8:00 发送汇总
    if now.hour == 8:
        print("发送每日价格汇总...")
        send(daily_summary_message(new_prices))

    save_prices(new_prices)
    print("完成！价格已保存。")


if __name__ == "__main__":
    main()
