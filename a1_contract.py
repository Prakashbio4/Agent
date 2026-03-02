"""
a1_contract.py
--------------
Input and Output typed contracts for A1 — Business Model Agent.

KEY RULES (from build plan):
- Output is JSON in → JSON out
- All categorical fields are enums — no free-text categorisation
- Unknown is a valid enum value — agents must not hallucinate
- money_engine must be ≤15 words (enforced by validator)
- moat_type must be a single primary moat — no compound answers
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ─── Output Enums ─────────────────────────────────────────────────────────────

class MoatType(str, Enum):
    SWITCHING_COSTS    = "SwitchingCosts"
    NETWORK_EFFECTS    = "NetworkEffects"
    COST_ADVANTAGE     = "CostAdvantage"
    INTANGIBLE_ASSETS  = "IntangibleAssets"    # brand, patents, licences
    EFFICIENT_SCALE    = "EfficientScale"       # regulated monopoly / niche
    NONE               = "None"
    UNKNOWN            = "Unknown"


class MoatStrength(str, Enum):
    WIDE     = "Wide"
    NARROW   = "Narrow"
    NONE     = "None"
    UNKNOWN  = "Unknown"


class RevenueModel(str, Enum):
    SUBSCRIPTION       = "Subscription"
    TRANSACTION_FEE    = "TransactionFee"       # marketplace / platform take-rate
    PRODUCT_SALE       = "ProductSale"          # one-time product
    SERVICE_CONTRACT   = "ServiceContract"      # project / outsourcing
    LICENSING          = "Licensing"
    ADVERTISING        = "Advertising"
    ASSET_YIELD        = "AssetYield"           # lending, leasing
    HYBRID             = "Hybrid"               # only if truly inseparable
    UNKNOWN            = "Unknown"


class BusinessModelArchetype(str, Enum):
    """
    This is the key output A2.5 (Framework Selector) reads.
    It determines which metrics A3 and A4 should use.
    """
    PLATFORM_MARKETPLACE  = "PlatformMarketplace"
    ASSET_LIGHT_B2B       = "AssetLightB2B"
    ASSET_HEAVY_INDUSTRIAL = "AssetHeavyIndustrial"
    SUBSCRIPTION_SAAS     = "SubscriptionSaaS"
    CONSUMER_BRAND        = "ConsumerBrand"
    FINANCIAL_SERVICES    = "FinancialServices"
    COMMODITY_CYCLICAL    = "CommodityCyclical"
    REGULATED_UTILITY     = "RegulatedUtility"
    CONGLOMERATE          = "Conglomerate"
    UNKNOWN               = "Unknown"


class CustomerConcentration(str, Enum):
    HIGH    = "High"    # top 1 customer >30% revenue
    MEDIUM  = "Medium"  # top 3 customers >50% revenue
    LOW     = "Low"
    UNKNOWN = "Unknown"


class PricingPower(str, Enum):
    STRONG  = "Strong"   # can raise prices above inflation without volume loss
    MODERATE = "Moderate"
    WEAK    = "Weak"
    UNKNOWN = "Unknown"


# ─── Output Contract ──────────────────────────────────────────────────────────

@dataclass
class A1Output:
    """
    A1 Business Model Agent output.
    All fields required. Unknown is always a valid fallback — never leave blank.
    """
    # Core identity
    moat_type:          MoatType
    moat_strength:      MoatStrength
    revenue_model:      RevenueModel
    archetype:          BusinessModelArchetype    # feeds A2.5 / Framework Selector

    # Business description — used as context injection for A3/A4
    money_engine:       str      # ≤15 words: how does this business make money?
    value_proposition:  str      # ≤20 words: why do customers keep paying?

    # Risk signals
    customer_concentration: CustomerConcentration
    pricing_power:          PricingPower

    # Confidence signals (for evidence gate)
    inferred_fields:    list[str] = field(default_factory=list)   # fields agent had to infer
    source_refs:        list[str] = field(default_factory=list)   # citations used
    unknown_count:      int       = 0                             # how many Unknowns in output

    # Agent metadata
    agent_version:      str = "A1-v1.0"
    confidence_note:    Optional[str] = None    # free-text flag for orchestrator


# ─── Validator ────────────────────────────────────────────────────────────────

class A1ValidationError(Exception):
    pass


def validate_a1_output(output: A1Output) -> A1Output:
    """
    Deterministic Python validator. Runs after every A1 call.
    Raises A1ValidationError on hard failures.
    On soft failures (Unknown count), caps but doesn't raise.
    """
    errors = []

    # Hard rule: money_engine word count
    word_count = len(output.money_engine.split())
    if word_count > 15:
        errors.append(
            f"money_engine exceeds 15 words ({word_count} words): '{output.money_engine}'"
        )

    # Hard rule: value_proposition word count
    vp_words = len(output.value_proposition.split())
    if vp_words > 20:
        errors.append(
            f"value_proposition exceeds 20 words ({vp_words} words)"
        )

    # Hard rule: required enum fields must not be blank strings
    enum_fields = {
        "moat_type":               output.moat_type,
        "moat_strength":           output.moat_strength,
        "revenue_model":           output.revenue_model,
        "archetype":               output.archetype,
        "customer_concentration":  output.customer_concentration,
        "pricing_power":           output.pricing_power,
    }
    for fname, val in enum_fields.items():
        if val is None:
            errors.append(f"Required field '{fname}' is None — must be an enum value or Unknown")

    if errors:
        raise A1ValidationError("\n".join(errors))

    # Soft rule: count Unknowns, set unknown_count
    unknown_count = sum(
        1 for v in enum_fields.values()
        if hasattr(v, "value") and v.value == "Unknown"
    )
    output.unknown_count = unknown_count

    # Soft rule: ≥4 Unknowns → confidence note
    if unknown_count >= 4:
        output.confidence_note = (
            f"HIGH_UNKNOWN: {unknown_count}/6 categorical fields are Unknown. "
            "Data quality may be insufficient. Orchestrator should consider capping conviction."
        )

    return output
