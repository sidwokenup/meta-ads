"""
Campaign Mapper

Converts raw Facebook Graph API JSON dicts into clean, strongly-typed
Python objects. This is the normalization layer — Facebook JSON never
leaves this module as raw dicts.

Every field is:
  - Typed (float, int, str, Optional[str])
  - Named clearly (no Facebook internal names like "effective_status" leaking out as-is)
  - Converted from Facebook's string-encoded numbers to proper Python numbers
  - Documented with units

Output objects (dataclasses):
  CampaignData       — full normalized campaign object
  AdSetData          — normalized ad set
  AdData             — normalized ad
  AccountData        — normalized account overview
  InsightsData       — normalized performance metrics (reused inside campaigns/adsets/ads)
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Helpers — convert Facebook's string-encoded values to Python types
# ---------------------------------------------------------------------------


def _float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _budget(value: Any) -> Optional[float]:
    """Convert budget from Facebook cents (string) to currency float. None if 0."""
    raw = _int(value, 0)
    return raw / 100.0 if raw > 0 else None


def _action(actions: list[dict], action_type: str, default: int = 0) -> int:
    """Extract int count from Facebook actions[] array by action_type."""
    for item in (actions or []):
        if item.get("action_type") == action_type:
            return _int(item.get("value"), default)
    return default


def _cost(cost_list: list[dict], action_type: str, default: float = 0.0) -> float:
    """Extract float cost from Facebook cost_per_action_type[] by action_type."""
    for item in (cost_list or []):
        if item.get("action_type") == action_type:
            return _float(item.get("value"), default)
    return default


def _roas(roas_list: list[dict], action_type: str = "omni_purchase", default: float = 0.0) -> float:
    """Extract float ROAS from Facebook purchase_roas[] by action_type."""
    for item in (roas_list or []):
        if item.get("action_type") == action_type:
            return _float(item.get("value"), default)
    return default


def _conv_value(conv_list: list[dict], action_type: str = "omni_purchase", default: float = 0.0) -> float:
    """Extract float conversion value from Facebook conversion_values[] by action_type."""
    for item in (conv_list or []):
        if item.get("action_type") == action_type:
            return _float(item.get("value"), default)
    return default


def _budget_type(daily_raw: Any, lifetime_raw: Any) -> str:
    """Determine budget type: DAILY, LIFETIME, or UNKNOWN."""
    if _int(daily_raw) > 0:
        return "DAILY"
    if _int(lifetime_raw) > 0:
        return "LIFETIME"
    return "UNKNOWN"


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class InsightsData:
    """
    Normalized performance metrics for a reporting period.
    Used inside CampaignData, AdSetData, AdData.
    """
    # Reporting period
    date_start: Optional[str] = None
    date_stop: Optional[str] = None

    # Reach & impressions
    spend: float = 0.0                     # total spend in account currency
    impressions: int = 0                   # total impressions
    reach: int = 0                         # unique people reached
    frequency: float = 0.0                 # avg times each person saw the ad

    # Clicks
    clicks: int = 0                        # all clicks
    unique_clicks: int = 0                 # unique clicks (deduplicated)
    link_clicks: int = 0                   # link clicks only

    # Rates & costs
    ctr: float = 0.0                       # click-through rate (%)
    cpc: float = 0.0                       # cost per click
    cpm: float = 0.0                       # cost per 1,000 impressions

    # Conversions
    purchases: int = 0                     # purchase events
    purchase_value: float = 0.0            # total purchase conversion value
    cost_per_purchase: float = 0.0         # cost per purchase
    roas: float = 0.0                      # return on ad spend

    # Additional actions
    landing_page_views: int = 0            # landing page view events
    add_to_carts: int = 0                  # add to cart events
    initiate_checkouts: int = 0            # initiate checkout events

    def is_empty(self) -> bool:
        """True if no data was returned for this period (no spend, no impressions)."""
        return self.spend == 0.0 and self.impressions == 0


@dataclass
class CampaignData:
    """
    Fully normalized campaign object.
    This is what CollectorService returns — never raw Facebook JSON.
    """
    # Identity
    campaign_id: str = ""
    campaign_name: str = ""
    objective: Optional[str] = None
    buying_type: Optional[str] = None

    # Delivery
    status: str = "UNKNOWN"               # ACTIVE | PAUSED | DELETED | ARCHIVED
    effective_status: str = "UNKNOWN"     # what Facebook actually delivers
    delivery_status: Optional[str] = None  # UI label: active, inactive, limited
    learning_status: Optional[str] = None  # LEARNING | LEARNING_LIMITED | OFF

    # Budget
    daily_budget: Optional[float] = None   # in account currency, None if not set
    lifetime_budget: Optional[float] = None
    budget_type: str = "UNKNOWN"           # DAILY | LIFETIME | UNKNOWN

    # Schedule
    start_time: Optional[str] = None       # ISO 8601
    end_time: Optional[str] = None         # ISO 8601, None if ongoing

    # Strategy
    bid_strategy: Optional[str] = None     # LOWEST_COST_WITHOUT_CAP | COST_CAP | etc.

    # Performance for the requested date preset
    insights: InsightsData = field(default_factory=InsightsData)


@dataclass
class AdSetData:
    """Normalized ad set object."""
    adset_id: str = ""
    adset_name: str = ""
    campaign_id: str = ""
    status: str = "UNKNOWN"
    effective_status: str = "UNKNOWN"
    optimization_goal: Optional[str] = None
    bid_strategy: Optional[str] = None
    daily_budget: Optional[float] = None
    lifetime_budget: Optional[float] = None
    budget_type: str = "UNKNOWN"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    insights: InsightsData = field(default_factory=InsightsData)


@dataclass
class AdData:
    """Normalized ad object."""
    ad_id: str = ""
    ad_name: str = ""
    adset_id: str = ""
    campaign_id: str = ""
    status: str = "UNKNOWN"
    effective_status: str = "UNKNOWN"
    creative_id: Optional[str] = None
    creative_name: Optional[str] = None
    insights: InsightsData = field(default_factory=InsightsData)


@dataclass
class AccountData:
    """Normalized ad account overview."""
    account_id: str = ""
    account_name: str = ""
    currency: str = ""
    timezone: str = ""
    account_status: int = 0               # 1=ACTIVE 2=DISABLED 3=UNSETTLED etc.
    business_name: Optional[str] = None
    amount_spent: float = 0.0             # lifetime spend in account currency
    balance: float = 0.0
    spend_cap: Optional[float] = None


# ---------------------------------------------------------------------------
# Mapper functions
# ---------------------------------------------------------------------------


def _map_insights(node: dict, date_preset: str = "last_30d") -> InsightsData:
    """
    Extract and normalize the insights sub-object from any campaign/adset/ad node.
    Facebook returns insights as {"data": [{...}]}.
    """
    insights_data: list[dict] = (node.get("insights") or {}).get("data") or []
    if not insights_data:
        return InsightsData()

    ins = insights_data[0]
    actions: list[dict] = ins.get("actions") or []
    cost_per_action: list[dict] = ins.get("cost_per_action_type") or []
    purchase_roas: list[dict] = ins.get("purchase_roas") or []
    conversion_values: list[dict] = ins.get("conversion_values") or []

    return InsightsData(
        date_start=ins.get("date_start"),
        date_stop=ins.get("date_stop"),
        spend=_float(ins.get("spend")),
        impressions=_int(ins.get("impressions")),
        reach=_int(ins.get("reach")),
        frequency=_float(ins.get("frequency")),
        clicks=_int(ins.get("clicks")),
        unique_clicks=_int(ins.get("unique_clicks")),
        link_clicks=_action(actions, "link_click"),
        ctr=_float(ins.get("ctr")),
        cpc=_float(ins.get("cpc")),
        cpm=_float(ins.get("cpm")),
        purchases=_action(actions, "purchase"),
        purchase_value=_conv_value(conversion_values),
        cost_per_purchase=_cost(cost_per_action, "purchase"),
        roas=_roas(purchase_roas),
        landing_page_views=_action(actions, "landing_page_view"),
        add_to_carts=_action(actions, "add_to_cart"),
        initiate_checkouts=_action(actions, "initiate_checkout"),
    )


def map_campaign(node: dict, date_preset: str = "last_30d") -> CampaignData:
    """
    Convert a raw Graph API campaign dict into a CampaignData object.

    Args:
        node: Raw campaign dict from GraphClient.get_campaigns().
        date_preset: Used only for InsightsData context (not re-fetched here).

    Returns:
        CampaignData — fully typed, normalized campaign.
    """
    daily_raw = node.get("daily_budget", "0")
    lifetime_raw = node.get("lifetime_budget", "0")

    return CampaignData(
        campaign_id=_str(node.get("id")),
        campaign_name=_str(node.get("name"), "Unnamed Campaign"),
        objective=node.get("objective"),
        buying_type=node.get("buying_type"),
        status=_str(node.get("status"), "UNKNOWN"),
        effective_status=_str(node.get("effective_status"), "UNKNOWN"),
        delivery_status=None,     # not available via standard Graph API
        learning_status=None,     # not available via standard Graph API
        daily_budget=_budget(daily_raw),
        lifetime_budget=_budget(lifetime_raw),
        budget_type=_budget_type(daily_raw, lifetime_raw),
        start_time=node.get("start_time"),
        end_time=node.get("stop_time"),
        bid_strategy=node.get("bid_strategy"),
        insights=_map_insights(node, date_preset),
    )


def map_adset(node: dict, date_preset: str = "last_30d") -> AdSetData:
    """Convert a raw Graph API ad set dict into an AdSetData object."""
    daily_raw = node.get("daily_budget", "0")
    lifetime_raw = node.get("lifetime_budget", "0")

    return AdSetData(
        adset_id=_str(node.get("id")),
        adset_name=_str(node.get("name"), "Unnamed Ad Set"),
        campaign_id=_str(node.get("campaign_id")),
        status=_str(node.get("status"), "UNKNOWN"),
        effective_status=_str(node.get("effective_status"), "UNKNOWN"),
        optimization_goal=node.get("optimization_goal"),
        bid_strategy=node.get("bid_strategy"),
        daily_budget=_budget(daily_raw),
        lifetime_budget=_budget(lifetime_raw),
        budget_type=_budget_type(daily_raw, lifetime_raw),
        start_time=node.get("start_time"),
        end_time=node.get("end_time"),
        insights=_map_insights(node, date_preset),
    )


def map_ad(node: dict, date_preset: str = "last_30d") -> AdData:
    """Convert a raw Graph API ad dict into an AdData object."""
    creative = node.get("creative") or {}
    return AdData(
        ad_id=_str(node.get("id")),
        ad_name=_str(node.get("name"), "Unnamed Ad"),
        adset_id=_str(node.get("adset_id")),
        campaign_id=_str(node.get("campaign_id")),
        status=_str(node.get("status"), "UNKNOWN"),
        effective_status=_str(node.get("effective_status"), "UNKNOWN"),
        creative_id=creative.get("id"),
        creative_name=creative.get("name"),
        insights=_map_insights(node, date_preset),
    )


def map_account(node: dict) -> AccountData:
    """Convert a raw Graph API account dict into an AccountData object."""
    return AccountData(
        account_id=_str(node.get("account_id") or node.get("id", "").replace("act_", "")),
        account_name=_str(node.get("name")),
        currency=_str(node.get("currency")),
        timezone=_str(node.get("timezone_name")),
        account_status=_int(node.get("account_status")),
        business_name=node.get("business_name"),
        amount_spent=_float(node.get("amount_spent")),
        balance=_float(node.get("balance")),
        spend_cap=_float(node.get("spend_cap")) if node.get("spend_cap") else None,
    )
