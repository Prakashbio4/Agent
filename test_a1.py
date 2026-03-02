"""
test_a1.py
----------
Track B — Eval tests for A1 Business Model Agent.
Per build plan: tests MUST exist before implementation is considered complete.
All 5 tests should fail if A1 is not implemented correctly.

Test categories (per build plan):
  T1: missing industry → Unknown archetype expected
  T2: moat_strength Unknown → should not raise, should flag
  T3: money_engine >15 words → validator must catch and raise
  T4: inferred-heavy output → inferred_fields must be populated
  T5: no description provided → agent should degrade gracefully, not hallucinate

Run with: python -m pytest tests/test_a1.py -v
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from contracts.primary_data import (
    PrimaryData, CompanyMeta, IncomeStatement, BalanceSheet,
    CashflowStatement, ValuationInputs, RiskMeta, Exchange
)
from contracts.a1_contract import (
    A1Output, A1ValidationError, validate_a1_output,
    MoatType, MoatStrength, RevenueModel,
    BusinessModelArchetype, CustomerConcentration, PricingPower
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_minimal_primary_data(
    sector="Unknown",
    industry="Unknown",
    description=None
) -> PrimaryData:
    """Minimal valid PrimaryData for testing."""
    return PrimaryData(
        meta=CompanyMeta(
            ticker="TEST",
            name="Test Corp",
            exchange=Exchange.NSE,
            sector=sector,
            industry=industry,
            description=description,
        ),
        income=IncomeStatement(
            revenue=[100.0, 120.0],
            revenue_growth=[20.0],
            ebitda=[20.0, 25.0],
            ebitda_margin=[20.0, 20.8],
            pat=[12.0, 15.0],
            pat_margin=[12.0, 12.5],
            eps=[5.0, 6.0],
            years=["FY23", "FY24"],
        ),
        balance=BalanceSheet(years=["FY23", "FY24"]),
        cashflow=CashflowStatement(years=["FY23", "FY24"]),
        valuation=ValuationInputs(),
        risk_meta=RiskMeta(),
    )


def make_valid_a1_output(**overrides) -> A1Output:
    """Returns a valid A1Output. Use overrides to inject bad fields for testing."""
    defaults = dict(
        moat_type=MoatType.SWITCHING_COSTS,
        moat_strength=MoatStrength.NARROW,
        revenue_model=RevenueModel.SUBSCRIPTION,
        archetype=BusinessModelArchetype.ASSET_LIGHT_B2B,
        money_engine="Charges monthly SaaS fee; upsells seats as client scales",
        value_proposition="Reduces manual effort; deeply embedded in client workflows",
        customer_concentration=CustomerConcentration.LOW,
        pricing_power=PricingPower.MODERATE,
    )
    defaults.update(overrides)
    return A1Output(**defaults)


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestA1Validator:

    # T1 — Validator must NOT raise when archetype=Unknown (graceful degradation)
    def test_T1_unknown_archetype_is_valid(self):
        """
        FAILURE CATEGORY: enum_unknown_rejection
        If sector/industry are missing, archetype=Unknown is the correct output.
        Validator must accept Unknown — not raise as if it's a missing field.
        """
        output = make_valid_a1_output(archetype=BusinessModelArchetype.UNKNOWN)
        result = validate_a1_output(output)
        assert result.unknown_count >= 1, "unknown_count should be at least 1"
        # Should NOT raise

    # T2 — moat_strength Unknown should increment unknown_count, not raise
    def test_T2_unknown_moat_strength_counted(self):
        """
        FAILURE CATEGORY: unknown_count_not_tracked
        Unknown moat_strength must increment unknown_count.
        """
        output = make_valid_a1_output(moat_strength=MoatStrength.UNKNOWN)
        result = validate_a1_output(output)
        assert result.unknown_count >= 1

    # T3 — money_engine >15 words must raise A1ValidationError
    def test_T3_money_engine_exceeds_15_words_raises(self):
        """
        FAILURE CATEGORY: hard_rule_not_enforced
        money_engine is a hard rule: >15 words must raise, not silently truncate.
        """
        long_engine = (
            "This company earns revenue by selling subscription software "
            "to enterprise clients across multiple geographies and verticals"
        )
        assert len(long_engine.split()) > 15, "Test setup: ensure >15 words"

        output = make_valid_a1_output(money_engine=long_engine)
        with pytest.raises(A1ValidationError, match="money_engine exceeds 15 words"):
            validate_a1_output(output)

    # T4 — When ≥4 fields are Unknown, confidence_note must be set
    def test_T4_high_unknown_sets_confidence_note(self):
        """
        FAILURE CATEGORY: confidence_flag_missing
        If agent returns 4+ Unknowns (data quality issue), 
        confidence_note must be populated for the Orchestrator to act on.
        """
        output = make_valid_a1_output(
            moat_type=MoatType.UNKNOWN,
            moat_strength=MoatStrength.UNKNOWN,
            archetype=BusinessModelArchetype.UNKNOWN,
            customer_concentration=CustomerConcentration.UNKNOWN,
            pricing_power=PricingPower.UNKNOWN,
        )
        result = validate_a1_output(output)
        assert result.confidence_note is not None, (
            "confidence_note must be set when unknown_count >= 4"
        )
        assert "HIGH_UNKNOWN" in result.confidence_note

    # T5 — None value in required field must raise, not silently pass
    def test_T5_none_in_required_field_raises(self):
        """
        FAILURE CATEGORY: missing_required_field_not_caught
        If a required enum field is None (e.g. agent returned partial JSON),
        validator must raise A1ValidationError, not return a broken output object.
        """
        output = make_valid_a1_output()
        output.moat_type = None  # Simulate missing field

        with pytest.raises(A1ValidationError, match="Required field 'moat_type' is None"):
            validate_a1_output(output)


class TestA1PromptBuilder:

    # T6 — Prompt must degrade gracefully when description is None
    def test_T6_no_description_builds_prompt_without_error(self):
        """
        FAILURE CATEGORY: prompt_build_failure_on_missing_data
        DataHub may not always have a description. Prompt builder must not crash.
        """
        from agents.a1_business_model import build_a1_user_prompt

        data = make_minimal_primary_data(description=None)
        prompt = build_a1_user_prompt(data)

        assert "COMPANY:" in prompt
        assert "Not provided" in prompt    # Expected fallback text
        assert "TASK:" in prompt

    # T7 — Existing holding context injected when present
    def test_T7_existing_thesis_injected_in_prompt(self):
        """
        FAILURE CATEGORY: context_injection_missing
        If investor has provided original_thesis, it must appear in the prompt
        so A1 can consider business model drift against original intent.
        """
        from agents.a1_business_model import build_a1_user_prompt

        data = make_minimal_primary_data()
        data.existing_holding = True
        data.original_thesis = "High quality NBFC with clean book and secular growth"

        prompt = build_a1_user_prompt(data)
        assert "High quality NBFC" in prompt, (
            "Original thesis must be injected into A1 prompt for existing holdings"
        )


# ─── Test runner (for direct execution) ──────────────────────────────────────

if __name__ == "__main__":
    import traceback

    tests = TestA1Validator()
    prompt_tests = TestA1PromptBuilder()
    all_tests = [
        ("T1 Unknown archetype valid",          tests.test_T1_unknown_archetype_is_valid),
        ("T2 Unknown moat_strength counted",    tests.test_T2_unknown_moat_strength_counted),
        ("T3 money_engine >15 words raises",    tests.test_T3_money_engine_exceeds_15_words_raises),
        ("T4 High unknown → confidence_note",   tests.test_T4_high_unknown_sets_confidence_note),
        ("T5 None required field raises",       tests.test_T5_none_in_required_field_raises),
        ("T6 No description → no crash",        prompt_tests.test_T6_no_description_builds_prompt_without_error),
        ("T7 Thesis injected in prompt",        prompt_tests.test_T7_existing_thesis_injected_in_prompt),
    ]

    passed, failed = 0, 0
    for name, fn in all_tests:
        try:
            fn()
            print(f"  ✓  {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗  {name}")
            print(f"     {e}")
            failed += 1

    print(f"\n{passed} passed / {failed} failed")
