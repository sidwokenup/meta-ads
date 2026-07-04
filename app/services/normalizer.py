"""
Normalizer — converts raw Facebook GraphQL field values into Python types.

Facebook's API returns all numeric metrics as strings (e.g., "234.56", "45230").
Nested action arrays require filtering by action_type.

All conversion logic lives here so that parser.py stays clean.
"""

from typing import Any, Optional


# ------------------------------------------------------------------
# Primitive converters
# ------------------------------------------------------------------


def to_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float. Returns default on failure."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    """Safely convert a value to int. Returns default on failure."""
    if value is None:
        return default
    try:
        return int(float(value))  # handle "45230.0" strings
    except (ValueError, TypeError):
        return default


def cents_to_currency(value: Any) -> Optional[float]:
    """
    Convert a budget value from cents (string) to currency units.
    Facebook stores budgets as integer strings in subunits (e.g., "5000" = $50.00).
    Returns None if value is "0" or None (i.e., budget type not set).
    """
    raw = to_int(value, default=0)
    if raw == 0:
        return None
    return raw / 100.0


# ------------------------------------------------------------------
# Action array helpers
# ------------------------------------------------------------------


def get_action(actions: list[dict], action_type: str, default: int = 0) -> int:
    """
    Extract an integer count from a Facebook actions array.

    Args:
        actions: List of {"action_type": str, "value": str} dicts.
        action_type: The action_type to search for (e.g. "purchase", "link_click").
        default: Value to return if action_type is not found.

    Returns:
        Integer value for the matched action type.

    Example:
        actions = [{"action_type": "purchase", "value": "23"}, ...]
        get_action(actions, "purchase")  # -> 23
    """
    for item in (actions or []):
        if item.get("action_type") == action_type:
            return to_int(item.get("value"), default=default)
    return default


def get_cost(cost_per_action: list[dict], action_type: str, default: float = 0.0) -> float:
    """
    Extract a cost value from a Facebook cost_per_action_type array.

    Args:
        cost_per_action: List of {"action_type": str, "value": str} dicts.
        action_type: The action_type to search for (e.g. "purchase").
        default: Value to return if action_type is not found.

    Returns:
        Float cost value for the matched action type.
    """
    for item in (cost_per_action or []):
        if item.get("action_type") == action_type:
            return to_float(item.get("value"), default=default)
    return default


def get_roas(purchase_roas: list[dict], action_type: str = "omni_purchase", default: float = 0.0) -> float:
    """
    Extract the ROAS value from a Facebook purchase_roas array.

    Args:
        purchase_roas: List of {"action_type": str, "value": str} dicts.
        action_type: The action_type to match (default: "omni_purchase").
        default: Value to return if not found.

    Returns:
        Float ROAS value.
    """
    for item in (purchase_roas or []):
        if item.get("action_type") == action_type:
            return to_float(item.get("value"), default=default)
    return default


def get_conversion_value(
    conversion_values: list[dict],
    action_type: str = "omni_purchase",
    default: float = 0.0,
) -> float:
    """
    Extract the total conversion value from a Facebook conversion_values array.

    Args:
        conversion_values: List of {"action_type": str, "value": str} dicts.
        action_type: The action_type to match (default: "omni_purchase").
        default: Value to return if not found.

    Returns:
        Float total conversion value.
    """
    for item in (conversion_values or []):
        if item.get("action_type") == action_type:
            return to_float(item.get("value"), default=default)
    return default


# ------------------------------------------------------------------
# Budget normalization
# ------------------------------------------------------------------


def normalize_budget_type(daily_raw: Any, lifetime_raw: Any) -> str:
    """
    Determine whether a campaign uses a daily or lifetime budget.

    Facebook sets unused budget fields to "0".
    """
    if to_int(daily_raw) > 0:
        return "DAILY"
    if to_int(lifetime_raw) > 0:
        return "LIFETIME"
    return "UNKNOWN"
