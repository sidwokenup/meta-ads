"""Use Runtime.evaluate to call adsmanager-graph API from inside the browser."""
import asyncio
import json
import sys, os, re
sys.path.insert(0, os.path.dirname(__file__))
from app.collectors.adspower import AdsPowerClient
from app.collectors.cdp_client import CDPClient
from app.collectors.token_extractor import extract_token_via_cdp

PROFILE_ID = "k1dvlyr0"
ACCOUNT_ID = "1559140139101704"

async def browser_get(cdp, url, label):
    js = f"""
(async () => {{
    const r = await fetch("{url}", {{credentials: "include"}});
    const d = await r.json();
    return JSON.stringify({{status: r.status, data: d}});
}})()
"""
    result = await cdp._send("Runtime.evaluate", {
        "expression": js,
        "awaitPromise": True,
        "returnByValue": True,
    })
    raw = result.get("result", {}).get("value", "{}")
    try:
        parsed = json.loads(raw)
        st = parsed.get("status", 0)
        d = parsed.get("data", {})
        if "error" in d:
            print(f"FAIL [{label}] HTTP {st}: {d['error']}")
            return None
        campaigns = d.get("data", [])
        print(f"OK   [{label}] HTTP {st}: {len(campaigns)} items")
        for c in campaigns[:5]:
            name = c.get("name", c.get("id", "?"))
            status = c.get("status", c.get("effective_status", "?"))
            spend = ""
            ins = c.get("insights", {})
            if ins and ins.get("data"):
                spend = f" | spend={ins['data'][0].get('spend','?')}"
            print(f"     -> {name} | {status}{spend}")
        return campaigns
    except Exception as e:
        print(f"ERROR [{label}]: {e} | raw={raw[:200]}")
        return None

async def main():
    adspower = AdsPowerClient()
    ws_url = await adspower.get_websocket(PROFILE_ID)
    cdp = CDPClient(ws_url=ws_url, prefer_url_fragment="adsmanager")
    await cdp.connect()
    await cdp.enable_network()

    result = await extract_token_via_cdp(cdp, ACCOUNT_ID)
    token = result.token
    print(f"Token: {token[:30]}...\n")

    BASE = f"https://adsmanager-graph.facebook.com/v22.0"
    ACT = f"act_{ACCOUNT_ID}"

    # Test 1: basic campaigns from inside browser
    await browser_get(cdp,
        f"{BASE}/{ACT}/campaigns?fields=id,name,status&limit=10&access_token={token}",
        "adsmanager-graph basic"
    )

    # Test 2: with insights
    fields = (
        "id,name,status,effective_status,daily_budget,lifetime_budget,objective,bid_strategy,start_time,stop_time,"
        "insights.date_preset(last_30d){spend,impressions,reach,frequency,clicks,ctr,cpc,cpm,"
        "actions,cost_per_action_type,purchase_roas,conversion_values,date_start,date_stop}"
    )
    await browser_get(cdp,
        f"{BASE}/{ACT}/campaigns?fields={fields}&limit=10&access_token={token}",
        "adsmanager-graph full insights"
    )

    # Test 3: graph.facebook.com from inside browser
    await browser_get(cdp,
        f"https://graph.facebook.com/v22.0/{ACT}/campaigns?fields=id,name,status&limit=10&access_token={token}",
        "graph.facebook.com basic"
    )

    await cdp.disconnect()

asyncio.run(main())
