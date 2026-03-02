"""
mock_data.py
------------
Mock PrimaryData objects for manual testing and development.
Two contrasting examples:
  1. Zomato — platform/marketplace with GMV-based economics
  2. TCS   — asset-light B2B services with high switching costs

These are the two stocks you should run A1 against first.
IMPORTANT: These are for dev/test only. Numbers are approximate.
"""

from contracts.primary_data import (
    PrimaryData, CompanyMeta, IncomeStatement, BalanceSheet,
    CashflowStatement, ValuationInputs, RiskMeta, Exchange
)


def get_zomato() -> PrimaryData:
    """
    Zomato — PlatformMarketplace archetype.
    Expected A1 output: archetype=PlatformMarketplace, moat=NetworkEffects,
    revenue_model=TransactionFee
    P/E is NOT the right metric here. A3 should use take-rate expansion, not EPS.
    """
    p = PrimaryData(
        meta=CompanyMeta(
            ticker="ZOMATO",
            name="Zomato Ltd",
            exchange=Exchange.NSE,
            sector="Consumer Discretionary",
            industry="Online Food Delivery",
            currency="INR",
            description=(
                "India's largest food delivery and quick-commerce platform. "
                "Earns commission (take-rate) on GMV from restaurants and delivery fees from customers. "
                "Expanding into Blinkit quick-commerce."
            ),
        ),
        income=IncomeStatement(
            revenue=[1,414, 7,079, 14_112],
            revenue_growth=[None, 400.0, 99.4],
            ebitda=[-1_000, -800, 1_200],
            ebitda_margin=[-70.0, -11.3, 8.5],
            pat=[-1_222, -971, 351],
            pat_margin=[-86.4, -13.7, 2.5],
            eps=[-1.4, -1.1, 0.4],
            years=["FY22", "FY23", "FY24"],
        ),
        balance=BalanceSheet(
            total_assets=[12_000, 15_000, 22_000],
            total_equity=[10_000, 12_000, 18_000],
            total_debt=[200, 150, 100],
            cash=[8_000, 9_000, 12_000],
            roce=[-12.0, -7.0, 3.2],
            roe=[-12.5, -8.1, 1.9],
            debt_to_equity=[0.02, 0.01, 0.01],
            years=["FY22", "FY23", "FY24"],
        ),
        cashflow=CashflowStatement(
            cfo=[-900, -500, 1_100],
            capex=[-200, -300, -600],
            fcf=[-1_100, -800, 500],
            years=["FY22", "FY23", "FY24"],
        ),
        valuation=ValuationInputs(
            current_price=220.0,
            market_cap=195_000,
            pe_ttm=None,          # Not meaningful — use EV/GMV or EV/Sales
            ev_sales=12.0,
            ev_gmv=3.2,           # Key metric for platform businesses
        ),
        risk_meta=RiskMeta(
            fx_exposure="Low",
            related_party_flag=False,
        ),
        existing_holding=False,
        original_thesis=None,
    )
    p.data_fingerprint = p.compute_fingerprint()
    return p


def get_tcs() -> PrimaryData:
    """
    TCS — AssetLightB2B archetype.
    Expected A1 output: archetype=AssetLightB2B, moat=SwitchingCosts,
    revenue_model=ServiceContract
    CFO/PAT comparison IS valid here. P/E and FCF yield are meaningful.
    """
    p = PrimaryData(
        meta=CompanyMeta(
            ticker="TCS",
            name="Tata Consultancy Services",
            exchange=Exchange.NSE,
            sector="Information Technology",
            industry="IT Services & Consulting",
            currency="INR",
            description=(
                "India's largest IT services company. Provides application development, "
                "infrastructure management, and business process services to global enterprises. "
                "Long-term multi-year contracts with deep client integration."
            ),
        ),
        income=IncomeStatement(
            revenue=[191_754, 225_458, 240_893],
            revenue_growth=[16.8, 17.6, 6.8],
            ebitda=[51_500, 59_000, 61_000],
            ebitda_margin=[26.9, 26.2, 25.3],
            pat=[38_327, 42_147, 45_908],
            pat_margin=[20.0, 18.7, 19.1],
            eps=[103.6, 114.0, 124.4],
            years=["FY22", "FY23", "FY24"],
        ),
        balance=BalanceSheet(
            total_assets=[139_000, 153_000, 165_000],
            total_equity=[88_000, 98_000, 107_000],
            total_debt=[0, 0, 0],
            cash=[8_600, 9_200, 10_400],
            roce=[48.0, 50.0, 49.0],
            roe=[43.0, 46.0, 44.0],
            debt_to_equity=[0.0, 0.0, 0.0],
            years=["FY22", "FY23", "FY24"],
        ),
        cashflow=CashflowStatement(
            cfo=[38_000, 42_000, 46_000],
            capex=[-3_200, -3_400, -3_600],
            fcf=[34_800, 38_600, 42_400],
            years=["FY22", "FY23", "FY24"],
        ),
        valuation=ValuationInputs(
            current_price=3_900.0,
            market_cap=1_420_000,
            pe_ttm=31.4,
            pb=13.5,
            ev_ebitda=23.2,
            price_to_fcf=33.5,
        ),
        risk_meta=RiskMeta(
            fx_exposure="High",        # USD, EUR revenue → INR reporting
            related_party_flag=False,
            promoter_pledge_pct=0.0,
        ),
        existing_holding=True,
        current_weight_pct=8.5,
        avg_buy_price=3_200.0,
        original_thesis=(
            "Best-in-class IT services franchise with irreplaceable enterprise relationships. "
            "Own for compounding FCF yield and dividend growth."
        ),
    )
    p.data_fingerprint = p.compute_fingerprint()
    return p
