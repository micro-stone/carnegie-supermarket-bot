#!/usr/bin/env python3
"""Carnegie 3163 超市价格监控"""
import json, time, random
from datetime import datetime
from pathlib import Path

from scraper.woolworths import get_price as ww_get
from scraper.coles      import get_price as coles_get
from scraper.aldi       import get_price as aldi_get
from scraper.notify     import send, price_change_message, daily_summary_message

WATCHLIST_FILE = Path("watchlist.json")
PRICES_FILE    = Path("data/prices.json")

def load_watchlist(): return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
def load_prices():
    return json.loads(PRICES_FILE.read_text(encoding="utf-8")) if PRICES_FILE.exists() else {}
def save_prices(p):
    PRICES_FILE.parent.mkdir(exist_ok=True)
    PRICES_FILE.write_text(json.dumps(p, indent=2, ensure_ascii=False), encoding="utf-8")

def fetch_prices(watchlist):
    snapshot = {}
    for item in watchlist:
        name, stores = item["name"], {}
        print(f"\n  → {name}")
        if ww_id := item.get("woolworths_id"):
            r = ww_get(ww_id)
            if r:
                stores["Woolworths"] = r
                print(f"    WW:    ${r['price']:.2f}{'🏷️' if r.get('on_special') else ''}  ({r['source']})")
            else: print("    WW:    ❌ 无法获取")
            time.sleep(random.uniform(1.0, 2.5))
        if q := item.get("coles_query"):
            r = coles_get(q)
            if r:
                stores["Coles"] = r
                print(f"    Coles: ${r['price']:.2f}{'🏷️' if r.get('on_special') else ''}  ({r['source']})")
            else: print("    Coles: ❌ 无法获取")
            time.sleep(random.uniform(1.0, 2.5))
        if item.get("monitor_aldi") and (kw := item.get("aldi_keyword")):
            r = aldi_get(kw)
            if r:
                stores["ALDI"] = r
                print(f"    ALDI:  ${r['price']:.2f}")
            else: print("    ALDI:  ❌ 无法获取")
            time.sleep(random.uniform(0.5, 1.5))
        snapshot[name] = stores
    return snapshot

def detect_changes(old, new, watchlist):
    thresholds = {i["name"]: i.get("alert_threshold", 0.10) for i in watchlist}
    alerts = []
    for name, stores in new.items():
        for store, data in stores.items():
            np = data.get("price"); op = old.get(name, {}).get(store, {}).get("price")
            if np is None or op is None: continue
            change = round(np - op, 2)
            if abs(change) >= thresholds.get(name, 0.10):
                alerts.append({"item": name, "store": store, "branch": data.get("branch",""),
                                "old_price": op, "new_price": np, "change": change,
                                "on_special": data.get("on_special", False)})
    return alerts

def main():
    now = datetime.now()
    print(f"[{now:%Y-%m-%d %H:%M} AEDT] Carnegie 3163 价格监控启动")
    print("门店: Woolworths Carnegie North #3298 | Coles Carnegie Central | ALDI Carnegie")
    print("─" * 60)
    watchlist  = load_watchlist()
    old_prices = load_prices()
    print("\n正在获取价格…")
    new_prices = fetch_prices(watchlist)
    print("\n" + "─" * 60)
    alerts = detect_changes(old_prices, new_prices, watchlist)
    if alerts:
        print(f"检测到 {len(alerts)} 条价格变动，发送 Telegram 通知…")
        send(price_change_message(alerts))
    else:
        print("无价格变动")
    if now.hour == 8:
        send(daily_summary_message(new_prices))
    save_prices(new_prices)
    print("✅ 完成！")

if __name__ == "__main__":
    main()
