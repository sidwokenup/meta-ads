"""
Pydantic v2 domain models for campaign data.

These are the internal representations used throughout the application.
All fields are strongly typed — no plain dicts.

Budget values are already converted from cents to currency units
(i.e., divided by 100) before being stored here.
Metric strings from the Facebook JSON are converted to float/int.
"""

from typing import Optional

from pydantic import BaseModel, Field


class BudgetModel(BaseModel):
    """Campaign budget information."""

    daily_budget: Optional[float] = Field(
        None, description="Daily budget in account currency."
    )
    lifetime_budget: Optional[float] = Field(
        None, description="Lifetime budget in account currency. None if not set."
    )
    budget_type: str = Field(
        "UNKNOWN", description="'DAILY', 'LIFETIME', or 'UNKNOWN'."
    )


class DeliveryModel(BaseModel):
    """Campaign delivery and learning phase status."""

    status: str = Field(description="Campaign status: ACTIVE, PAUSED, DELETED, ARCHIVED.")
    effective_status: str = Field(
        description="Effective delivery status (may differ from status)."
    )
    delivery_status: Optional[str] = Field(
        None, description="UI delivery label: active, inactive, limited, etc."
    )
    learning_status: Optional[str] = Field(
        None, description="Learning phase: LEARNING, LEARNING_LIMITED, OFF, or None."
    )
    bid_strategy: Optional[str] = Field(
        None, description="e.g., LOWEST_COST_WITHOUT_CAP, COST_CAP."
    )
    start_date: Optional[str] = Field(None, description="Campaign start (ISO 8601).")
    end_date: Optional[str] = Field(None, description="Campaign end (ISO 8601), or None.")


class PerformanceModel(BaseModel):
    """Campaign performance metrics for a given date range."""

    spend: float = Field(0.0, description="Total spend in account currency.")
    impressions: int = Field(0, description="Total impressions.")
    reach: int = Field(0, description="Unique accounts reached.")
    frequency: float = Field(0.0, description="Average number of times each person saw the ad.")
    clicks: int = Field(0, description="Total clicks (all types).")
    link_clicks: int = Field(0, description="Link clicks only.")
    ctr: float = Field(0.0, description="Click-through rate (%).")
    cpc: float = Field(0.0, description="Cost per click.")
    cpm: float = Field(0.0, description="Cost per 1,000 impressions.")
    date_start: Optional[str] = Field(None, description="Reporting period start.")
    date_stop: Optional[str] = Field(None, description="Reporting period end.")


class ConversionModel(BaseModel):
    """Conversion and ROAS metrics."""

    purchases: int = Field(0, description="Number of purchase events.")
    cost_per_purchase: float = Field(0.0, description="Cost per purchase.")
    roas: float = Field(0.0, description="Return on ad spend (purchase ROAS).")
    conversion_value: float = Field(
        0.0, description="Total conversion value (omni_purchase)."
    )


class CampaignModel(BaseModel):
    """
    Complete campaign representation.

    Composed of sub-models for budget, delivery, performance, and conversions.
    """

    campaign_id: str = Field(description="Facebook Campaign ID.")
    campaign_name: str = Field(description="Campaign name.")
    objective: Optional[str] = Field(
        None, description="Campaign objective, e.g. OUTCOME_SALES."
    )
    budget: BudgetModel
    delivery: DeliveryModel
    performance: PerformanceModel
    conversion: ConversionModel
