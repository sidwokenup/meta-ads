import asyncio
import httpx

async def check():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=60.0) as client:
        r = await client.get("/campaigns")
        data = r.json()
        print(f"HTTP Status : {r.status_code}")
        print(f"Total       : {data['total']} campaigns")
        print(f"Account     : {data['account_id']}")
        print(f"Preset      : {data['date_preset']}")
        print(f"Time        : {data['response_time_ms']}ms")
        print()
        for i, c in enumerate(data["campaigns"], 1):
            ins = c["insights"]
            print(f"{i}. {c['campaign_name']}")
            print(f"   Status    : {c['effective_status']}")
            print(f"   Objective : {c['objective']}")
            print(f"   Budget    : {c['budget_type']}  daily={c['daily_budget']}  lifetime={c['lifetime_budget']}")
            print(f"   Spend     : ${ins['spend']}")
            print(f"   Impressions: {ins['impressions']}")
            print(f"   Reach     : {ins['reach']}")
            print(f"   Frequency : {ins['frequency']}")
            print(f"   Clicks    : {ins['clicks']}  LinkClicks={ins['link_clicks']}  UniqueClicks={ins['unique_clicks']}")
            print(f"   CTR       : {ins['ctr']}%")
            print(f"   CPC       : ${ins['cpc']}")
            print(f"   CPM       : ${ins['cpm']}")
            print(f"   Purchases : {ins['purchases']}")
            print(f"   PurchaseVal: ${ins['purchase_value']}")
            print(f"   CostPerPur: ${ins['cost_per_purchase']}")
            print(f"   ROAS      : {ins['roas']}x")
            print(f"   LP Views  : {ins['landing_page_views']}")
            print(f"   AddToCart : {ins['add_to_carts']}")
            print(f"   Checkouts : {ins['initiate_checkouts']}")
            print()

asyncio.run(check())
