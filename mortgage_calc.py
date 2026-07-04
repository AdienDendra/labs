#!/usr/bin/env python3
"""
mortgage_calc.py
================================
Kalkulator mortgage/KPR NSW untuk first-home buyer, dengan asumsi:
  - pembeli sudah Australian PR atau Australian citizen;
  - membeli rumah pertama di NSW;
  - owner occupier;
  - loan principal-and-interest selama 30 tahun;
  - fokus pada simulasi edukasi, bukan financial advice dan bukan pre-approval bank.

SCRIPT INI MENJAWAB 6 PERTANYAAN BESAR
--------------------------------------
1. Berapa estimasi net household income dari gross salary?
2. Berapa kira-kira borrowing capacity ala bank?
3. Berapa harga rumah maksimal menurut model bank dan menurut model keluarga aman?
4. Berapa cash yang dibutuhkan saat settlement?
5. Apakah target rumah tertentu feasible secara serviceability, cash, dan scheme cap?
6. Berapa total interest, total repayment, dan efek variable rate / offset / extra repayment?

MODEL YANG DIPAKAI
------------------
A. BANK MAX
   Menggunakan assessment rate = actual current rate + APRA buffer 3%.
   Ini meniru konsep umum lender: bank tidak hanya melihat cicilan hari ini, tetapi juga
   kemampuan bayar jika rate naik atau kondisi berubah. Ini tetap hanya pendekatan kasar.

B. FAMILY SAFE
   Lebih konservatif dari Bank Max.
   Menggunakan actual repayment, lalu menyisakan minimum monthly surplus setelah:
     living expenses + ownership costs + liabilities + mortgage repayment.
   Untuk keputusan keluarga, angka FAMILY SAFE biasanya lebih berguna daripada BANK MAX.

C. VARIABLE RATE / RATE PATH
   Jika --rate-path dipakai, script memproyeksikan amortisasi dengan bunga berubah.
   Format:
     "RATE:BULAN,RATE:BULAN,RATE"
   Contoh:
     "6.25:12,5.75:12,5.25"
   Artinya:
     - bulan 1-12  : 6.25%
     - bulan 13-24 : 5.75%
     - bulan 25-360: 5.25%

   Catatan penting:
     - serviceability bank memakai rate saat ini, yaitu rate pertama di --rate-path.
     - jika --rate-path tidak dipakai, script memakai --rate flat selama 30 tahun.

D. REPAYMENT STRATEGY UNTUK VARIABLE RATE
   --repayment-strategy recast
     Minimum repayment dihitung ulang saat rate berubah, berdasarkan saldo berjalan
     dan sisa tenor. Ini meniru perilaku umum variable loan ketika lender mengubah
     minimum repayment.

   --repayment-strategy hold
     Kamu mempertahankan cicilan awal jika rate turun, sehingga principal turun lebih cepat.
     Jika rate naik dan cicilan awal tidak cukup untuk minimum repayment baru, script akan
     otomatis menaikkan payment ke minimum baru agar tidak terjadi negative amortisation.

E. OFFSET DAN EXTRA REPAYMENT
   --offset-start
     Cash awal yang kamu parkir di offset account. Ini mengurangi saldo yang dikenai bunga,
     tetapi bukan repayment. Contoh: loan $900k dan offset $30k, maka bunga bulan itu dihitung
     kira-kira dari $870k.

   --offset-monthly
     Tambahan uang yang masuk ke offset setiap bulan. Ini juga bukan repayment.

   --extra-monthly
     Extra repayment langsung mengurangi principal. Dampaknya kuat di tahun awal karena
     mengurangi saldo yang dikenai bunga untuk sisa tenor.

BATASAN SCRIPT
--------------
- Tax model disederhanakan. Tidak menghitung semua offset, deduction, fringe benefit, income test,
  salary sacrifice, child care subsidy, rental income, bonus, RSU, atau family tax benefit.
- HELP/HECS dibuat manual dengan --help-debt-rate karena threshold detail berubah dan tergantung income.
- MLS memakai simplified family thresholds. Untuk tax final, pakai ATO/myTax/accountant.
- FHBAS concessional duty $800k-$1m dibuat estimasi linear konservatif. Untuk angka final,
  cek Revenue NSW calculator atau conveyancer.
- Lender policy berbeda-beda: HEM, credit score, employment type, probation, overtime/bonus,
  dependants, genuine savings, DTI cap, dan credit card treatment bisa berbeda.
- Variable rate path adalah asumsi skenario, bukan prediksi RBA/bank.

CONTOH PENGGUNAAN CASE BY CASE
------------------------------

CASE 1 — Baseline kamu, flat rate, target $950k
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 130000 \
    --rate 6.25 \
    --target-price 950000

CASE 2 — Target $1m dengan 9.7% deposit agar loan turun
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 150000 \
    --rate 6.25 \
    --deposit-pct 9.7 \
    --target-price 1000000

CASE 3 — Variable rate turun bertahap, minimum repayment ikut turun/recast
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 150000 \
    --rate 6.25 \
    --rate-path "6.25:12,5.75:12,5.25" \
    --deposit-pct 9.7 \
    --target-price 1000000

CASE 4 — Rate turun, tapi kamu tetap bayar cicilan awal supaya loan cepat turun
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 150000 \
    --rate 6.25 \
    --rate-path "6.25:12,5.75:12,5.25" \
    --repayment-strategy hold \
    --deposit-pct 9.7 \
    --target-price 1000000

CASE 5 — Tambah offset $30k dan extra repayment $500/bulan
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 150000 \
    --rate 6.25 \
    --deposit-pct 9.7 \
    --target-price 1000000 \
    --offset-start 30000 \
    --extra-monthly 500

CASE 6 — Lebih konservatif untuk keluarga: living expense naik + ownership costs
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 130000 \
    --rate 6.25 \
    --living-expenses 6200 \
    --ownership-costs 800 \
    --min-surplus 2500 \
    --target-price 900000

CASE 7 — Ada credit card limit dan car loan
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 130000 \
    --rate 6.25 \
    --cc-limit 10000 \
    --car-loan 650 \
    --target-price 900000

CASE 8 — Export amortisasi bulanan ke CSV untuk Excel/LibreOffice
  python3 mortgage_calc.py \
    --salary 115000 80000 \
    --cash 150000 \
    --rate 6.25 \
    --deposit-pct 9.7 \
    --target-price 1000000 \
    --rate-path "6.25:12,5.75:12,5.25" \
    --offset-start 30000 \
    --extra-monthly 500 \
    --csv jadwal_1jt.csv \
    --all-years
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Literal


# =============================================================================
# CONFIG — update di sini kalau aturan berubah
# =============================================================================

# Resident income tax FY2026/27, excluding Medicare levy.
# Tax brackets in decimal form: 15% = 0.15.
TAX_BRACKETS_2026_27 = [
    (18_200, 0.00),
    (45_000, 0.15),
    (135_000, 0.30),
    (190_000, 0.37),
    (float("inf"), 0.45),
]

MEDICARE_LEVY_RATE = 0.02

# Medicare Levy Surcharge FY2026/27 simplified family thresholds.
# Family threshold increases by $1,500 for each MLS dependent child after the first child.
MLS_FAMILY_BASE_THRESHOLD = 210_000
MLS_CHILD_INCREMENT_AFTER_FIRST = 1_500
MLS_FAMILY_TIERS = [
    (210_000, 0.0000),
    (246_000, 0.0100),
    (328_000, 0.0125),
    (float("inf"), 0.0150),
]

APRA_BUFFER_PCT = 3.0
CREDIT_CARD_LIMIT_FACTOR_MONTHLY = 0.038

LOAN_TERM_YEARS = 30
DEFAULT_DEPOSIT_PCT = 5.0
DEFAULT_LIVING_EXPENSES_MONTHLY = 5_200
DEFAULT_OWNERSHIP_COSTS_MONTHLY = 600
DEFAULT_MISC_BUYING_COSTS = 10_000
DEFAULT_MIN_SURPLUS_MONTHLY = 2_000

# NSW 5% Deposit Scheme / First Home Guarantee caps.
FHG_PRICE_CAPS_NSW = {
    "sydney": 1_500_000,
    "regional-centre": 1_500_000,
    "other-nsw": 800_000,
}

# NSW transfer duty FY2026/27.
# For residential properties above premium threshold, premium residential duty applies.
NSW_DUTY_BRACKETS_2026_27 = [
    (18_000, 0, 0.0125, 0),
    (38_000, 225, 0.0150, 18_000),
    (103_000, 525, 0.0175, 38_000),
    (387_000, 1_662, 0.0350, 103_000),
    (1_290_000, 11_602, 0.0450, 387_000),
    (3_870_000, 52_237, 0.0550, 1_290_000),
    (float("inf"), 194_137, 0.0700, 3_870_000),
]

FHBAS_FULL_EXEMPT_LIMIT = 800_000
FHBAS_CONCESSION_END = 1_000_000

RepaymentStrategy = Literal["recast", "hold"]


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass(frozen=True)
class RateSegment:
    rate_pct: float
    months: int


@dataclass(frozen=True)
class AmortizationRow:
    month: int
    year: int
    rate_pct: float
    payment: float
    scheduled_payment: float
    extra_repayment: float
    interest: float
    principal: float
    balance: float
    offset_balance: float
    interest_balance: float


# =============================================================================
# FORMAT HELPERS
# =============================================================================

def money(value: float) -> str:
    """Format as whole dollars, preserving negative signs."""
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def pct(value: float) -> str:
    return f"{value:.2f}%"


def months_to_years_months(months: int) -> str:
    years, rem = divmod(months, 12)
    if years and rem:
        return f"{years} years {rem} months"
    if years:
        return f"{years} years"
    return f"{rem} months"


# =============================================================================
# TAX FUNCTIONS
# =============================================================================

def income_tax_resident(taxable_income: float) -> float:
    """Resident income tax for one person, excluding Medicare levy and MLS."""
    if taxable_income <= 0:
        return 0.0

    tax = 0.0
    lower = 0.0
    for upper, rate in TAX_BRACKETS_2026_27:
        amount_in_bracket = max(0.0, min(taxable_income, upper) - lower)
        tax += amount_in_bracket * rate
        lower = upper
        if taxable_income <= upper:
            break
    return tax


def net_annual_person(
    gross: float,
    work_deduction: float = 0.0,
    help_debt_rate_pct: float = 0.0,
) -> float:
    """
    Estimate annual net income for one person.

    work_deduction reduces taxable income. Default is 0 for conservative modelling.
    help_debt_rate_pct is a manual simplified HELP/HECS repayment as % of gross.
    """
    if gross <= 0:
        return 0.0

    taxable_income = max(0.0, gross - max(0.0, work_deduction))
    income_tax = income_tax_resident(taxable_income)
    medicare_levy = taxable_income * MEDICARE_LEVY_RATE
    help_repayment = gross * max(0.0, help_debt_rate_pct) / 100
    return gross - income_tax - medicare_levy - help_repayment


def medicare_levy_surcharge_family(
    household_income: float,
    dependent_children: int,
    has_private_hospital_cover: bool,
) -> float:
    """Simplified MLS for a family/couple household."""
    if has_private_hospital_cover or household_income <= 0:
        return 0.0

    child_adjustment = max(0, dependent_children - 1) * MLS_CHILD_INCREMENT_AFTER_FIRST
    adjusted_threshold_income = household_income - child_adjustment

    for upper, rate in MLS_FAMILY_TIERS:
        if adjusted_threshold_income <= upper:
            return household_income * rate
    return 0.0


def household_net_annual(
    salaries: Iterable[float],
    dependent_children: int = 0,
    private_hospital_cover: bool = False,
    work_deduction: float = 0.0,
    help_debt_rate_pct: float = 0.0,
) -> float:
    """Estimate household net income after income tax, Medicare levy, HELP override, and MLS."""
    salaries = list(salaries)
    gross_household = sum(salaries)
    net_before_mls = sum(
        net_annual_person(
            gross=salary,
            work_deduction=work_deduction,
            help_debt_rate_pct=help_debt_rate_pct,
        )
        for salary in salaries
    )
    mls = medicare_levy_surcharge_family(
        household_income=gross_household,
        dependent_children=dependent_children,
        has_private_hospital_cover=private_hospital_cover,
    )
    return net_before_mls - mls


# =============================================================================
# LOAN MATH
# =============================================================================

def monthly_repayment(
    principal: float,
    annual_rate_pct: float,
    months: int = LOAN_TERM_YEARS * 12,
) -> float:
    """Principal-and-interest monthly repayment using the annuity formula."""
    if principal <= 0 or months <= 0:
        return 0.0

    monthly_rate = annual_rate_pct / 100 / 12
    if monthly_rate == 0:
        return principal / months

    factor = (1 + monthly_rate) ** months
    return principal * monthly_rate * factor / (factor - 1)


def loan_from_monthly_repayment(
    monthly_payment: float,
    annual_rate_pct: float,
    months: int = LOAN_TERM_YEARS * 12,
) -> float:
    """Inverse of monthly_repayment: payment -> loan principal."""
    if monthly_payment <= 0 or months <= 0:
        return 0.0

    monthly_rate = annual_rate_pct / 100 / 12
    if monthly_rate == 0:
        return monthly_payment * months

    factor = (1 + monthly_rate) ** months
    return monthly_payment * (factor - 1) / (monthly_rate * factor)


def payment_for_remaining(balance: float, annual_rate_pct: float, months_remaining: int) -> float:
    """Minimum payment required to amortise the remaining balance over remaining months."""
    return monthly_repayment(balance, annual_rate_pct, months_remaining)


def parse_rate_path(
    spec: str | None,
    fallback_rate_pct: float,
    term_months: int = LOAN_TERM_YEARS * 12,
) -> list[RateSegment]:
    """
    Parse --rate-path. If spec is None, return a flat-rate path using fallback_rate_pct.

    Accepted examples:
      "6.25"                 -> 6.25% for entire term
      "6.25:12,5.75"         -> 12 months at 6.25%, then 5.75% to the end
      "6.25:12,5.75:12,5.25" -> 12 + 12 months, then 5.25% to the end
    """
    if spec is None or not spec.strip():
        return [RateSegment(fallback_rate_pct, term_months)]

    segments: list[RateSegment] = []
    used_months = 0
    parts = [p.strip() for p in spec.split(",") if p.strip()]

    if not parts:
        raise ValueError("--rate-path is empty. Example: '6.25:12,5.75:12,5.25'")

    for idx, part in enumerate(parts):
        rate_text, sep, duration_text = part.partition(":")
        try:
            rate_pct = float(rate_text)
        except ValueError as exc:
            raise ValueError(f"Invalid rate in --rate-path segment '{part}'") from exc

        if rate_pct < 0:
            raise ValueError("Rates in --rate-path cannot be negative")

        is_last = idx == len(parts) - 1
        if sep:
            try:
                months = int(duration_text)
            except ValueError as exc:
                raise ValueError(f"Invalid month duration in --rate-path segment '{part}'") from exc
            if months <= 0:
                if is_last:
                    months = term_months - used_months
                else:
                    raise ValueError("Only the last --rate-path segment may use duration 0 or blank")
        else:
            if not is_last:
                raise ValueError("Only the last --rate-path segment may omit duration")
            months = term_months - used_months

        if used_months + months > term_months:
            raise ValueError("--rate-path durations exceed loan term")

        if months > 0:
            segments.append(RateSegment(rate_pct=rate_pct, months=months))
            used_months += months

    if used_months < term_months:
        # If all segments had explicit durations but did not fill the term, extend the last rate.
        last = segments[-1]
        segments[-1] = RateSegment(last.rate_pct, last.months + (term_months - used_months))

    return segments


def first_rate(rate_segments: list[RateSegment]) -> float:
    return rate_segments[0].rate_pct


def rate_path_label(rate_segments: list[RateSegment]) -> str:
    if len(rate_segments) == 1:
        return f"{pct(rate_segments[0].rate_pct)} flat"
    chunks = []
    used = 0
    total = sum(s.months for s in rate_segments)
    for segment in rate_segments:
        used += segment.months
        duration = f"{segment.months}m" if used < total else "remaining"
        chunks.append(f"{pct(segment.rate_pct)} for {duration}")
    return "; ".join(chunks)


def amortization_schedule(
    principal: float,
    rate_segments: list[RateSegment],
    repayment_strategy: RepaymentStrategy = "recast",
    offset_start: float = 0.0,
    offset_monthly: float = 0.0,
    extra_monthly: float = 0.0,
    term_months: int = LOAN_TERM_YEARS * 12,
) -> list[AmortizationRow]:
    """
    Build monthly amortization rows.

    recast:
      payment recalculated at each rate segment using balance + remaining term.

    hold:
      maintain initial payment where possible, but never below the recast minimum required
      at each rate segment. This models keeping repayments high after rate cuts.
    """
    if principal <= 0:
        return []

    if repayment_strategy not in ("recast", "hold"):
        raise ValueError("repayment_strategy must be either 'recast' or 'hold'")

    offset_balance = max(0.0, offset_start)
    offset_monthly = max(0.0, offset_monthly)
    extra_monthly = max(0.0, extra_monthly)

    balance = principal
    rows: list[AmortizationRow] = []
    month = 0
    initial_payment = monthly_repayment(principal, rate_segments[0].rate_pct, term_months)

    for segment in rate_segments:
        if balance <= 0:
            break

        months_remaining_at_segment = term_months - month
        recast_payment = payment_for_remaining(balance, segment.rate_pct, months_remaining_at_segment)

        if repayment_strategy == "recast":
            scheduled_payment = recast_payment
        else:
            # Hold the initial payment if rates fall, but lift to recast minimum if rates rise enough.
            scheduled_payment = max(initial_payment, recast_payment)

        monthly_rate = segment.rate_pct / 100 / 12

        for _ in range(segment.months):
            if balance <= 0 or month >= term_months:
                break

            month += 1
            interest_balance = max(balance - offset_balance, 0.0)
            interest = interest_balance * monthly_rate

            intended_payment = scheduled_payment + extra_monthly
            principal_part = intended_payment - interest

            if principal_part < 0:
                # Defensive fallback. This should not happen with recast/hold logic unless offset/rates
                # are extreme, but avoid negative amortisation silently compounding.
                raise ValueError(
                    f"Payment is below monthly interest in month {month}; "
                    "increase repayment or use recast strategy."
                )

            if principal_part >= balance:
                principal_part = balance
                actual_payment = interest + principal_part
                balance = 0.0
            else:
                actual_payment = intended_payment
                balance -= principal_part

            rows.append(
                AmortizationRow(
                    month=month,
                    year=(month - 1) // 12 + 1,
                    rate_pct=segment.rate_pct,
                    payment=actual_payment,
                    scheduled_payment=scheduled_payment,
                    extra_repayment=min(extra_monthly, max(actual_payment - scheduled_payment, 0.0)),
                    interest=interest,
                    principal=principal_part,
                    balance=max(balance, 0.0),
                    offset_balance=offset_balance,
                    interest_balance=interest_balance,
                )
            )

            offset_balance += offset_monthly

    return rows


# =============================================================================
# SERVICEABILITY / NSW SCHEME FUNCTIONS
# =============================================================================

def monthly_liabilities(
    credit_card_limit: float = 0.0,
    car_loan_monthly: float = 0.0,
    personal_loan_monthly: float = 0.0,
    other_commitments_monthly: float = 0.0,
) -> float:
    """Monthly commitments. Credit card model uses limit, not balance."""
    return (
        max(0.0, credit_card_limit) * CREDIT_CARD_LIMIT_FACTOR_MONTHLY
        + max(0.0, car_loan_monthly)
        + max(0.0, personal_loan_monthly)
        + max(0.0, other_commitments_monthly)
    )


def max_loan_bank_assessed(
    net_monthly: float,
    current_rate_pct: float,
    living_expenses_monthly: float,
    ownership_costs_monthly: float,
    liabilities_monthly: float,
    term_months: int = LOAN_TERM_YEARS * 12,
) -> float:
    """Approximate bank borrowing capacity at current rate + APRA buffer."""
    assessment_rate = current_rate_pct + APRA_BUFFER_PCT
    available = net_monthly - living_expenses_monthly - ownership_costs_monthly - liabilities_monthly
    return loan_from_monthly_repayment(available, assessment_rate, term_months)


def safe_loan_family(
    net_monthly: float,
    current_rate_pct: float,
    living_expenses_monthly: float,
    ownership_costs_monthly: float,
    liabilities_monthly: float,
    min_surplus_monthly: float,
    term_months: int = LOAN_TERM_YEARS * 12,
) -> float:
    """Family-safe loan based on actual repayment plus a monthly surplus buffer."""
    available = (
        net_monthly
        - living_expenses_monthly
        - ownership_costs_monthly
        - liabilities_monthly
        - min_surplus_monthly
    )
    return loan_from_monthly_repayment(available, current_rate_pct, term_months)


def nsw_transfer_duty(price: float) -> float:
    """NSW residential transfer duty FY2026/27, including premium bracket."""
    if price <= 0:
        return 0.0
    for upper, base, rate, start in NSW_DUTY_BRACKETS_2026_27:
        if price <= upper:
            duty = base + (price - start) * rate
            return max(20.0, duty)
    raise RuntimeError("Unreachable duty bracket")


def nsw_fhbas_duty(price: float) -> float:
    """Estimated NSW FHBAS duty for eligible first-home buyer."""
    if price <= FHBAS_FULL_EXEMPT_LIMIT:
        return 0.0
    if price < FHBAS_CONCESSION_END:
        full_duty_at_1m = nsw_transfer_duty(FHBAS_CONCESSION_END)
        ratio = (price - FHBAS_FULL_EXEMPT_LIMIT) / (FHBAS_CONCESSION_END - FHBAS_FULL_EXEMPT_LIMIT)
        return full_duty_at_1m * ratio
    return nsw_transfer_duty(price)


def fhg_price_cap(area: str) -> float:
    return FHG_PRICE_CAPS_NSW[area]


def loan_from_price(price: float, deposit_pct: float) -> float:
    return max(0.0, price) * (1 - deposit_pct / 100)


def price_from_loan(loan: float, deposit_pct: float) -> float:
    loan_ratio = 1 - deposit_pct / 100
    if loan_ratio <= 0:
        return 0.0
    return max(0.0, loan) / loan_ratio


def split_total_income(total_gross: float, ratios: list[float]) -> list[float]:
    return [total_gross * ratio for ratio in ratios]


def required_gross_for_loan(
    target_loan: float,
    current_rate_pct: float,
    current_salaries: list[float],
    living_expenses_monthly: float,
    ownership_costs_monthly: float,
    liabilities_monthly: float,
    dependent_children: int,
    private_hospital_cover: bool,
    work_deduction: float,
    help_debt_rate_pct: float,
    term_months: int = LOAN_TERM_YEARS * 12,
) -> float:
    """Reverse calculation: target loan -> approximate gross household income required."""
    current_total = sum(current_salaries)
    if target_loan <= 0 or current_total <= 0:
        return 0.0

    ratios = [salary / current_total for salary in current_salaries]
    assessed_payment = monthly_repayment(target_loan, current_rate_pct + APRA_BUFFER_PCT, term_months)
    required_net_monthly = (
        assessed_payment + living_expenses_monthly + ownership_costs_monthly + liabilities_monthly
    )

    lo = max(1.0, required_net_monthly * 12 * 0.65)
    hi = 1_500_000.0

    for _ in range(30):
        net_hi = household_net_annual(
            split_total_income(hi, ratios),
            dependent_children=dependent_children,
            private_hospital_cover=private_hospital_cover,
            work_deduction=work_deduction,
            help_debt_rate_pct=help_debt_rate_pct,
        )
        if net_hi / 12 >= required_net_monthly:
            break
        hi *= 1.5

    for _ in range(80):
        mid = (lo + hi) / 2
        net_mid = household_net_annual(
            split_total_income(mid, ratios),
            dependent_children=dependent_children,
            private_hospital_cover=private_hospital_cover,
            work_deduction=work_deduction,
            help_debt_rate_pct=help_debt_rate_pct,
        )
        if net_mid / 12 < required_net_monthly:
            lo = mid
        else:
            hi = mid

    return hi


# =============================================================================
# SCENARIO REPORT
# =============================================================================

@dataclass
class Scenario:
    salaries: list[float]
    cash: float
    rate: float
    target_price: float | None = None
    rate_path: str | None = None
    repayment_strategy: RepaymentStrategy = "recast"
    area: str = "sydney"
    deposit_pct: float = DEFAULT_DEPOSIT_PCT
    use_fhg: bool = True
    use_fhbas: bool = True
    living_expenses_monthly: float = DEFAULT_LIVING_EXPENSES_MONTHLY
    ownership_costs_monthly: float = DEFAULT_OWNERSHIP_COSTS_MONTHLY
    min_surplus_monthly: float = DEFAULT_MIN_SURPLUS_MONTHLY
    misc_buying_costs: float = DEFAULT_MISC_BUYING_COSTS
    credit_card_limit: float = 0.0
    car_loan_monthly: float = 0.0
    personal_loan_monthly: float = 0.0
    other_commitments_monthly: float = 0.0
    dependent_children: int = 2
    private_hospital_cover: bool = False
    work_deduction: float = 0.0
    help_debt_rate_pct: float = 0.0
    offset_start: float = 0.0
    offset_monthly: float = 0.0
    extra_monthly: float = 0.0
    csv_path: str | None = None
    show_all_years: bool = False

    def run(self) -> str:
        self._validate()

        rate_segments = parse_rate_path(self.rate_path, fallback_rate_pct=self.rate)
        current_rate = first_rate(rate_segments)
        gross = sum(self.salaries)
        net_annual = household_net_annual(
            self.salaries,
            dependent_children=self.dependent_children,
            private_hospital_cover=self.private_hospital_cover,
            work_deduction=self.work_deduction,
            help_debt_rate_pct=self.help_debt_rate_pct,
        )
        net_monthly = net_annual / 12
        liabilities = monthly_liabilities(
            credit_card_limit=self.credit_card_limit,
            car_loan_monthly=self.car_loan_monthly,
            personal_loan_monthly=self.personal_loan_monthly,
            other_commitments_monthly=self.other_commitments_monthly,
        )

        bank_loan_cap = max_loan_bank_assessed(
            net_monthly=net_monthly,
            current_rate_pct=current_rate,
            living_expenses_monthly=self.living_expenses_monthly,
            ownership_costs_monthly=self.ownership_costs_monthly,
            liabilities_monthly=liabilities,
        )
        bank_price_by_income = price_from_loan(bank_loan_cap, self.deposit_pct)
        scheme_cap = fhg_price_cap(self.area) if self.use_fhg else float("inf")
        bank_price_cap = min(bank_price_by_income, scheme_cap)

        family_safe_loan = safe_loan_family(
            net_monthly=net_monthly,
            current_rate_pct=current_rate,
            living_expenses_monthly=self.living_expenses_monthly,
            ownership_costs_monthly=self.ownership_costs_monthly,
            liabilities_monthly=liabilities,
            min_surplus_monthly=self.min_surplus_monthly,
        )
        family_safe_price = min(price_from_loan(family_safe_loan, self.deposit_pct), bank_price_cap)

        lines = [
            "=" * 78,
            "  NSW MORTGAGE CALCULATOR v3 — PR/CITIZEN + FIRST HOME BUYER ASSUMPTION",
            "=" * 78,
            f"  Gross household income      : {money(gross):>14} /year",
            f"  Estimated net income        : {money(net_annual):>14} /year ({money(net_monthly)}/month)",
            f"  Current actual rate         : {pct(current_rate)}",
            f"  Bank assessment rate        : {pct(current_rate + APRA_BUFFER_PCT)}",
            f"  Rate path                   : {rate_path_label(rate_segments)}",
            f"  Repayment strategy          : {self.repayment_strategy}",
            f"  Loan term                   : {LOAN_TERM_YEARS} years",
            f"  Deposit assumption          : {self.deposit_pct:.1f}%",
            f"  Area / FHG cap              : {self.area} / {self._scheme_cap_text()}",
            "",
            "  MONTHLY ASSUMPTIONS",
            f"    Living expenses           : {money(self.living_expenses_monthly):>14}",
            f"    Ownership costs           : {money(self.ownership_costs_monthly):>14}",
            f"    Liabilities/commitments   : {money(liabilities):>14}",
            f"    Family-safe surplus       : {money(self.min_surplus_monthly):>14}",
            "",
            "  BANK MAX — assessed at current rate + APRA buffer",
            f"    Max loan by income        : {money(bank_loan_cap):>14}",
            f"    Max price by income       : {money(bank_price_by_income):>14}",
            f"    Max price after FHG cap   : {money(bank_price_cap):>14}",
            f"    Initial repayment         : {money(monthly_repayment(loan_from_price(bank_price_cap, self.deposit_pct), current_rate)):>14} /month",
            "",
            "  FAMILY SAFE — actual repayment + ownership costs + monthly surplus",
            f"    Safe loan                 : {money(family_safe_loan):>14}",
            f"    Safe price                : {money(family_safe_price):>14}",
            f"    Initial repayment         : {money(monthly_repayment(loan_from_price(family_safe_price, self.deposit_pct), current_rate)):>14} /month",
            f"    Weekly equivalent         : {money(monthly_repayment(loan_from_price(family_safe_price, self.deposit_pct), current_rate) * 12 / 52):>14} /week",
            "",
            self.cash_breakdown(family_safe_price, label="FAMILY SAFE PRICE"),
        ]

        if self.target_price is not None:
            lines.extend(
                self.target_report(
                    target_price=self.target_price,
                    bank_loan_cap=bank_loan_cap,
                    net_monthly=net_monthly,
                    liabilities=liabilities,
                    current_rate=current_rate,
                    rate_segments=rate_segments,
                    gross=gross,
                )
            )

        amort_price = self.target_price if self.target_price is not None else family_safe_price
        amort_label = "TARGET PRICE" if self.target_price is not None else "FAMILY SAFE PRICE"
        lines.extend(self.amortization_report(amort_price, amort_label, rate_segments))
        lines.append(self.notes())
        return "\n".join(lines)

    def target_report(
        self,
        target_price: float,
        bank_loan_cap: float,
        net_monthly: float,
        liabilities: float,
        current_rate: float,
        rate_segments: list[RateSegment],
        gross: float,
    ) -> list[str]:
        loan = loan_from_price(target_price, self.deposit_pct)
        assessed_payment = monthly_repayment(loan, current_rate + APRA_BUFFER_PCT)
        initial_payment = monthly_repayment(loan, current_rate)
        monthly_after_target = (
            net_monthly
            - self.living_expenses_monthly
            - self.ownership_costs_monthly
            - liabilities
            - initial_payment
        )
        required_gross = required_gross_for_loan(
            target_loan=loan,
            current_rate_pct=current_rate,
            current_salaries=self.salaries,
            living_expenses_monthly=self.living_expenses_monthly,
            ownership_costs_monthly=self.ownership_costs_monthly,
            liabilities_monthly=liabilities,
            dependent_children=self.dependent_children,
            private_hospital_cover=self.private_hospital_cover,
            work_deduction=self.work_deduction,
            help_debt_rate_pct=self.help_debt_rate_pct,
        )

        cash_needed = self.cash_needed_for_price(target_price)
        cash_shortfall = max(0.0, cash_needed - self.cash)
        cash_ok = self.cash >= cash_needed
        serviceability_ok = loan <= bank_loan_cap + 1
        scheme_ok = (not self.use_fhg) or target_price <= fhg_price_cap(self.area)
        overall_ok = cash_ok and serviceability_ok and scheme_ok
        dti = loan / gross if gross > 0 else float("inf")
        gross_gap = max(0.0, required_gross - gross)

        warnings = self.target_warnings(target_price, dti, cash_shortfall, rate_segments)

        lines = [
            "",
            "-" * 78,
            f"  TARGET PROPERTY: {money(target_price)}",
            "-" * 78,
            f"    Loan amount               : {money(loan):>14}",
            f"    Initial repayment         : {money(initial_payment):>14} /month",
            f"    Assessed repayment        : {money(assessed_payment):>14} /month",
            f"    Net left after target     : {money(monthly_after_target):>14} /month",
            f"    Required gross household  : {money(required_gross):>14} /year",
            f"    Gross income gap          : {money(gross_gap):>14} /year",
            f"    Debt-to-income ratio      : {dti:.2f}x",
            f"    Serviceability status     : {'LIKELY PASS model' if serviceability_ok else 'NOT PASS model'}",
            f"    Cash status               : {'OK' if cash_ok else 'SHORTFALL ' + money(cash_shortfall)}",
            f"    Scheme cap status         : {'OK' if scheme_ok else 'EXCEEDS FHG CAP'}",
            f"    Overall purchase status   : {'FEASIBLE model' if overall_ok else 'NOT FEASIBLE model'}",
            "",
            self.cash_breakdown(target_price, label="TARGET PRICE"),
        ]

        if warnings:
            lines.append("  WARNINGS")
            lines.extend(f"    - {warning}" for warning in warnings)

        return lines

    def amortization_report(
        self,
        price: float,
        label: str,
        rate_segments: list[RateSegment],
    ) -> list[str]:
        loan = loan_from_price(price, self.deposit_pct)
        rows = amortization_schedule(
            principal=loan,
            rate_segments=rate_segments,
            repayment_strategy=self.repayment_strategy,
            offset_start=self.offset_start,
            offset_monthly=self.offset_monthly,
            extra_monthly=self.extra_monthly,
        )

        if self.csv_path:
            self.write_csv(rows)

        total_paid = sum(row.payment for row in rows)
        total_interest = sum(row.interest for row in rows)
        total_principal = sum(row.principal for row in rows)
        deposit = price * self.deposit_pct / 100
        duty = self.duty_for_price(price)
        upfront = deposit + duty + self.misc_buying_costs
        total_cash_outflow = total_paid + upfront
        payoff_months = rows[-1].month if rows else 0
        first = rows[0] if rows else None
        last = rows[-1] if rows else None

        flat_rows = amortization_schedule(
            principal=loan,
            rate_segments=[RateSegment(rate_segments[0].rate_pct, LOAN_TERM_YEARS * 12)],
            repayment_strategy="recast",
        )
        flat_interest = sum(row.interest for row in flat_rows)
        interest_delta = total_interest - flat_interest

        lines = [
            "",
            "-" * 78,
            f"  AMORTISATION — {label} ({money(price)}, loan {money(loan)})",
            f"  Rate assumption: {rate_path_label(rate_segments)}",
            "-" * 78,
        ]

        if first and last:
            lines.extend([
                f"    First payment             : {money(first.payment):>14} /month ({money(first.payment * 12 / 52)}/week)",
                f"    Payoff time               : {months_to_years_months(payoff_months):>14}",
                "",
                "    Komposisi cicilan bergeser karena interest dihitung dari saldo berjalan:",
                f"      Month 1                 : interest {money(first.interest)} vs principal {money(first.principal)}",
                f"      Last month              : interest {money(last.interest)} vs principal {money(last.principal)}",
            ])

        payment_changes = self.payment_change_lines(rows)
        if payment_changes:
            lines.extend(["", "    Payment changes:"])
            lines.extend(payment_changes)

        lines.extend([
            "",
            f"    {'Yr':>4} | {'Paid/yr':>11} | {'Interest':>11} | {'Principal':>11} | {'Balance':>13} | {'Offset':>11}",
            "    " + "-" * 78,
        ])
        lines.extend(self.yearly_rows(rows))

        lines.extend([
            "",
            "    TOTAL CASH OUTFLOW — no tax effects, no selling costs, no property growth",
            f"      Loan principal          : {money(loan):>14}",
            f"      Principal repaid        : {money(total_principal):>14}",
            f"      Total interest          : {money(total_interest):>14}",
            f"      Total loan payments     : {money(total_paid):>14}",
            f"      Upfront cash            : {money(upfront):>14}  (deposit + duty + buying costs)",
            f"      Total cash outflow      : {money(total_cash_outflow):>14}  ({total_cash_outflow / price:.2f}x purchase price)",
        ])

        if len(rate_segments) > 1 or self.offset_start or self.offset_monthly or self.extra_monthly or self.repayment_strategy == "hold":
            direction = "more" if interest_delta > 0 else "less"
            lines.append(
                f"      Interest vs flat {pct(rate_segments[0].rate_pct)} : "
                f"{money(abs(interest_delta))} {direction}"
            )

        if self.csv_path:
            lines.append(f"      CSV monthly schedule    : {self.csv_path}")

        return lines

    def yearly_rows(self, rows: list[AmortizationRow]) -> list[str]:
        if not rows:
            return []

        result: list[str] = []
        max_year = rows[-1].year
        for year in range(1, max_year + 1):
            year_rows = [row for row in rows if row.year == year]
            if not year_rows:
                continue
            if not (self.show_all_years or year <= 5 or year % 5 == 0 or year == max_year):
                continue
            paid = sum(row.payment for row in year_rows)
            interest = sum(row.interest for row in year_rows)
            principal = sum(row.principal for row in year_rows)
            balance = year_rows[-1].balance
            offset = year_rows[-1].offset_balance
            result.append(
                f"    {year:>4} | {money(paid):>11} | {money(interest):>11} | "
                f"{money(principal):>11} | {money(balance):>13} | {money(offset):>11}"
            )
        return result

    def payment_change_lines(self, rows: list[AmortizationRow]) -> list[str]:
        if not rows:
            return []
        changes: list[str] = []
        previous_payment: float | None = None
        previous_rate: float | None = None
        for row in rows:
            payment_changed = previous_payment is None or abs(row.scheduled_payment - previous_payment) > 0.50
            rate_changed = previous_rate is None or abs(row.rate_pct - previous_rate) > 0.0001
            if payment_changed or rate_changed:
                changes.append(
                    f"      Month {row.month:>3} @ {pct(row.rate_pct):>6}: "
                    f"scheduled {money(row.scheduled_payment)}/month"
                )
                previous_payment = row.scheduled_payment
                previous_rate = row.rate_pct
        return changes

    def write_csv(self, rows: list[AmortizationRow]) -> None:
        path = Path(self.csv_path or "")
        with path.open("w", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "month", "year", "rate_pct", "payment", "scheduled_payment", "extra_repayment",
                "interest", "principal", "balance", "offset_balance", "interest_balance",
            ])
            for row in rows:
                writer.writerow([
                    row.month,
                    row.year,
                    f"{row.rate_pct:.4f}",
                    f"{row.payment:.2f}",
                    f"{row.scheduled_payment:.2f}",
                    f"{row.extra_repayment:.2f}",
                    f"{row.interest:.2f}",
                    f"{row.principal:.2f}",
                    f"{row.balance:.2f}",
                    f"{row.offset_balance:.2f}",
                    f"{row.interest_balance:.2f}",
                ])

    def duty_for_price(self, price: float) -> float:
        return nsw_fhbas_duty(price) if self.use_fhbas else nsw_transfer_duty(price)

    def cash_needed_for_price(self, price: float) -> float:
        deposit = price * self.deposit_pct / 100
        duty = self.duty_for_price(price)
        return deposit + duty + self.misc_buying_costs

    def cash_breakdown(self, price: float, label: str) -> str:
        deposit = price * self.deposit_pct / 100
        duty = self.duty_for_price(price)
        total_needed = deposit + duty + self.misc_buying_costs
        leftover = self.cash - total_needed
        duty_label = "FHBAS duty" if self.use_fhbas else "standard duty"
        status = "surplus -> offset/buffer" if leftover >= 0 else "SHORTFALL"
        return (
            f"  CASH AT SETTLEMENT — {label} ({money(price)})\n"
            f"    Deposit                  : {money(deposit):>14}\n"
            f"    NSW {duty_label:<14}: {money(duty):>14}\n"
            f"    Buying costs buffer      : {money(self.misc_buying_costs):>14}\n"
            f"    Total cash needed        : {money(total_needed):>14}\n"
            f"    Cash available           : {money(self.cash):>14}\n"
            f"    Remaining / shortfall    : {money(leftover):>14}  -> {status}\n"
        )

    def target_warnings(
        self,
        target_price: float,
        dti: float,
        cash_shortfall: float,
        rate_segments: list[RateSegment],
    ) -> list[str]:
        warnings: list[str] = []
        if self.use_fhg and target_price > fhg_price_cap(self.area):
            warnings.append(f"Target exceeds 5% Deposit Scheme cap for {self.area}: {money(fhg_price_cap(self.area))}.")
        if self.use_fhbas and target_price >= FHBAS_CONCESSION_END:
            warnings.append("FHBAS concession does not apply at $1m or above; standard duty is used.")
        if cash_shortfall > 0:
            warnings.append(f"Cash shortfall at settlement: {money(cash_shortfall)}.")
        if self.deposit_pct <= 5 and not self.use_fhg:
            warnings.append("Deposit <=5% without FHG may trigger LMI or lender refusal.")
        if not self.private_hospital_cover and sum(self.salaries) >= MLS_FAMILY_BASE_THRESHOLD:
            warnings.append("No private hospital cover selected; simplified MLS may reduce net income.")
        if dti >= 6:
            warnings.append("DTI is 6x or above; APRA high-DTI limits/lender policy may become a major constraint.")
        elif dti >= 5:
            warnings.append("DTI is above 5x; approval may be sensitive to lender policy and expenses.")
        if len(rate_segments) > 1:
            warnings.append("Variable rate path is a scenario, not a prediction. Re-check with current rates before applying.")
        if self.ownership_costs_monthly <= 0:
            warnings.append("Ownership costs are set to $0; this may understate real monthly cost after buying.")
        return warnings

    def notes(self) -> str:
        return (
            "\n"
            "  NOTES\n"
            "    - Bank Max is not approval. Lender calculators and credit policy can be stricter.\n"
            "    - FAMILY SAFE is usually the better household decision metric.\n"
            "    - Variable rate path is an assumption. Rates can move differently.\n"
            "    - Total cash outflow is not the same as 'house value'. It ignores property growth,\n"
            "      selling costs, refinancing, tax, insurance claim events, and opportunity cost.\n"
            "    - Offset reduces interest but does not reduce loan principal unless you make repayment.\n"
            "    - Extra repayment reduces principal directly and can shorten payoff time.\n"
        )

    def _scheme_cap_text(self) -> str:
        return "FHG disabled" if not self.use_fhg else money(fhg_price_cap(self.area))

    def _validate(self) -> None:
        if not self.salaries or any(s < 0 for s in self.salaries):
            raise ValueError("--salary must contain one or more non-negative gross incomes")
        if self.cash < 0:
            raise ValueError("--cash cannot be negative")
        if self.rate < 0:
            raise ValueError("--rate cannot be negative")
        if self.area not in FHG_PRICE_CAPS_NSW:
            raise ValueError(f"--area must be one of: {', '.join(FHG_PRICE_CAPS_NSW)}")
        if not (0 < self.deposit_pct < 100):
            raise ValueError("--deposit-pct must be between 0 and 100")
        if self.repayment_strategy not in ("recast", "hold"):
            raise ValueError("--repayment-strategy must be recast or hold")
        # Validate rate path early.
        parse_rate_path(self.rate_path, fallback_rate_pct=self.rate)


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="NSW mortgage calculator with serviceability, FHBAS/FHG, amortisation, variable rates, offset, and extra repayments."
    )
    parser.add_argument("--salary", nargs="+", type=float, required=True, metavar="GROSS", help="Gross annual salary per person, e.g. --salary 115000 80000")
    parser.add_argument("--cash", type=float, default=0.0, help="Cash available for deposit, duty, buying costs, and buffer")
    parser.add_argument("--rate", type=float, default=6.25, help="Current actual annual interest rate in percent")
    parser.add_argument("--target-price", type=float, default=None, help="Target purchase price")
    parser.add_argument("--rate-path", type=str, default=None, metavar="SPEC", help='Variable rate path, e.g. "6.25:12,5.75:12,5.25". First rate is current rate for serviceability.')
    parser.add_argument("--repayment-strategy", choices=["recast", "hold"], default="recast", help="recast = minimum repayment changes with rate; hold = keep initial repayment if rates fall")

    parser.add_argument("--area", choices=sorted(FHG_PRICE_CAPS_NSW.keys()), default="sydney", help="NSW area for 5%% Deposit Scheme cap")
    parser.add_argument("--deposit-pct", type=float, default=DEFAULT_DEPOSIT_PCT, help="Deposit percentage; default 5 for 5%% Deposit Scheme simulation")
    parser.add_argument("--no-fhg", action="store_true", help="Disable 5%% Deposit Scheme price cap")
    parser.add_argument("--no-fhbas", action="store_true", help="Disable NSW First Home Buyers Assistance Scheme")

    parser.add_argument("--living-expenses", type=float, default=DEFAULT_LIVING_EXPENSES_MONTHLY, help="Monthly pre-home living expenses")
    parser.add_argument("--ownership-costs", type=float, default=DEFAULT_OWNERSHIP_COSTS_MONTHLY, help="Monthly ownership costs: council, water, insurance, maintenance, strata")
    parser.add_argument("--min-surplus", type=float, default=DEFAULT_MIN_SURPLUS_MONTHLY, help="Minimum monthly surplus after expenses and mortgage")
    parser.add_argument("--misc-costs", type=float, default=DEFAULT_MISC_BUYING_COSTS, help="Buying costs buffer: conveyancing, inspection, moving, initial repairs")

    parser.add_argument("--cc-limit", type=float, default=0.0, help="Total credit card limit; model uses limit x 3.8%% monthly")
    parser.add_argument("--car-loan", type=float, default=0.0, help="Monthly car loan repayment")
    parser.add_argument("--personal-loan", type=float, default=0.0, help="Monthly personal loan repayment")
    parser.add_argument("--other-commitments", type=float, default=0.0, help="Other monthly commitments")

    parser.add_argument("--children", type=int, default=2, help="Dependent children for simplified MLS threshold")
    parser.add_argument("--private-hospital-cover", action="store_true", help="Eligible private hospital cover; avoids simplified MLS")
    parser.add_argument("--work-deduction", type=float, default=0.0, help="Optional annual work deduction per person")
    parser.add_argument("--help-debt-rate", type=float, default=0.0, help="Simplified HELP/HECS repayment as percent of gross income")

    parser.add_argument("--offset-start", type=float, default=0.0, help="Initial cash parked in offset account")
    parser.add_argument("--offset-monthly", type=float, default=0.0, help="Monthly additional cash parked in offset account")
    parser.add_argument("--extra-monthly", type=float, default=0.0, help="Monthly extra repayment directly reducing principal")

    parser.add_argument("--csv", type=str, default=None, metavar="FILE", help="Export monthly amortisation schedule to CSV")
    parser.add_argument("--all-years", action="store_true", help="Show all yearly amortisation rows instead of year 1-5 + every 5 years")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    scenario = Scenario(
        salaries=args.salary,
        cash=args.cash,
        rate=args.rate,
        target_price=args.target_price,
        rate_path=args.rate_path,
        repayment_strategy=args.repayment_strategy,
        area=args.area,
        deposit_pct=args.deposit_pct,
        use_fhg=not args.no_fhg,
        use_fhbas=not args.no_fhbas,
        living_expenses_monthly=args.living_expenses,
        ownership_costs_monthly=args.ownership_costs,
        min_surplus_monthly=args.min_surplus,
        misc_buying_costs=args.misc_costs,
        credit_card_limit=args.cc_limit,
        car_loan_monthly=args.car_loan,
        personal_loan_monthly=args.personal_loan,
        other_commitments_monthly=args.other_commitments,
        dependent_children=args.children,
        private_hospital_cover=args.private_hospital_cover,
        work_deduction=args.work_deduction,
        help_debt_rate_pct=args.help_debt_rate,
        offset_start=args.offset_start,
        offset_monthly=args.offset_monthly,
        extra_monthly=args.extra_monthly,
        csv_path=args.csv,
        show_all_years=args.all_years,
    )
    print(scenario.run())


if __name__ == "__main__":
    main()
