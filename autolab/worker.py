"""Polymarket Lab - автономный воркер.
Сканирует крипто-рынки предсказаний Polymarket (gamma-api), ищет эджи,
ведёт бумажный портфель, пишет JSON для дашборда. Без зависимостей.
"""
import json, math, os, time, urllib.request

GAMMA = "https://gamma-api.polymarket.com"
ST = {"state": "results/state.json", "signals": "results/signals.json", "scan": "results/scan.json"}
CASH0 = 1000.0
MAX_POS = 6
MAX_MARKETS = 200
HIST_TOP = 50
FEE = 0.002
BUDGET_S = 420
TP, SL, MAX_AGE_D = 0.10, 0.10, 14.0
MIN_LIQ = 2000.0
T0 = time.time()

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def fetch(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "pm-lab/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def jload(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def jsave(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f: json.dump(obj, f, ensure_ascii=False, indent=1)

def plist(s):
    try: return json.loads(s)
    except Exception: return []

def fnum(x):
    try: return float(x or 0)
    except Exception: return 0.0

def scan():
    ms = []
    for off in range(0, MAX_MARKETS, 100):
        if time.time() > T0 + BUDGET_S * 0.35: break
        url = (GAMMA + "/markets?tag_id=21&closed=false&active=true&limit=100&offset=%d" % off) + "&order=volume24hr&ascending=false"
        try: batch = fetch(url, 12)
        except Exception: break
        if not isinstance(batch, list) or not batch: break
        ms.extend(batch)
        if len(batch) < 100: break
    out = []
    for m in ms:
        try:
            pr = [fnum(x) for x in plist(m.get("outcomePrices", "[]"))]
            outs = plist(m.get("outcomes", "[]"))
            if len(pr) != 2 or len(outs) != 2: continue
            if not m.get("active") or m.get("closed"): continue
            end = (m.get("endDate") or "")[:10]
            try: end_epoch = time.mktime(time.strptime(end, "%Y-%m-%d"))
            except Exception: end_epoch = 0
            out.append({
                "id": str(m.get("id")), "slug": m.get("slug", ""),
                "question": (m.get("question") or m.get("groupItemTitle") or "")[:140],
                "yes": pr[0], "no": pr[1],
                "v24": fnum(m.get("volume24hr")),
                "v1w": fnum(m.get("volume1wk")),
                "liq": fnum(m.get("liquidityNum") or m.get("liquidity")),
                "end": end, "end_epoch": end_epoch,
                "accepting": bool(m.get("acceptingOrders")),
            })
        except Exception: continue
    return out

def hist(mid):
    url = GAMMA + "/markets/%s/prices-history?interval=1w&fidelity=60" % mid
    try: d = fetch(url, 10)
    except Exception: return []
    h = d.get("history") if isinstance(d, dict) else None
    pts = []
    if isinstance(h, list):
        for x in h:
            try: pts.append(float(x.get("p")))
            except Exception: pass
    return pts

def zscore(pts):
    tail = pts[-48:]
    if len(tail) < 12: return 0.0
    m = sum(tail) / len(tail)
    var = sum((p - m) ** 2 for p in tail) / len(tail)
    sd = math.sqrt(var) or 1e-9
    return (tail[-1] - m) / sd

def days_left(m):
    if not m["end_epoch"]: return 999
    return max(0.0, (m["end_epoch"] - time.time()) / 86400.0)

def make_signals(ms):
    sigs = []
    ms2 = sorted(ms, key=lambda x: -x["liq"])[:HIST_TOP]
    for m in ms2:
        if time.time() > T0 + BUDGET_S * 0.8: break
        pts = hist(m["id"])
        z = zscore(pts)
        p, q = m["yes"], m["no"]
        dl = days_left(m)
        def add(strategy, outcome, price, edge, note, tradeable=True):
            sigs.append({"strategy": strategy, "slug": m["slug"], "question": m["question"],
                         "outcome": outcome, "price": round(price, 4), "edge": round(edge, 4),
                         "note": note, "liq": round(m["liq"]), "v24": round(m["v24"]),
                         "z": round(z, 2), "end": m["end"], "days_left": round(dl, 1),
                         "tradeable": tradeable})
        s = p + q
        if s < 1 - 3 * FEE and m["liq"] >= MIN_LIQ and s > 0:
            side = "Yes" if p <= q else "No"
            add("arb", side, min(p, q), (1.0 - s) / s, "сумма исходов %.3f < 1 - издержки" % s)
        if len(pts) >= 40 and 0.10 <= p <= 0.92:
            base = pts[-min(72, len(pts) - 1)]
            chg = pts[-1] - base
            if chg > 0.05: add("momentum", "Yes", p, chg * 2, "рост +%.1f%% за 3 дня" % (chg * 100))
            elif chg < -0.05: add("momentum", "No", q, -chg * 2, "падение %.1f%% за 3 дня" % (chg * 100))
        if z < -2.0 and 0.15 <= p <= 0.85: add("mr", "Yes", p, -z * 0.02, "цена ниже нормы, z=%.1f" % z)
        if z > 2.0 and 0.15 <= q <= 0.85: add("mr", "No", q, z * 0.02, "цена выше нормы, z=%.1f" % z)
        if m["v1w"] > 0 and m["v24"] > 0 and m["v24"] > (m["v1w"] / 7.0) * 3.0:
            add("vols", "-", 0, 0, "объём 24ч %.0f против среднего %.0f" % (m["v24"], m["v1w"] / 7.0), False)
        if 0.78 <= p <= 0.95 and dl <= 30 and m["liq"] >= 10000: add("fav", "Yes", p, (1 - p) * 0.5, "фаворит %.0f%% до конца %.0f дн" % (p * 100, dl))
        if 0.78 <= q <= 0.95 and dl <= 30 and m["liq"] >= 10000: add("fav", "No", q, (1 - q) * 0.5, "фаворит (No) %.0f%% до конца %.0f дн" % (q * 100, dl))
    best = {}
    for s in sigs:
        if s["slug"] not in best or s["edge"] > best[s["slug"]]["edge"]:
            best[s["slug"]] = s
    return sorted(best.values(), key=lambda x: -x["edge"])[:20]

def close_pos(st, key, reason):
    pos = st["positions"].pop(key)
    px = pos["last"]
    ret = px / pos["entry"] - 1.0 - FEE
    st["cash"] += pos["shares"] * px * (1 - FEE / 2)
    st["closed"].append({"question": pos["question"], "slug": pos["slug"], "outcome": pos["outcome"],
                          "entry": pos["entry"], "exit": px, "ret_pct": round(ret * 100, 2),
                          "strategy": pos["strategy"], "opened": pos["opened"], "closed": now(),
                          "reason": reason})
    st["closed"] = st["closed"][-200:]

def main():
    st = jload(ST["state"], {"cash": CASH0, "positions": {}, "closed": [], "curve": [[now(), CASH0]], "runs": 0})
    ms = scan()
    by_slug = {}
    for m in ms: by_slug[m["slug"]] = m
    for key in list(st["positions"].keys()):
        pos = st["positions"].get(key)
        if pos is None: continue
        m = by_slug.get(pos["slug"])
        if m is not None:
            pos["last"] = m["yes"] if pos["outcome"] == "Yes" else m["no"]
            if not m["accepting"]:
                close_pos(st, key, "рынок закрыт")
                continue
        else:
            pos.setdefault("last", pos["entry"])
        chg = pos["last"] / pos["entry"] - 1.0
        age = (time.time() - pos["epoch"]) / 86400.0
        if chg >= TP: close_pos(st, key, "тейк-профит +10%")
        elif chg <= -SL: close_pos(st, key, "стоп-лосс -10%")
        elif age > MAX_AGE_D: close_pos(st, key, "макс. срок 14 дней")
    sigs = make_signals(ms)
    eq = st["cash"] + sum(p["shares"] * p.get("last", p["entry"]) for p in st["positions"].values())
    held = set(p["slug"] for p in st["positions"].values())
    for s in sigs:
        if len(st["positions"]) >= MAX_POS or st["cash"] < 20: break
        if not s["tradeable"] or s["slug"] in held: continue
        if not (0.06 <= s["price"] <= 0.94) or s["liq"] < MIN_LIQ or s["edge"] <= 0: continue
        amt = min(0.05 * eq, st["cash"])
        if amt < 10: continue
        shares = amt * (1 - FEE / 2) / s["price"]
        st["cash"] -= amt
        st["positions"][s["slug"]] = {"question": s["question"], "slug": s["slug"],
            "outcome": s["outcome"], "strategy": s["strategy"], "entry": s["price"],
            "last": s["price"], "shares": round(shares, 2), "usd": round(amt, 2),
            "opened": now(), "epoch": time.time()}
        held.add(s["slug"])
    eq = st["cash"] + sum(p["shares"] * p.get("last", p["entry"]) for p in st["positions"].values())
    st["curve"].append([now(), round(eq, 2)])
    st["curve"] = st["curve"][-500:]
    st["runs"] = int(st.get("runs", 0)) + 1
    closed = st["closed"]
    wins = sum(1 for c in closed if c["ret_pct"] > 0)
    st["stats"] = {"equity": round(eq, 2), "cash": round(st["cash"], 2), "open": len(st["positions"]),
                   "trades": len(closed), "wins": wins,
                   "winrate": round(100.0 * wins / len(closed), 1) if closed else 0.0,
                   "pnl_pct": round((eq / CASH0 - 1) * 100, 2), "updated": now(), "runs": st["runs"]}
    jsave(ST["state"], st)
    jsave(ST["signals"], {"updated": now(), "scanned": len(ms), "signals": sigs})
    jsave(ST["scan"], {"updated": now(), "scanned": len(ms), "runs": st["runs"],
                       "with_history": min(len(ms), HIST_TOP)})
    print("pm-lab: scanned %d markets, %d signals, equity %.2f, open %d" % (len(ms), len(sigs), eq, len(st["positions"])))

if __name__ == "__main__":
    main()
