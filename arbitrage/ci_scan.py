#!/usr/bin/env python
"""CI-сканер арбитража (Skinport -> Steam) для GitHub Actions.
Живёт в arbitrage/ репозитория; пишет arbitrage/data.json для панели."""
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import quote

import sources
from config import (DEALS_LIMIT, MIN_PROFIT, MIN_ROI, MIN_VOL, PRIORITY_ITEMS,
                    PRICE_MAX, PRICE_MIN, SKINPORT_FEE, STEAM_FEE,
                    STEAM_MAX_FAILS, STEAM_TTL)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "cache", "steam_prices.json")
DATA_PATH = os.path.join(BASE_DIR, "data.json")

BUDGET = int(os.environ.get("STEAM_BUDGET", "100"))
STEAM_DELAY = float(os.environ.get("STEAM_DELAY", "3.0"))
FAIL_COOLDOWN = 3600
CACHE_TTL = 30 * 86400


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_cache():
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def candidates(cache, catalog):
    now = time.time()
    prio = set(PRIORITY_ITEMS)
    cands = []
    for name, it in catalog.items():
        if not (PRICE_MIN <= it["min_price"] <= PRICE_MAX):
            continue
        c = cache.get(name)
        if c:
            if c.get("fails", 0) >= STEAM_MAX_FAILS and now - c.get("ts_fail", 0) < FAIL_COOLDOWN:
                continue
            if c.get("price") and now - c.get("ts", 0) <= STEAM_TTL:
                continue
        score = 0.0
        if name in prio:
            score -= 1_000_000
        if c and c.get("price"):
            score -= min(c["price"], 500)
        score -= min(it["qty"], 300) * 2.0
        cands.append((score, name))
    cands.sort()
    return [n for _, n in cands]


def main():
    print("== ARB SCAN START", now_iso())
    raw = sources.fetch_skinport()
    catalog = {}
    for x in raw:
        name = x.get("market_hash_name")
        mp = x.get("min_price")
        if not name or mp is None:
            continue
        catalog[name] = {"min_price": float(mp),
                         "qty": int(x.get("quantity") or 0),
                         "suggested": x.get("suggested_price")}
    print("Skinport catalog:", len(catalog), "items")

    cache = load_cache()
    todo = candidates(cache, catalog)
    print("Steam queue:", len(todo), "| budget:", BUDGET)

    fetched = fails = r429 = 0
    for i, name in enumerate(todo):
        if i >= BUDGET:
            break
        try:
            res = sources.fetch_steam(name)
        except sources.RateLimited:
            r429 += 1
            time.sleep(30)
            continue
        except Exception as e:
            fails += 1
            print("  ERR", name, e)
            c = cache.get(name) or {}
            c["fails"] = c.get("fails", 0) + 1
            c["ts_fail"] = int(time.time())
            cache[name] = c
            continue
        if res and res["price"]:
            cache[name] = {"price": res["price"], "volume": res["volume"],
                           "ts": int(time.time()), "fails": 0}
            fetched += 1
        else:
            c = cache.get(name) or {}
            c["fails"] = c.get("fails", 0) + 1
            c["ts_fail"] = int(time.time())
            cache[name] = c
            fails += 1
        time.sleep(STEAM_DELAY)

    now = time.time()
    for n in list(cache.keys()):
        if n not in catalog and now - cache[n].get("ts", 0) > CACHE_TTL:
            del cache[n]

    deals = []
    passing = 0
    for name, it in catalog.items():
        c = cache.get(name)
        if not c or not c.get("price"):
            continue
        if now - c["ts"] > STEAM_TTL * 3:
            continue
        buy = it["min_price"] * (1 + SKINPORT_FEE)
        net = c["price"] / (1 + STEAM_FEE)
        profit = net - buy
        roi = (profit / buy * 100) if buy > 0 else 0.0
        vol = c.get("volume") or 0
        ok = roi >= MIN_ROI and profit >= MIN_PROFIT and vol >= MIN_VOL
        deals.append({
            "name": name, "buy": round(it["min_price"], 2),
            "steam": round(c["price"], 2), "profit": round(profit, 2),
            "roi": round(roi, 1), "volume": vol, "qty": it["qty"],
            "steam_ts": c["ts"], "pass": ok,
            "steam_url": "https://steamcommunity.com/market/listings/730/" + quote(name),
            "skinport_url": "https://skinport.com/market?search=" + quote(name),
        })
        if ok:
            passing += 1
    deals.sort(key=lambda d: -d["roi"])
    deals = deals[:DEALS_LIMIT]

    data = {
        "updated": now_iso(), "updated_ts": int(now),
        "skinport": {"items": len(catalog), "total": len(raw)},
        "steam": {
            "cached": sum(1 for v in cache.values() if v.get("price")),
            "queue": len(candidates(cache, catalog)),
            "fetched_this_run": fetched, "fails": fails, "r429": r429,
        },
        "stats": {"matched": len(deals), "passing": passing,
                  "best_roi": deals[0]["roi"] if deals else None},
        "thresholds": {"min_roi": MIN_ROI, "min_profit": MIN_PROFIT, "min_vol": MIN_VOL},
        "deals": deals,
    }
    save(CACHE_PATH, cache)
    save(DATA_PATH, data)
    print("Fetched:", fetched, "| fails:", fails, "| 429:", r429)
    print("Deals:", len(deals), "| passing:", passing, "| best ROI:", data["stats"]["best_roi"])
    print("== ARB SCAN DONE")


if __name__ == "__main__":
    main()
