"""
a1_business_model.py
---------------------
A1 — Business Model Analyst

ROLE: Given primary_data, classify the business model with precision.
      Output structured JSON only. No prose in Phase 1.

KEY RULES (hard-coded, non-negotiable):
- money_engine ≤ 15 words
- value_proposition ≤ 20 words
- All categorical outputs must use exact enum values
- Unknown is always acceptable — hallucination is not
- No financial analysis here — that is A3's job
- No valuation commentary — that is A4's job
- No competitive analysis — that is A2's job

WHAT A1 FEEDS DOWNSTREAM:
- archetype → A2.5 Framework Selector (determines which metrics A3/A4 use)
- moat_type + moat_strength → A7a Decision Core (thesis strength)
- money_engine + value_proposition → injected as context block into A3, A4
"""

import json
import os
from typing import Optional

from contracts.primary_data import PrimaryData
from contracts.a1_contract import (
    A1Output, A1ValidationError, validate_a1_output,
    MoatType, MoatStrength, RevenueModel,
    BusinessModelArchetype, CustomerConcentration, PricingPower
)


# ─── Prompt Template ──────────────────────────────────────────────────────────

A1_SYSTEM_PROMPT = """You are A1, the Business Model Analyst in a multi-agent investment research pipeline.

YOUR ONLY JOB: Classify the business model of the company. Nothing else.
- Do NOT comment on valuation, price, or whether to buy/sell.
- Do NOT analyse financial statements beyond what is needed to classify the business type.
- Do NOT write prose. Return ONLY a valid JSON object matching the schema below.

CLASSIFICATION RULES:
1. moat_type: Choose ONE primary moat. If multiple exist, choose the dominant one. 
   Options: SwitchingCosts | NetworkEffects | CostAdvantage | IntangibleAssets | EfficientScale | None | Unknown

2. moat_strength: Wide (durable 10+ years) | Narrow (defensible 3–5 years) | None | Unknown

3. revenue_model: Choose the PRIMARY revenue driver.
   Options: Subscription | TransactionFee | ProductSale | ServiceContract | Licensing | Advertising | AssetYield | Hybrid | Unknown
   Use Hybrid ONLY if two revenue streams are truly inseparable and roughly equal.

4. archetype: This is critical — it determines which financial metrics are appropriate downstream.
   Options: PlatformMarketplace | AssetLightB2B | AssetHeavyIndustrial | SubscriptionSaaS | 
            ConsumerBrand | FinancialServices | CommodityCyclical | RegulatedUtility | Conglomerate | Unknown

5. money_engine: ≤15 words. How does this business generate profit? Be mechanistic, not descriptive.
   Good: "Charges take-rate on GMV; margin expands as fixed costs spread over more transactions"
   Bad: "A leading platform that connects buyers and sellers across India"

6. value_proposition: ≤20 words. Why do customers keep paying / returning?

7. customer_concentration: High (top customer >30% rev) | Medium (top 3 >50%) | Low | Unknown

8. pricing_power: Strong | Moderate | Weak | Unknown
   Strong = can raise prices above inflation without meaningful volume loss

UNKNOWN RULE: If you genuinely cannot determine a field from the data provided, use Unknown.
Do NOT guess. An Unknown is better than a confident wrong answer.
Acknowledge inferred fields in the inferred_fields list.

OUTPUT FORMAT — return ONLY this JSON, no preamble, no explanation:
{
  "moat_type": "<enum value>",
  "moat_strength": "<enum value>",
  "revenue_model": "<enum value>",
  "archetype": "<enum value>",
  "money_engine": "<≤15 words>",
  "value_proposition": "<≤20 words>",
  "customer_concentration": "<enum value>",
  "pricing_power": "<enum value>",
  "inferred_fields": ["field1", "field2"],
  "source_refs": ["Annual Report FY24", "Management commentary Q3"],
  "confidence_note": null
}"""


def build_a1_user_prompt(data: PrimaryData) -> str:
    """
    Constructs the user-turn prompt from primary_data.
    Passes only what A1 needs: company identity + high-level business context.
    Financial detail is deliberately limited here — that is A3's domain.
    """
    meta = data.meta
    income = data.income

    # Revenue trend: just last 2 years to give business context, not financial analysis
    rev_context = ""
    if income.revenue and len(income.revenue) >= 2:
        rev_context = (
            f"Revenue (last 2 years): {income.revenue[-2]:.0f} → {income.revenue[-1]:.0f} "
            f"{meta.currency} cr | "
            f"EBITDA margin (latest): {income.ebitda_margin[-1]:.1f}%"
            if income.ebitda_margin else ""
        )

    existing_context = ""
    if data.existing_holding and data.original_thesis:
        existing_context = f"\nInvestor's original thesis: {data.original_thesis}"

    prompt = f"""COMPANY: {meta.name} ({meta.ticker} | {meta.exchange.value})
SECTOR: {meta.sector} | INDUSTRY: {meta.industry}
DESCRIPTION: {meta.description or 'Not provided'}
{rev_context}
{existing_context}

TASK: Classify this business model. Return the JSON object only."""

    return prompt.strip()


# ─── Agent Runner ─────────────────────────────────────────────────────────────

def run_a1(
    data: PrimaryData,
    api_key: Optional[str] = None,
    model: str = "claude-opus-4-5",
    max_retries: int = 2,
) -> A1Output:
    """
    Runs the A1 Business Model Agent.

    Flow:
    1. Build prompt from primary_data
    2. Call Claude API
    3. Parse JSON response
    4. Validate with deterministic validator
    5. On validation failure: retry once, then raise

    Returns: validated A1Output dataclass
    Raises:  A1ValidationError if both attempts fail
    """
    import anthropic

    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
    user_prompt = build_a1_user_prompt(data)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=600,
                system=A1_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            raw_text = response.content[0].text.strip()

            # Strip any accidental markdown fences
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            raw_text = raw_text.strip()

            parsed = json.loads(raw_text)

            # Map JSON dict → typed A1Output
            output = A1Output(
                moat_type             = MoatType(parsed["moat_type"]),
                moat_strength         = MoatStrength(parsed["moat_strength"]),
                revenue_model         = RevenueModel(parsed["revenue_model"]),
                archetype             = BusinessModelArchetype(parsed["archetype"]),
                money_engine          = parsed["money_engine"],
                value_proposition     = parsed["value_proposition"],
                customer_concentration= CustomerConcentration(parsed["customer_concentration"]),
                pricing_power         = PricingPower(parsed["pricing_power"]),
                inferred_fields       = parsed.get("inferred_fields", []),
                source_refs           = parsed.get("source_refs", []),
                confidence_note       = parsed.get("confidence_note"),
            )

            # Run deterministic validator
            output = validate_a1_output(output)
            return output

        except (json.JSONDecodeError, KeyError, ValueError, A1ValidationError) as e:
            last_error = e
            print(f"[A1] Attempt {attempt} failed: {e}")
            if attempt == max_retries:
                raise A1ValidationError(
                    f"A1 failed after {max_retries} attempts. Last error: {last_error}"
                )

    # Should never reach here
    raise A1ValidationError("A1 run_a1: unexpected exit from retry loop")
