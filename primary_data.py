"""
primary_data.py  —  v2.0
--------------------------
The canonical input object for every agent in the SIPY pipeline.
All agents consume ONLY this. DataHub is responsible for populating it.
If the source (Google Sheets) changes, only DataHub changes. Agents never change.

KEY RULES:
  - Every field is Optional where data may be missing
  - All list fields preserve None for missing years (year alignment guaranteed)
  - DataHub sets data_fingerprint (SHA-256 hash of content fields)
  - schema_version bumped to 2.0 for V1 data contract

ADDITIONS IN v2.0 (no modifications to existing fields):
  IncomeStatement  : ttm_* fields, dividend_payout series
  BalanceSheet     : inventories, long_term_debt, short_term_debt, trade_receivables
  CashflowStatement: cfi, cff (investing + financing cashflows)
  ShareholdingData : new dataclass (promoters, fiis, diis, government, public)
  OperatingMetrics : new dataclass (debtor_days, inventory_days, days_payable,
                                    cash_conversion_cycle, working_capital_days)
  PrimaryData      : shareholding, operating_metrics, recent_periods,
                     reporting_frequency
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import hashlib, json


# ─── Enums ────────────────────────────────────────────────────────────────────

class Exchange(str, Enum):
    NSE    = "NSE"
    BSE    = "BSE"
    NYSE   = "NYSE"
    NASDAQ = "NASDAQ"
    OTHER  = "OTHER"


# ─── Sub-objects ──────────────────────────────────────────────────────────────

@dataclass
class CompanyMeta:
    ticker:      str
    name:        str
    exchange:    Exchange
    sector:      str
    industry:    str
    currency:    str            = "INR"
    description: Optional[str] = None     # 2-3 line business description


@dataclass
class IncomeStatement:
    """
    All values in crores (INR) or native currency unit.
    Annual series — one value per fiscal year, None where data is absent.
    TTM fields are point-in-time snapshots, not part of the annual series.
    """
    # ── Annual series (aligned to years[]) ──
    revenue:         list = field(default_factory=list)  # Sales
    revenue_growth:  list = field(default_factory=list)  # YoY %
    ebitda:          list = field(default_factory=list)  # Operating Profit
    ebitda_margin:   list = field(default_factory=list)  # OPM %
    pat:             list = field(default_factory=list)  # Net Profit
    pat_margin:      list = field(default_factory=list)  # %
    eps:             list = field(default_factory=list)
    dividend_payout: list = field(default_factory=list)  # % — v2.0
    years:           list = field(default_factory=list)  # ["FY22","FY23","FY24"]

    # ── TTM (Trailing Twelve Months) — v2.0 ──
    # Separate from annual series — point-in-time, excluded from trend calcs
    ttm_revenue:         Optional[float] = None
    ttm_ebitda:          Optional[float] = None
    ttm_ebitda_margin:   Optional[float] = None
    ttm_pat:             Optional[float] = None
    ttm_eps:             Optional[float] = None

    # ── Metadata ──
    data_source: str = ""     # 'Annual P&L' | 'Aggregated from quarterly data'


@dataclass
class BalanceSheet:
    """
    All series aligned to years[]. None preserved for missing years.
    v2.0 adds debt breakdown and working capital components.
    """
    # ── Existing fields ──
    total_assets:    list = field(default_factory=list)
    total_equity:    list = field(default_factory=list)  # Equity Capital + Reserves
    total_debt:      list = field(default_factory=list)  # Total borrowings
    cash:            list = field(default_factory=list)  # Cash Equivalents
    roce:            list = field(default_factory=list)  # % — from Ratios section
    roe:             list = field(default_factory=list)  # % — computed if available
    debt_to_equity:  list = field(default_factory=list)  # computed
    years:           list = field(default_factory=list)

    # ── New in v2.0 ──
    long_term_debt:    list = field(default_factory=list)  # Long term Borrowings
    short_term_debt:   list = field(default_factory=list)  # Short term Borrowings
    inventories:       list = field(default_factory=list)  # Inventories
    trade_receivables: list = field(default_factory=list)  # Trade receivables


@dataclass
class CashflowStatement:
    """
    All series aligned to years[]. None preserved for missing years.
    v2.0 adds investing and financing cashflows.
    """
    # ── Existing fields ──
    cfo:   list = field(default_factory=list)  # Cash from Operations
    capex: list = field(default_factory=list)  # Fixed assets purchased (negative)
    fcf:   list = field(default_factory=list)  # FCF = CFO + capex
    years: list = field(default_factory=list)

    # ── New in v2.0 ──
    cfi: list = field(default_factory=list)  # Cash from Investing Activity
    cff: list = field(default_factory=list)  # Cash from Financing Activity


@dataclass
class ShareholdingData:
    """
    Shareholding pattern — quarterly series.
    All values as decimals (0.63 = 63%).
    New dataclass in v2.0.
    """
    promoters:  list = field(default_factory=list)
    fiis:       list = field(default_factory=list)
    diis:       list = field(default_factory=list)
    government: list = field(default_factory=list)
    public:     list = field(default_factory=list)
    quarters:   list = field(default_factory=list)  # ["Dec-2023","Mar-2024",...]


@dataclass
class OperatingMetrics:
    """
    Working capital and efficiency ratios — annual series aligned to years[].
    New dataclass in v2.0.
    """
    debtor_days:           list = field(default_factory=list)
    inventory_days:        list = field(default_factory=list)
    days_payable:          list = field(default_factory=list)
    cash_conversion_cycle: list = field(default_factory=list)
    working_capital_days:  list = field(default_factory=list)
    years:                 list = field(default_factory=list)


@dataclass
class ValuationInputs:
    """Populated by investor manually or future DataHub extension."""
    current_price: Optional[float] = None
    market_cap:    Optional[float] = None  # crores
    pe_ttm:        Optional[float] = None
    pb:            Optional[float] = None
    ev_ebitda:     Optional[float] = None
    ev_sales:      Optional[float] = None
    div_yield:     Optional[float] = None  # %
    # Sector-specific
    ev_gmv:        Optional[float] = None  # platforms
    ps_ratio:      Optional[float] = None  # high-growth / SaaS
    price_to_fcf:  Optional[float] = None


@dataclass
class RiskMeta:
    """Flags pre-identified by investor or auto-detected by DataHub."""
    promoter_pledge_pct:  Optional[float] = None  # % of promoter holding pledged
    fx_exposure:          Optional[str]   = None  # "High"|"Medium"|"Low"|None
    related_party_flag:   Optional[bool]  = None
    auditor_change:       Optional[bool]  = None
    contingent_liability: Optional[float] = None  # crores
    notes:                list            = field(default_factory=list)


# ─── Master Object ─────────────────────────────────────────────────────────────

@dataclass
class PrimaryData:
    """
    The single canonical object passed to every agent.
    Constructed by DataHub. Never mutated by agents.
    """
    # ── Core financial data ──
    meta:      CompanyMeta
    income:    IncomeStatement
    balance:   BalanceSheet
    cashflow:  CashflowStatement
    valuation: ValuationInputs
    risk_meta: RiskMeta

    # ── New in v2.0 ──
    shareholding:      ShareholdingData = field(default_factory=ShareholdingData)
    operating_metrics: OperatingMetrics = field(default_factory=OperatingMetrics)

    # ── Set by DataHub — agents treat as read-only ──
    data_fingerprint:    str  = ""
    schema_version:      str  = "2.0"
    reporting_frequency: str  = ""   # 'quarterly'|'semi-annual'|'unknown'

    # ── Recent periodic trend — last 4 periods ──
    # {label: [(date_label, value), ...]} e.g. {'Sales +': [('Dec-2025', 222.0), ...]}
    recent_periods: dict = field(default_factory=dict)

    # ── Investor's existing position context (Job 1) ──
    existing_holding:   Optional[bool]  = None
    current_weight_pct: Optional[float] = None  # % of portfolio
    avg_buy_price:      Optional[float] = None
    original_thesis:    Optional[str]   = None  # free text

    def compute_fingerprint(self) -> str:
        """
        SHA-256 of all content fields (excluding fingerprint itself).
        Orchestrator uses this to skip agents if data hasn't changed.
        """
        content = {
            "meta":              self.meta.__dict__,
            "income":            self.income.__dict__,
            "balance":           self.balance.__dict__,
            "cashflow":          self.cashflow.__dict__,
            "valuation":         self.valuation.__dict__,
            "risk_meta":         self.risk_meta.__dict__,
            "shareholding":      self.shareholding.__dict__,
            "operating_metrics": self.operating_metrics.__dict__,
        }
        raw = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
