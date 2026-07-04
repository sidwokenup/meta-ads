"""
Parser — converts raw Facebook GraphQL JSON into CampaignModel objects.

Receives the raw JSON dict from a captured /api/graphql/ response and
extracts the campaign edges, delegating all type conversion to normalizer.py.

Never touches HTML, CSS selectors, XPath, or Playwright locators.
"""

from typing import Any, Optional

from app.core.logger import logger
from app.models.campaign import (
    BudgetModel,
    CampaignModel,
    ConversionModel,
    DeliveryModel,
    PerformanceModel,
)
from app.services.normalizer import (
    cents_to_currency,
    get_action,
    get_conversion_value,
    get_cost,
    get_roas,
    normalize_budget_type,
    to_float,
    to_int,
)


class ParseError(Exception):
    """Raised when the JSON structure cannot be parsed as campaign data."""


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def parse_graphql_response(raw_json: dict) -> list[CampaignModel]:
    """
    Parse a raw /api/graphql/ JSON response and return a list of CampaignModel.

    Tries multiple known JSON paths to find the campaign edges, since
    Facebook's response structure may vary slightly between query versions.

    Args:
        raw_json: Parsed JSON dict from the GraphQL response body.

    Returns:
        List of CampaignModel objects. Empty list if no campaigns found.

    Raises:
        ParseError: If the JSON is structurally unrecognisable as campaign data.
    """
    edges = _find_campaign_edges(raw_json)
    if edges is None:
        raise ParseError(
            "Could not locate campaign edges in GraphQL response. "
            "The response may not be a campaign table query."
        )

    if not edges:
        logger.warning("Campaign edges list is empty — no campaigns in this response.")
        return []

    campaigns: list[CampaignModel] = []
    for edge in edges:
        node = edge.get("node", {})
        if not node:
            continue
        try:
            campaign = _parse_campaign_node(node)
            campaigns.append(campaign)
        except Exception as exc:
            campaign_id = node.get("id", "unknown")
            logger.warning(f"Failed to parse campaign node {campaign_id}: {exc}")

    logger.info(f"Parsed {len(campaigns)} campaign(s) from GraphQL response.")
    return campaigns


# ------------------------------------------------------------------
# Path discovery
# ------------------------------------------------------------------


def _find_campaign_edges(raw_json: dict) -> Optional[list]:
    """
    Attempt to locate the campaign edges list inside the response.

    Facebook's GraphQL responses use different nesting paths depending on
    the query version. We try known paths in order.
    """
    data = raw_json.get("data", {})

    # Path 1: data.node.ad_account.campaigns.edges
    try:
        edges = (
            data
            .get("node", {})
            .get("ad_account", {})
            .get("campaigns", {})
            .get("edges", None)
        )
        if isinstance(edges, list):
            return edges
    except AttributeError:
        pass

    # Path 2: data.ad_account.campaigns.edges
    try:
        edges = (
            data
            .get("ad_account", {})
            .get("campaigns", {})
            .get("edges", None)
        )
        if isinstance(edges, list):
            return edges
    except AttributeError:
        pass

    # Path 3: data.campaigns.edges (flattened)
    try:
        edges = data.get("campaigns", {}).get("edges", None)
        if isinstance(edges, list):
            return edges
    except AttributeError:
        pass

    # Path 4: data.viewer.ad_accounts[0].campaigns.edges
    try:
        accounts = data.get("viewer", {}).get("ad_accounts", {}).get("nodes", [])
        if accounts:
            edges = accounts[0].get("campaigns", {}).get("edges", None)
            if isinstance(edges, list):
                return edges
    except (AttributeError, IndexError):
        pass

    return None


def has_campaign_data(raw_json: dict) -> bool:
    """
    Quick check: does this GraphQL response look like a campaign table response?
    Used by the collector to filter relevant responses before full parsing.
    """
    return _find_campaign_edges(raw_json) is not None


# ------------------------------------------------------------------
# Node parsing
# ------------------------------------------------------------------


def _parse_campaign_node(node: dict) -> CampaignModel:
    """
    Parse a single campaign node dict into a CampaignModel.
    """
    campaign_id: str = str(node.get("id", ""))
    campaign_name: str = node.get("name", "Unnamed Campaign")
    objective: Optional[str] = node.get("objective")

    # --- Budget ---
    daily_raw = node.get("daily_budget", "0")
    lifetime_raw = node.get("lifetime_budget", "0")
    budget = BudgetModel(
        daily_budget=cents_to_currency(daily_raw),
        lifetime_budget=cents_to_currency(lifetime_raw),
        budget_type=normalize_budget_type(daily_raw, lifetime_raw),
    )

    # --- Delivery ---
    delivery_info = node.get("delivery_info", {}) or {}
    learning_info = node.get("learning_phase_info", {}) or {}
    delivery = DeliveryModel(
        status=node.get("status", "UNKNOWN"),
        effective_status=node.get("effective_status", "UNKNOWN"),
        delivery_status=delivery_info.get("status"),
        learning_status=learning_info.get("status"),
        bid_strategy=node.get("bid_strategy"),
        start_date=node.get("start_time"),
        end_date=node.get("stop_time"),
    )

    # --- Insights (performance + conversion) ---
    insights_data: list[dict] = (
        node.get("insights", {}) or {}
    ).get("data", []) or []

    if insights_data:
        ins = insights_data[0]
        actions: list[dict] = ins.get("actions", []) or []
        cost_per_action: list[dict] = ins.get("cost_per_action_type", []) or []
        purchase_roas: list[dict] = ins.get("purchase_roas", []) or []
        conversion_values: list[dict] = ins.get("conversion_values", []) or []

        performance = PerformanceModel(
            spend=to_float(ins.get("spend")),
            impressions=to_int(ins.get("impressions")),
            reach=to_int(ins.get("reach")),
            frequency=to_float(ins.get("frequency")),
            clicks=to_int(ins.get("clicks")),
            link_clicks=get_action(actions, "link_click"),
            ctr=to_float(ins.get("ctr")),
            cpc=to_float(ins.get("cpc")),
            cpm=to_float(ins.get("cpm")),
            date_start=ins.get("date_start"),
            date_stop=ins.get("date_stop"),
        )
        conversion = ConversionModel(
            purchases=get_action(actions, "purchase"),
            cost_per_purchase=get_cost(cost_per_action, "purchase"),
            roas=get_roas(purchase_roas),
            conversion_value=get_conversion_value(conversion_values),
        )
    else:
        performance = PerformanceModel()
        conversion = ConversionModel()

    return CampaignModel(
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        objective=objective,
        budget=budget,
        delivery=delivery,
        performance=performance,
        conversion=conversion,
    )


# Public alias — used by campaign_collector.py for Graph API responses where
# campaign nodes are already extracted from response["data"] and iterated directly.
parse_campaign_node = _parse_campaign_node
