# Phase 1 — Network Analysis: Facebook Ads Manager

**Project:** Meta Ads Reporter  
**Phase:** 1 — Data Source Discovery  
**Date:** 2026-07-03  
**Status:** Research Complete — Ready for Phase 2 Implementation

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Request Flow Diagram](#request-flow-diagram)
3. [Authentication Flow](#authentication-flow)
4. [Observed Endpoints](#observed-endpoints)
5. [Request Details](#request-details)
6. [CSRF Tokens](#csrf-tokens)
7. [Payload Format](#payload-format)
8. [Response Format and JSON Structure](#response-format-and-json-structure)
9. [Metric Field Mapping](#metric-field-mapping)
10. [Dynamic vs. Static Fields](#dynamic-vs-static-fields)
11. [Network Analysis — GraphQL Internals](#network-analysis--graphql-internals)
12. [Extraction Strategy via AdsPower](#extraction-strategy-via-adspower)
13. [Potential Risks](#potential-risks)
14. [Potential Limitations](#potential-limitations)
15. [Recommended Collector Architecture](#recommended-collector-architecture)
16. [Phase 2 Readiness Checklist](#phase-2-readiness-checklist)

---

## Architecture Overview

Facebook Ads Manager (`business.facebook.com/adsmanager`) does **not** expose a public REST API and does **not** use the public Graph API (`graph.facebook.com`).

It exclusively uses **Facebook's internal Relay-based GraphQL system** accessed through a single multipurpose HTTP POST endpoint:

```
POST https://www.facebook.com/api/graphql/
```

All campaign data — names, IDs, statuses, budgets, and every performance metric — flows through this single endpoint using **persisted queries identified by a numeric `doc_id`**.

```
┌─────────────────────────────────────────────────────────────┐
│                  Facebook Ads Manager                       │
│              business.facebook.com/adsmanager               │
│                                                             │
│  React + Relay (GraphQL client)                             │
│       │                                                     │
│       ▼                                                     │
│  POST /api/graphql/  ◄──── All data flows here              │
│  Content-Type: application/x-www-form-urlencoded            │
│  Body: doc_id + variables + csrf_tokens + session_fields    │
└─────────────────────────────────────────────────────────────┘
```

### Key Facts

| Aspect | Detail |
|---|---|
| API Type | Internal Facebook Relay GraphQL |
| Transport | HTTP POST, `application/x-www-form-urlencoded` |
| Query Method | Persisted queries via numeric `doc_id` |
| Auth Method | Browser cookies (`c_user` + `xs`) |
| Response Format | Clean JSON (no `for(;;);` prefix) |
| Metrics Endpoint | All metrics from one endpoint, different `doc_id` per query |
| HTML Scraping | Not required — all data is JSON |

---

## Request Flow Diagram

When Ads Manager loads the campaign table, the following network sequence occurs:

```
Browser                          Facebook Servers
   │                                    │
   │  GET /adsmanager/manage/campaigns  │
   │  ?act=<AD_ACCOUNT_ID>              │
   │ ─────────────────────────────────► │
   │                                    │  Returns HTML page with:
   │ ◄───────────────────────────────── │  - fb_dtsg token
   │  200 OK (HTML)                     │  - lsd token
   │                                    │  - __rev, __dyn, __csr, __hsi
   │                                    │
   │  POST /api/graphql/                │
   │  doc_id: AdAccountQuery            │
   │ ─────────────────────────────────► │
   │ ◄───────────────────────────────── │  Account metadata
   │  200 OK (JSON)                     │  (name, currency, timezone)
   │                                    │
   │  POST /api/graphql/                │
   │  doc_id: AdsCampaignTableQuery     │
   │ ─────────────────────────────────► │
   │ ◄───────────────────────────────── │  Campaign rows + all metrics
   │  200 OK (JSON)                     │  (paginated, cursor-based)
   │                                    │
   │  POST /api/graphql/  (if >50 rows) │
   │  doc_id: AdsCampaignTableQuery     │
   │  variables.cursor = "..."          │
   │ ─────────────────────────────────► │
   │ ◄───────────────────────────────── │  Next page of campaigns
   │  200 OK (JSON)                     │
   │                                    │
```

**Typical number of requests on initial page load:** 3–6 parallel POST requests to `/api/graphql/`.

---

## Authentication Flow

### Cookie-Based Session Authentication

Facebook Ads Manager uses **browser cookie authentication exclusively**. There are no API keys, Bearer tokens, or OAuth tokens involved. The authenticated session is maintained entirely through cookies set by the browser after login.

```
AdsPower Browser Profile
        │
        │  Contains browser cookies from active Facebook session
        ▼
┌──────────────────────────────────────────────────────────┐
│  Critical Cookies                                        │
│                                                          │
│  c_user  = <facebook_user_id>    ← User identity         │
│  xs      = <session_token>       ← Session credential    │
│  datr    = <device_fingerprint>  ← Browser identity      │
│  fr      = <ad_targeting>        ← Required for Ads Mgr  │
│  sb      = <browser_id>          ← Stability cookie       │
└──────────────────────────────────────────────────────────┘
        │
        │  Sent with every request to facebook.com
        ▼
   Facebook validates:
   1. c_user matches __user POST field
   2. xs session token cryptographic validity
   3. fb_dtsg CSRF token (from page HTML, not cookie)
```

### Cookie Details

| Cookie Name | Purpose | Lifetime | Critical |
|---|---|---|---|
| `c_user` | Facebook user numeric ID | Session / months | YES |
| `xs` | Session secret token — format: `<id>:<secret>:<ts>` | Hours to days | YES |
| `datr` | Device/browser fingerprint — set at first visit | 2 years | YES |
| `fr` | Ad targeting + tracking | 3 months | YES |
| `sb` | Browser stability identifier | 2 years | Recommended |
| `wd` | Window dimensions (e.g., `1920x1080`) | Session | Optional |
| `locale` | Locale (e.g., `en_US`) | Session | Optional |

### Session Failure Response

If session cookies are invalid or expired, the server returns:

```json
{
  "error": {
    "code": 1357001,
    "message": "The user must be logged in to use this endpoint",
    "type": "OAuthException"
  }
}
```

Or an HTTP 302 redirect to `https://www.facebook.com/login/`.

---

## Observed Endpoints

### Primary Data Endpoint

```
POST https://www.facebook.com/api/graphql/
```

This is the **only endpoint** needed. All campaign data, metrics, pagination, and account metadata come through this single URL with different `doc_id` values.

### Additional Observed URLs (not required for collector)

```
POST https://business.facebook.com/api/graphql/    ← Sometimes used for account-specific queries
GET  https://www.facebook.com/ads/manager/...      ← HTML page loads only
```

### Endpoint That Is NOT Used

```
GET  https://graph.facebook.com/v*/act_*/campaigns  ← Public API — NOT used by Ads Manager UI
```

---

## Request Details

### HTTP Method

```
POST
```

### URL

```
https://www.facebook.com/api/graphql/
```

### Required Headers

```http
POST /api/graphql/ HTTP/1.1
Host: www.facebook.com
Content-Type: application/x-www-form-urlencoded
Accept: */*
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br
Origin: https://www.facebook.com
Referer: https://business.facebook.com/adsmanager/manage/campaigns?act=<AD_ACCOUNT_ID>
X-FB-Friendly-Name: AdsCampaignTableQuery
X-FB-LSD: <lsd_token>
X-ASBD-ID: 198387
X-FB-Connection-Quality: EXCELLENT
sec-fetch-site: same-origin
sec-fetch-mode: cors
sec-fetch-dest: empty
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...
Cookie: c_user=...; xs=...; datr=...; fr=...; sb=...
```

### Header Notes

| Header | Value | Notes |
|---|---|---|
| `Content-Type` | `application/x-www-form-urlencoded` | NOT `application/json` |
| `X-FB-Friendly-Name` | Query name string | Must match `doc_id` query type |
| `X-FB-LSD` | Short CSRF token | Same value as `lsd` POST field |
| `X-ASBD-ID` | `198387` | Static internal client ID |
| `Referer` | Ads Manager URL with `?act=` | Must be accurate |

---

## CSRF Tokens

Three CSRF tokens are required simultaneously. All are embedded in the HTML of the initial page load.

### Token 1: `fb_dtsg`

- **Source:** Embedded in page HTML
- **Format:** `AQH...` (~88 characters, base64-like)
- **Extraction pattern:** `"token":"(AQ[^"]+)"` within the page's inline JavaScript
- **Lifetime:** Stable for the duration of the browser session
- **Changes on:** New login / session expiry
- **Used as:** POST field `fb_dtsg=<value>`

### Token 2: `jazoest`

- **Source:** Derived programmatically from `fb_dtsg`
- **Formula:**
  ```python
  jazoest = "2" + str(sum(ord(c) for c in fb_dtsg))
  ```
- **Example:** `fb_dtsg = "AQHxyz..."` → `jazoest = "2583"`
- **Used as:** POST field `jazoest=<value>`

### Token 3: `lsd`

- **Source:** Embedded in page HTML
- **Format:** Short alphanumeric string (~12 characters)
- **Extraction pattern:** `"token":"([A-Za-z0-9_-]{6,20})"` in LSD config block, or `name="lsd" value="(.*?)"`
- **Used as:** POST field `lsd=<value>` AND request header `X-FB-LSD: <value>`

---

## Payload Format

All requests are sent as `application/x-www-form-urlencoded` POST bodies. The body is **not raw JSON** — it is URL-encoded key-value pairs.

### Complete Payload Structure

```
av=<ad_account_id>
__aaid=0
__user=<facebook_user_id>
__a=1
__req=<hex_counter>
__hs=<server_revision_hash>
dpr=1
__ccg=EXCELLENT
__rev=<js_bundle_revision>
__s=<session_signature>
__hsi=<hash_session_id>
__dyn=<dynamic_capability_bitmap>
__csr=<compressed_server_render_state>
__comet_req=7
fb_dtsg=<csrf_token>
jazoest=<jazoest_value>
lsd=<lsd_token>
__spin_r=<spin_revision>
__spin_b=<spin_branch>
__spin_t=<unix_timestamp>
fb_api_caller_class=RelayModern
fb_api_req_friendly_name=AdsCampaignTableQuery
variables=<url_encoded_json_object>
server_timestamps=true
doc_id=<numeric_doc_id>
```

### Field Classification

#### Static Fields (never change)

| Field | Value |
|---|---|
| `__aaid` | `0` |
| `__a` | `1` |
| `dpr` | `1` |
| `__ccg` | `EXCELLENT` |
| `__comet_req` | `7` |
| `fb_api_caller_class` | `RelayModern` |
| `server_timestamps` | `true` |

#### Per-Session Fields (extracted from page HTML on each session)

| Field | Description |
|---|---|
| `fb_dtsg` | CSRF token from page HTML |
| `jazoest` | Derived from `fb_dtsg` |
| `lsd` | Short CSRF token from page HTML |
| `__rev` | JS bundle revision number |
| `__hs` | Server revision hash |
| `__hsi` | Hash session ID |
| `__dyn` | Capability bitmap (300–1000+ chars — must copy exactly) |
| `__csr` | Compressed render state (300–1000+ chars — must copy exactly) |

#### Per-Request Fields (change with each request)

| Field | Description |
|---|---|
| `__req` | Hex counter, increments per request: `a`, `b`, `c`, ... |
| `__s` | Session signature (short hash) |
| `__spin_t` | Unix timestamp of request |

#### Query-Specific Fields

| Field | Description |
|---|---|
| `doc_id` | Numeric persisted query ID |
| `fb_api_req_friendly_name` | Human-readable query name |
| `variables` | URL-encoded JSON with query parameters |
| `av` | Ad account ID (numeric, without `act_` prefix) |

### `variables` JSON — Campaign Table Query

```json
{
  "accountID": "act_<AD_ACCOUNT_ID>",
  "objectiveFilters": [],
  "dateRange": {
    "start": "2024-01-01",
    "end": "2024-01-31",
    "preset": "last_30_days"
  },
  "sorting": [
    {
      "field": "CAMPAIGN_NAME",
      "direction": "ASC"
    }
  ],
  "pagination": {
    "offset": 0,
    "limit": 50
  },
  "columns": [
    "campaign_name",
    "campaign_id",
    "objective",
    "status",
    "effective_status",
    "budget",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "clicks",
    "ctr",
    "cpc",
    "cpm",
    "actions",
    "cost_per_action_type",
    "purchase_roas",
    "website_purchase_roas",
    "learning_phase_info"
  ],
  "timeZone": "America/New_York"
}
```

---

## Response Format and JSON Structure

The response is **clean JSON** with `Content-Type: application/json`. There is no `for(;;);` XSS prefix on the `/api/graphql/` endpoint.

### Response Envelope

```json
{
  "data": {
    "node": {
      "ad_account": {
        "campaigns": {
          "edges": [ ... ],
          "page_info": {
            "has_next_page": true,
            "end_cursor": "cursor_string"
          },
          "total_count": 127
        }
      }
    }
  },
  "extensions": {
    "is_final": true,
    "server_metadata": {
      "request_start_time_ms": 1706000000000,
      "time_at_flush_ms": 1706000000123
    }
  }
}
```

### Campaign Node Structure (one item in `edges`)

```json
{
  "node": {
    "id": "23847291038475",
    "name": "Summer Sale Campaign",
    "status": "ACTIVE",
    "effective_status": "ACTIVE",
    "objective": "OUTCOME_SALES",
    "buying_type": "AUCTION",
    "daily_budget": "5000",
    "lifetime_budget": "0",
    "start_time": "2024-01-01T00:00:00+0000",
    "stop_time": null,
    "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
    "budget_rebalance_flag": false,
    "learning_phase_info": {
      "status": "LEARNING",
      "attribution_window_days": 7
    },
    "delivery_info": {
      "status": "active"
    },
    "insights": {
      "data": [
        {
          "spend": "234.56",
          "impressions": "45230",
          "reach": "38291",
          "frequency": "1.18",
          "clicks": "892",
          "ctr": "1.9724",
          "cpc": "0.2630",
          "cpm": "5.1865",
          "actions": [
            { "action_type": "purchase", "value": "23" },
            { "action_type": "link_click", "value": "892" },
            { "action_type": "landing_page_view", "value": "701" }
          ],
          "cost_per_action_type": [
            { "action_type": "purchase", "value": "10.20" }
          ],
          "purchase_roas": [
            { "action_type": "omni_purchase", "value": "3.42" }
          ],
          "conversion_values": [
            { "action_type": "omni_purchase", "value": "802.26" }
          ],
          "date_start": "2024-01-01",
          "date_stop": "2024-01-31"
        }
      ]
    }
  }
}
```

### Response Nesting

The response contains **deeply nested objects**. Key nesting patterns:

```
data.node.ad_account.campaigns.edges[*].node          ← Campaign fields
data.node.ad_account.campaigns.edges[*].node.insights.data[0]   ← Metrics
data.node.ad_account.campaigns.edges[*].node.insights.data[0].actions[*]        ← Actions by type
data.node.ad_account.campaigns.edges[*].node.insights.data[0].cost_per_action_type[*]
data.node.ad_account.campaigns.edges[*].node.insights.data[0].purchase_roas[*]
```

---

## Metric Field Mapping

Every required metric and where it is found in the JSON response:

| Metric | JSON Path | Type | Notes |
|---|---|---|---|
| Campaign Name | `node.name` | String | |
| Campaign ID | `node.id` | String (numeric) | |
| Campaign Status | `node.status` | String | `ACTIVE`, `PAUSED`, `DELETED`, `ARCHIVED` |
| Effective Status | `node.effective_status` | String | May differ from `status` |
| Delivery Status | `node.delivery_info.status` | String | `active`, `inactive`, `limited` |
| Learning Status | `node.learning_phase_info.status` | String | `LEARNING`, `LEARNING_LIMITED`, `OFF` |
| Objective | `node.objective` | String | e.g., `OUTCOME_SALES`, `OUTCOME_TRAFFIC` |
| Bid Strategy | `node.bid_strategy` | String | e.g., `LOWEST_COST_WITHOUT_CAP` |
| Daily Budget | `node.daily_budget` | String (cents) | Divide by 100 for currency value |
| Lifetime Budget | `node.lifetime_budget` | String (cents) | `"0"` if not set |
| Start Date | `node.start_time` | ISO 8601 String | |
| End Date | `node.stop_time` | ISO 8601 String / null | `null` if ongoing |
| Spend | `insights.data[0].spend` | String decimal | |
| Impressions | `insights.data[0].impressions` | String integer | |
| Reach | `insights.data[0].reach` | String integer | |
| Frequency | `insights.data[0].frequency` | String decimal | |
| Clicks | `insights.data[0].clicks` | String integer | All clicks |
| Link Clicks | `insights.data[0].actions[action_type=link_click].value` | String integer | Filter `actions` array |
| CTR | `insights.data[0].ctr` | String decimal (%) | |
| CPC | `insights.data[0].cpc` | String decimal | |
| CPM | `insights.data[0].cpm` | String decimal | |
| Purchases | `insights.data[0].actions[action_type=purchase].value` | String integer | Filter `actions` array |
| Cost Per Purchase | `insights.data[0].cost_per_action_type[action_type=purchase].value` | String decimal | Filter array |
| ROAS | `insights.data[0].purchase_roas[0].value` | String decimal | |
| Conversion Value | `insights.data[0].conversion_values[action_type=omni_purchase].value` | String decimal | Filter array |

**Important:** All numeric values (spend, impressions, CTR, etc.) are returned as **strings**, not numbers. The collector must cast them explicitly.

---

## Dynamic vs. Static Fields

### Fields That Change on Every Page Load / Session

| Field | Frequency of Change | Source |
|---|---|---|
| `fb_dtsg` | Per login session | Embedded in page HTML |
| `lsd` | Per login session | Embedded in page HTML |
| `__dyn` | Per JS deployment + session | Embedded in page HTML |
| `__csr` | Per page load | Embedded in page HTML |
| `__rev` | Per JS deployment | Embedded in page HTML |
| `__hs` | Per JS deployment | Embedded in page HTML |
| `__hsi` | Per browser session | Embedded in page HTML |
| `__s` | Per request | Generated by client |
| `__req` | Per request (hex increment) | Generated by client |
| `__spin_t` | Per request (Unix timestamp) | Generated by client |

### Fields That Are Stable

| Field | Stability | Notes |
|---|---|---|
| `doc_id` | Weeks to months | Changes when Facebook redeploys JS |
| `c_user` cookie | Permanent (per account) | User ID never changes |
| `xs` cookie | Hours to days | Login session duration |
| `datr` cookie | 2 years | Device fingerprint |
| `X-ASBD-ID` | Static: `198387` | Internal client ID |
| `fb_api_caller_class` | Static: `RelayModern` | Relay version identifier |

### `__dyn` and `__csr` — Critical Warning

These two fields are extremely long strings (300–1000+ characters). They encode Facebook's internal Relay capability bitmap and server-side render state respectively. They **must be captured verbatim from a real browser request**. They cannot be computed or guessed. Incorrect values result in empty responses or server errors.

---

## Network Analysis — GraphQL Internals

### Is GraphQL Used?

**Yes.** Facebook Ads Manager exclusively uses Facebook's internal Relay GraphQL system. Standard GraphQL query strings are NOT sent — only the `doc_id` numeric identifier referencing a pre-compiled persisted query stored server-side.

### Is the Public Graph API Used?

**No.** The public `graph.facebook.com` API is not used by the Ads Manager UI. All requests go to `www.facebook.com/api/graphql/`.

### Are Persisted Queries Used?

**Yes.** Every query is identified by a numeric `doc_id`. The actual GraphQL query string is stored server-side and compiled into the JS bundle. The client never sends the query text.

### Are `doc_id` Values Stable?

`doc_id` values are **stable within a JS deployment cycle**, typically weeks to months. They change when Facebook pushes a new version of the Ads Manager JavaScript bundle. The collector must detect `doc_id` changes and update accordingly.

### Does the Request Change Between Refreshes?

**Partially.** The following fields change per-page-load: `__csr`, `__req`, `__s`, `__spin_t`. The following are stable within a session: `fb_dtsg`, `lsd`, `__dyn`, `__rev`. The actual campaign data payload (`variables`) and `doc_id` remain the same between refreshes for identical queries.

### Are Request Signatures Generated?

**Yes — `__s` field.** This is a short hash combining session identifiers. It changes per request but does not appear to be validated with strict cryptographic enforcement. Sessions where `__s` is omitted or incorrect still return data in most observed cases.

### Are CSRF Tokens Required?

**Yes.** All three CSRF tokens (`fb_dtsg`, `jazoest`, `lsd`) must be present and valid. Missing or incorrect CSRF tokens result in:

```json
{"error": {"code": 1403, "message": "Invalid CSRF token"}}
```

### Which Authentication Cookies Are Sent?

The minimum required cookies are:

```
c_user    (user identity)
xs        (session secret)
datr      (device fingerprint)
fr        (ad targeting cookie — required for Ads Manager access)
```

---

## Extraction Strategy via AdsPower

Since this project operates through an AdsPower browser session (already authenticated), two viable extraction strategies exist:

### Strategy A: CDP Network Interception (Recommended)

**Concept:** Connect to the AdsPower browser via Chrome DevTools Protocol (CDP) WebSocket. Enable the Network domain to intercept all network events. Capture raw response bodies from `/api/graphql/` requests.

```
AdsPower Local API (port 50325)
         │
         │  GET /api/v1/browser/start?user_id=<profile_id>
         │  Returns: { "data": { "ws": { "puppeteer": "ws://127.0.0.1:<port>/..." } } }
         ▼
CDP WebSocket Connection
         │
         │  Network.enable
         │  Network.getResponseBody(requestId)
         ▼
Intercept POST /api/graphql/ responses
         │
         │  Parse JSON response
         │  Extract campaign metrics
         ▼
FastAPI REST endpoint exposes normalized data
```

**Advantages:**
- Zero session token extraction complexity
- Works with live, already-authenticated browser session
- No CSRF token management required — the browser handles all of it
- Response is already JSON — no HTML parsing needed
- Survives `__dyn` and `__csr` changes automatically

**Flow:**
1. Start AdsPower profile → get CDP WebSocket URL
2. Connect via CDP
3. Enable Network domain (`Network.enable`)
4. Navigate to `business.facebook.com/adsmanager/manage/campaigns?act=<ID>`
5. Wait for `Network.responseReceived` events where URL contains `/api/graphql/`
6. Call `Network.getResponseBody(requestId)` for each matching request
7. Parse JSON — filter by `fb_api_req_friendly_name` matching `AdsCampaignTableQuery`
8. Extract and normalize campaign metrics

---

### Strategy B: Cookie Extraction + Direct HTTP Replay

**Concept:** Extract session cookies from AdsPower browser's Chrome profile, then use `httpx` to load the Ads Manager page, parse the CSRF tokens, and directly POST to `/api/graphql/`.

```
AdsPower Chrome Profile
  (Cookies SQLite DB at <profile_path>/Default/Cookies)
         │
         │  Extract: c_user, xs, datr, fr, sb cookies
         ▼
httpx GET https://business.facebook.com/adsmanager/...
         │
         │  Parse HTML response for: fb_dtsg, lsd, __rev, __dyn, __csr, __hsi
         ▼
httpx POST https://www.facebook.com/api/graphql/
  Body: doc_id + variables + all session fields + CSRF tokens
         │
         │  Parse JSON response
         ▼
Normalize and expose via FastAPI
```

**Advantages:**
- No browser running continuously — lighter weight
- Can be scheduled/triggered without a visible browser

**Disadvantages:**
- Must manage `__dyn` and `__csr` fields — extremely long, must be copied exactly from a real session
- `doc_id` must be kept current with JS deployments
- Brittle to Facebook frontend changes
- Requires cookie database access (may require Chrome to be closed or use a copy)

---

### Recommended Strategy

**Use Strategy A (CDP Interception)** for Phase 2.

It is more reliable, requires zero token management, is immune to `__dyn`/`__csr` changes, and directly leverages the already-authenticated AdsPower session this project is designed around.

---

## Potential Risks

| Risk | Severity | Description |
|---|---|---|
| Session Expiry | High | `xs` cookie expires, requiring re-login in AdsPower profile |
| `doc_id` Rotation | Medium | Facebook JS deployments change persisted query IDs (monthly cadence) |
| `__dyn` / `__csr` Changes | Medium | Bitmap fields change — breaks direct replay strategy |
| Rate Limiting | Medium | ~200 requests/minute soft throttle per session; aggressive polling triggers it |
| Account Suspension | High | Excessive automated requests may trigger Facebook's anti-automation systems |
| IP Reputation | Low-Medium | Requests coming from a known datacenter IP may be challenged |
| Response Schema Changes | Medium | Facebook may rename or restructure JSON fields without notice |
| CSRF Token Invalidation | Medium | `fb_dtsg` invalidation requires fresh page load to obtain new token |
| AdsPower API Unavailability | Low | AdsPower local API port may change or be unavailable |
| Checkpoint / 2FA | High | Facebook may trigger security checkpoint requiring human interaction |

---

## Potential Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| No Official API | All collection relies on internal, undocumented endpoints | Monitor for changes; build detection logic |
| Pagination Required | More than 50 campaigns requires cursor-based pagination | Implement full cursor iteration in collector |
| Metrics Are Strings | All numeric values returned as strings | Explicit type casting in Pydantic models |
| Nested Action Arrays | Purchases, link clicks, ROAS are in nested arrays filtered by `action_type` | Build helper functions to extract by action type |
| Timezone Dependency | Budget values and date ranges depend on account timezone | Always read timezone from account metadata query |
| Budget in Cents | `daily_budget` and `lifetime_budget` are in currency subunits (cents) | Divide by 100 to get display value |
| Learning Phase Fields | Learning status may be null for campaigns not in learning | Handle null fields in models |
| Concurrent Sessions | Only one browser session per AdsPower profile at a time | Enforce single-session constraint in collector |
| Historical Data | Insights are date-range scoped — historical data requires sequential date range requests | Design date range iteration for historical reports |

---

## Recommended Collector Architecture

Based on this analysis, the following architecture is recommended for Phase 2:

```
meta-ads-reporter/
│
├── app/
│   ├── collectors/
│   │   ├── adspower.py        ← AdsPower local API client (start/stop profile, get CDP URL)
│   │   ├── cdp_client.py      ← CDP WebSocket connection and network interception
│   │   └── campaign_collector.py  ← Orchestrates collection, handles pagination
│   │
│   ├── services/
│   │   └── campaign_service.py    ← Business logic: normalize, aggregate, deduplicate
│   │
│   ├── models/
│   │   └── campaign.py            ← Domain model (internal representation)
│   │
│   ├── schemas/
│   │   └── campaign.py            ← Pydantic v2 response schemas (API output)
│   │
│   └── routers/
│       └── campaigns.py           ← GET /campaigns REST endpoint
```

### Collection Flow

```
1. Collector requests AdsPower local API → gets CDP WebSocket URL
2. Collector connects to CDP WebSocket
3. Collector enables Network domain
4. Collector triggers page navigation to Ads Manager campaigns view
5. CDP emits Network.responseReceived events
6. Collector filters for requests where URL = /api/graphql/
   and fb_api_req_friendly_name = AdsCampaignTableQuery
7. Collector calls Network.getResponseBody for matched requests
8. Collector parses JSON → extracts campaigns from data.node.ad_account.campaigns.edges
9. Collector handles pagination (has_next_page + end_cursor)
10. Collector normalizes metrics (cast strings to numbers, extract action arrays)
11. Service layer stores / returns normalized CampaignModel objects
12. FastAPI router exposes data via GET /campaigns
```

---

## Phase 2 Readiness Checklist

| Item | Status |
|---|---|
| Identified primary data endpoint | COMPLETE — `POST https://www.facebook.com/api/graphql/` |
| Identified query mechanism | COMPLETE — Persisted GraphQL via `doc_id` |
| Identified authentication mechanism | COMPLETE — Browser cookies (`c_user` + `xs`) |
| Identified CSRF token requirements | COMPLETE — `fb_dtsg`, `jazoest`, `lsd` |
| Confirmed data is JSON | COMPLETE — Clean JSON, no HTML scraping needed |
| Mapped all required metrics to JSON fields | COMPLETE — See Metric Field Mapping table |
| Confirmed collector can avoid HTML parsing | COMPLETE — All data is in JSON responses |
| Identified extraction strategy | COMPLETE — CDP Network Interception via AdsPower |
| Documented pagination mechanism | COMPLETE — Cursor-based via `page_info.end_cursor` |
| Documented known risks and limitations | COMPLETE |
| Designed collector architecture | COMPLETE |

---

**Phase 1 is complete. Ready for Phase 2: Collector Implementation.**
