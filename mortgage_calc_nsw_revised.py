#!/usr/bin/env python3
"""
GPT 5.5 Research — 2026-07-03

mortgage_calc_nsw_revised.py — Kalkulator KPR NSW untuk first home buyer
asumsi: sudah Australian PR / citizen, membeli rumah pertama, owner occupier.

Tujuan script:
  1. Menghitung net income dari gross income per orang.
  2. Menghitung borrowing capacity ala bank dengan assessment rate = bunga aktual + APRA buffer 3%.
  3. Menghitung cicilan bulanan/mingguan pada bunga aktual.
  4. Menghitung NSW transfer duty FY2026/27 + estimasi FHBAS.
  5. Menghitung cash at settlement: deposit + duty + buying costs.
  6. Memisahkan dua angka penting:
       - BANK MAX     : kira-kira batas maksimal yang bisa lolos serviceability bank.
       - FAMILY SAFE  : batas lebih konservatif berdasarkan net income, real expenses, dan sisa buffer.
  7. Skenario mundur: target harga rumah -> estimasi gross household income yang dibutuhkan.

Contoh penggunaan paling relevan untuk keluarga 4 orang di Sydney:

  # Basic: income $115k + $80k, cash $130k, rate 6.25%, target rumah $1m
  python3 mortgage_calc_nsw_revised.py \
      --salary 115000 80000 \
      --cash 130000 \
      --rate 6.25 \
      --target-price 1000000

  # Lebih realistis: living expenses dinaikkan, buffer keluarga minimal $2k/bulan
  python3 mortgage_calc_nsw_revised.py \
      --salary 115000 80000 \
      --cash 130000 \
      --rate 6.25 \
      --living-expenses 6200 \
      --min-surplus 2000 \
      --target-price 950000

  # Simulasi rate cut ke 5.75%
  python3 mortgage_calc_nsw_revised.py \
      --salary 115000 80000 \
      --cash 130000 \
      --rate 5.75 \
      --target-price 950000

  # Ada limit kartu kredit $10k — bank biasanya menilai limit, bukan balance saja
  python3 mortgage_calc_nsw_revised.py \
      --salary 115000 80000 \
      --cash 130000 \
      --rate 6.25 \
      --cc-limit 10000 \
      --target-price 950000

  # Other NSW area: 5% Deposit Scheme cap lebih rendah daripada Sydney/regional centres
  python3 mortgage_calc_nsw_revised.py \
      --salary 115000 80000 \
      --cash 130000 \
      --rate 6.25 \
      --area other-nsw \
      --target-price 900000

  # Kalau tidak pakai 5% Deposit Scheme, misalnya deposit 10% dan tidak membatasi price cap FHG
  python3 mortgage_calc_nsw_revised.py \
      --salary 115000 80000 \
      --cash 180000 \
      --rate 6.25 \
      --deposit-pct 10 \
      --no-fhg \
      --target-price 1000000

Catatan penting:
  - Ini alat edukasi, bukan financial advice dan bukan approval dari bank.
  - Lender memakai policy internal, HEM/expense benchmark, credit score, employment type,
    dependants, liabilities, existing commitments, dan data real bank statement.
  - Transfer duty/FHBAS/FHG berubah dari waktu ke waktu. Update constants di bagian CONFIG.
  - FHBAS concessional formula di range $800k-$1m dibuat sebagai estimasi konservatif linear.
    Untuk angka final, cek Revenue NSW calculator/conveyancer.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Iterable


# =============================================================================
# CONFIG — update di sini kalau aturan berubah
# =============================================================================

# Income tax resident FY2026/27.
# Bracket pertama $18,201-$45,000 turun dari 16% ke 15% mulai 1 Juli 2026.
TAX_BRACKETS_2026_27 = [
    (18_200, 0.00),
    (45_000, 0.15),
    (135_000, 0.30),
    (190_000, 0.37),
    (float("inf"), 0.45),
]

MEDICARE_LEVY_RATE = 0.02

# Medicare Levy Surcharge (MLS) simplified family thresholds.
# MLS hanya relevan jika tidak punya eligible private hospital cover.
# Family threshold naik $1,500 untuk setiap dependent child setelah anak pertama.
MLS_FAMILY_BASE_THRESHOLD = 202_000
MLS_CHILD_INCREMENT_AFTER_FIRST = 1_500
MLS_FAMILY_TIERS = [
    # (upper_income, surcharge_rate)
    (202_000, 0.0000),
    (236_000, 0.0100),
    (316_000, 0.0125),
    (float("inf"), 0.0150),
]

# APRA serviceability buffer. Bank menilai repayment di actual rate + buffer.
APRA_BUFFER_PCT = 3.0

# Common lender approximation: credit card commitment dihitung dari LIMIT, bukan balance.
# Angka 3.8%/month adalah pendekatan kasar. Tiap lender bisa berbeda.
CREDIT_CARD_LIMIT_FACTOR_MONTHLY = 0.038

LOAN_TERM_YEARS = 30
DEFAULT_DEPOSIT_PCT = 5.0

# NSW 5% Deposit Scheme / First Home Guarantee price caps.
# Sydney masuk capital city. Regional centres NSW: Central Coast, Coffs Harbour-Grafton,
# Illawarra, Mid North Coast, Richmond-Tweed, Newcastle and Lake Macquarie.
FHG_PRICE_CAPS_NSW = {
    "sydney": 1_500_000,
    "regional-centre": 1_500_000,
    "other-nsw": 800_000,
}

# NSW transfer duty FY2026/27.
# Format: (upper_limit, base_duty, marginal_rate, bracket_start)
# Marginal rate ditulis decimal: 4.5% = 0.045.
NSW_DUTY_BRACKETS_2026_27 = [
    (18_000, 0, 0.0125, 0),
    (38_000, 225, 0.0150, 18_000),
    (103_000, 525, 0.0175, 38_000),
    (387_000, 1_662, 0.0350, 103_000),
    (1_290_000, 11_602, 0.0450, 387_000),
    (3_870_000, 52_237, 0.0550, 1_290_000),
    (float("inf"), 194_137, 0.0700, 3_870_000),  # premium residential duty
]

# NSW First Home Buyers Assistance Scheme for new/existing residential home.
FHBAS_FULL_EXEMPT_LIMIT = 800_000
FHBAS_CONCESSION_END = 1_000_000

# Default assumption for family 4 in Sydney. Better override with your real monthly budget.
DEFAULT_LIVING_EXPENSES_MONTHLY = 5_200
DEFAULT_MISC_BUYING_COSTS = 10_000
DEFAULT_MIN_SURPLUS_MONTHLY = 2_000


# =============================================================================
# MONEY HELPERS
# =============================================================================

def money(value: float) -> str:
    """Format angka dollar tanpa cents."""
    return f"${value:,.0f}"


def pct(value: float) -> str:
    return f"{value:.2f}%"


# =============================================================================
# TAX FUNCTIONS
# =============================================================================

def income_tax_resident(gross: float) -> float:
    """Resident income tax per orang, belum termasuk Medicare levy/MLS."""
    if gross <= 0:
        return 0.0

    tax = 0.0
    lower = 0.0
    for upper, rate in TAX_BRACKETS_2026_27:
        taxable_in_bracket = max(0.0, min(gross, upper) - lower)
        tax += taxable_in_bracket * rate
        lower = upper
        if gross <= upper:
            break
    return tax


def net_annual_person(
    gross: float,
    work_deduction: float = 0.0,
    help_debt_rate_pct: float = 0.0,
) -> float:
    """
    Gross -> net annual per orang.

    work_deduction:
      Optional deduction untuk taxable income. Default 0 agar konservatif.
      Kalau mau simulasi $1k work deduction FY2026/27, pakai --work-deduction 1000.

    help_debt_rate_pct:
      Simplified HELP/HECS repayment sebagai % dari gross. Default 0.
      Karena threshold HELP cukup detail dan berubah, script ini pakai manual override.
    """
    taxable_income = max(0.0, gross - work_deduction)
    tax = income_tax_resident(taxable_income)
    medicare = taxable_income * MEDICARE_LEVY_RATE
    help_repayment = gross * (help_debt_rate_pct / 100)
    return gross - tax - medicare - help_repayment


def medicare_levy_surcharge_family(
    household_income: float,
    dependent_children: int,
    has_private_hospital_cover: bool,
) -> float:
    """
    Simplified Medicare Levy Surcharge untuk family.

    Jika punya eligible private hospital cover, MLS = 0.
    Family threshold dinaikkan $1,500 untuk tiap dependent child setelah anak pertama.
    """
    if has_private_hospital_cover:
        return 0.0

    child_adjustment = max(0, dependent_children - 1) * MLS_CHILD_INCREMENT_AFTER_FIRST
    adjusted_income = household_income - child_adjustment

    for upper, rate in MLS_FAMILY_TIERS:
        if adjusted_income <= upper:
            return household_income * rate
    return 0.0


def household_net_annual(
    salaries: Iterable[float],
    dependent_children: int = 0,
    private_hospital_cover: bool = False,
    work_deduction: float = 0.0,
    help_debt_rate_pct: float = 0.0,
) -> float:
    """Net household income setelah income tax, Medicare levy, optional HELP, dan optional MLS."""
    salaries = list(salaries)
    gross_household = sum(salaries)
    net_before_mls = sum(
        net_annual_person(
            gross=s,
            work_deduction=work_deduction,
            help_debt_rate_pct=help_debt_rate_pct,
        )
        for s in salaries
    )
    mls = medicare_levy_surcharge_family(
        household_income=gross_household,
        dependent_children=dependent_children,
        has_private_hospital_cover=private_hospital_cover,
    )
    return net_before_mls - mls


# =============================================================================
# LOAN / SERVICEABILITY FUNCTIONS
# =============================================================================

def monthly_repayment(
    principal: float,
    annual_rate_pct: float,
    years: int = LOAN_TERM_YEARS,
) -> float:
    """Repayment bulanan principal-and-interest, rumus anuitas standar."""
    if principal <= 0:
        return 0.0

    months = years * 12
    monthly_rate = annual_rate_pct / 100 / 12

    if monthly_rate == 0:
        return principal / months

    factor = (1 + monthly_rate) ** months
    return principal * monthly_rate * factor / (factor - 1)


def loan_from_monthly_repayment(
    monthly_payment: float,
    annual_rate_pct: float,
    years: int = LOAN_TERM_YEARS,
) -> float:
    """Inverse dari monthly_repayment: repayment -> principal."""
    if monthly_payment <= 0:
        return 0.0

    months = years * 12
    monthly_rate = annual_rate_pct / 100 / 12

    if monthly_rate == 0:
        return monthly_payment * months

    factor = (1 + monthly_rate) ** months
    return monthly_payment * (factor - 1) / (monthly_rate * factor)


def monthly_liabilities(
    credit_card_limit: float = 0.0,
    car_loan_monthly: float = 0.0,
    personal_loan_monthly: float = 0.0,
    other_commitments_monthly: float = 0.0,
) -> float:
    """Monthly commitments yang mengurangi serviceability."""
    cc_commitment = credit_card_limit * CREDIT_CARD_LIMIT_FACTOR_MONTHLY
    return cc_commitment + car_loan_monthly + personal_loan_monthly + other_commitments_monthly


def max_loan_bank_assessed(
    net_monthly: float,
    actual_rate_pct: float,
    living_expenses_monthly: float,
    liabilities_monthly: float,
    years: int = LOAN_TERM_YEARS,
) -> float:
    """
    Borrowing capacity kasar ala bank.

    Bank menilai loan repayment di assessment rate = actual rate + APRA buffer,
    lalu melihat apakah net monthly masih cukup setelah living expenses + liabilities.
    """
    assessment_rate = actual_rate_pct + APRA_BUFFER_PCT
    available_for_assessed_repayment = net_monthly - living_expenses_monthly - liabilities_monthly
    return loan_from_monthly_repayment(
        monthly_payment=available_for_assessed_repayment,
        annual_rate_pct=assessment_rate,
        years=years,
    )


def safe_loan_family(
    net_monthly: float,
    actual_rate_pct: float,
    living_expenses_monthly: float,
    liabilities_monthly: float,
    min_surplus_monthly: float,
    years: int = LOAN_TERM_YEARS,
) -> float:
    """
    Family-safe loan.

    Beda dengan bank max:
      - memakai actual repayment, bukan assessed repayment.
      - menyisakan minimum monthly surplus setelah expense + liabilities.
    """
    affordable_actual_payment = (
        net_monthly
        - living_expenses_monthly
        - liabilities_monthly
        - min_surplus_monthly
    )
    return loan_from_monthly_repayment(
        monthly_payment=affordable_actual_payment,
        annual_rate_pct=actual_rate_pct,
        years=years,
    )


# =============================================================================
# NSW DUTY / FHBAS / FHG FUNCTIONS
# =============================================================================

def nsw_transfer_duty(price: float) -> float:
    """NSW transfer duty FY2026/27, termasuk premium residential duty bracket."""
    if price <= 0:
        return 0.0

    for upper, base, rate, start in NSW_DUTY_BRACKETS_2026_27:
        if price <= upper:
            duty = base + (price - start) * rate
            return max(20.0, duty) if price > 0 else 0.0
    raise RuntimeError("Unreachable transfer duty bracket")


def nsw_fhbas_duty(price: float) -> float:
    """
    NSW FHBAS estimated duty for eligible first home buyer.

    Official rule:
      - <= $800k: full exemption.
      - > $800k and < $1m: concessional rate.
      - >= $1m: no FHBAS concession, standard transfer duty.

    Formula concessional rate tidak ditulis sebagai public bracket table di halaman ringkas.
    Untuk calculator ini, dipakai estimasi konservatif linear dari $0 duty di $800k
    ke full standard duty at $1m.
    """
    if price <= FHBAS_FULL_EXEMPT_LIMIT:
        return 0.0

    if price < FHBAS_CONCESSION_END:
        full_duty_at_1m = nsw_transfer_duty(FHBAS_CONCESSION_END)
        concession_ratio = (price - FHBAS_FULL_EXEMPT_LIMIT) / (
            FHBAS_CONCESSION_END - FHBAS_FULL_EXEMPT_LIMIT
        )
        return full_duty_at_1m * concession_ratio

    return nsw_transfer_duty(price)


def fhg_price_cap(area: str) -> float:
    """5% Deposit Scheme price cap untuk NSW berdasarkan area."""
    return FHG_PRICE_CAPS_NSW[area]


def price_from_loan(loan: float, deposit_pct: float) -> float:
    """Loan -> purchase price dengan deposit percentage tertentu."""
    loan_ratio = 1 - deposit_pct / 100
    if loan_ratio <= 0:
        return 0.0
    return loan / loan_ratio


def loan_from_price(price: float, deposit_pct: float) -> float:
    """Purchase price -> loan amount dengan deposit percentage tertentu."""
    return price * (1 - deposit_pct / 100)


# =============================================================================
# REVERSE CALCULATION
# =============================================================================

def split_total_income(total_gross: float, salary_ratios: list[float]) -> list[float]:
    """Bagi total gross ke beberapa income berdasarkan rasio income saat ini."""
    return [total_gross * r for r in salary_ratios]


def required_gross_for_loan(
    target_loan: float,
    actual_rate_pct: float,
    current_salaries: list[float],
    living_expenses_monthly: float,
    liabilities_monthly: float,
    dependent_children: int,
    private_hospital_cover: bool,
    work_deduction: float,
    help_debt_rate_pct: float,
    years: int = LOAN_TERM_YEARS,
) -> float:
    """
    Hitung mundur: target loan -> gross household income yang dibutuhkan.

    Karena tax progresif dan household bisa terdiri dari 2 income, dipakai binary search.
    Split income mengikuti proporsi income sekarang, sehingga lebih realistis daripada
    menganggap semua income milik 1 orang.
    """
    total_current = sum(current_salaries)
    if total_current <= 0:
        return 0.0

    ratios = [s / total_current for s in current_salaries]
    assessed_payment = monthly_repayment(
        principal=target_loan,
        annual_rate_pct=actual_rate_pct + APRA_BUFFER_PCT,
        years=years,
    )
    required_net_monthly = assessed_payment + living_expenses_monthly + liabilities_monthly

    lo = max(1.0, required_net_monthly * 12 * 0.7)
    hi = 1_500_000.0

    # Pastikan upper bound cukup tinggi.
    for _ in range(20):
        salaries_at_hi = split_total_income(hi, ratios)
        net_hi = household_net_annual(
            salaries=salaries_at_hi,
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
        salaries_at_mid = split_total_income(mid, ratios)
        net_mid = household_net_annual(
            salaries=salaries_at_mid,
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
    area: str = "sydney"
    deposit_pct: float = DEFAULT_DEPOSIT_PCT
    use_fhg: bool = True
    use_fhbas: bool = True
    living_expenses_monthly: float = DEFAULT_LIVING_EXPENSES_MONTHLY
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

    def run(self, target_price: float | None = None) -> str:
        self._validate()

        gross = sum(self.salaries)
        net_annual = household_net_annual(
            salaries=self.salaries,
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
            actual_rate_pct=self.rate,
            living_expenses_monthly=self.living_expenses_monthly,
            liabilities_monthly=liabilities,
        )
        bank_price_cap_from_income = price_from_loan(bank_loan_cap, self.deposit_pct)

        scheme_cap = fhg_price_cap(self.area) if self.use_fhg else float("inf")
        bank_price_cap = min(bank_price_cap_from_income, scheme_cap)

        family_safe_loan = safe_loan_family(
            net_monthly=net_monthly,
            actual_rate_pct=self.rate,
            living_expenses_monthly=self.living_expenses_monthly,
            liabilities_monthly=liabilities,
            min_surplus_monthly=self.min_surplus_monthly,
        )
        family_safe_price_from_income = price_from_loan(family_safe_loan, self.deposit_pct)
        family_safe_price = min(family_safe_price_from_income, bank_price_cap)

        lines = [
            "=" * 74,
            "  NSW MORTGAGE CALCULATOR — PR/CITIZEN + FIRST HOME BUYER ASSUMPTION",
            "=" * 74,
            f"  Gross household income     : {money(gross):>14} /year",
            f"  Estimated net income       : {money(net_annual):>14} /year ({money(net_monthly)}/month)",
            f"  Actual interest rate       : {pct(self.rate)}",
            f"  Bank assessment rate       : {pct(self.rate + APRA_BUFFER_PCT)}",
            f"  Loan term                  : {LOAN_TERM_YEARS} years",
            f"  Deposit assumption         : {self.deposit_pct:.1f}%",
            f"  Area / FHG cap             : {self.area} / {self._scheme_cap_text()}",
            "",
            "  MONTHLY ASSUMPTIONS",
            f"    Living expenses          : {money(self.living_expenses_monthly):>14}",
            f"    Liabilities/commitments  : {money(liabilities):>14}",
            f"    Family-safe surplus      : {money(self.min_surplus_monthly):>14}",
            "",
            "  BANK MAX — assessed at actual rate + APRA buffer",
            f"    Max loan by income       : {money(bank_loan_cap):>14}",
            f"    Max price by income      : {money(bank_price_cap_from_income):>14}",
            f"    Max price after FHG cap  : {money(bank_price_cap):>14}",
            f"    Actual repayment         : {money(monthly_repayment(loan_from_price(bank_price_cap, self.deposit_pct), self.rate)):>14} /month",
            "",
            "  FAMILY SAFE — actual repayment + minimum monthly surplus",
            f"    Safe loan                : {money(family_safe_loan):>14}",
            f"    Safe price               : {money(family_safe_price):>14}",
            f"    Actual repayment         : {money(monthly_repayment(loan_from_price(family_safe_price, self.deposit_pct), self.rate)):>14} /month",
            f"    Weekly equivalent        : {money(monthly_repayment(loan_from_price(family_safe_price, self.deposit_pct), self.rate) * 12 / 52):>14} /week",
            "",
            self.cash_breakdown(family_safe_price, label="FAMILY SAFE PRICE"),
        ]

        if target_price is not None:
            lines.extend(self.target_report(target_price, bank_loan_cap, net_monthly, liabilities))

        lines.append(self.notes())
        return "\n".join(lines)

    def target_report(
        self,
        target_price: float,
        bank_loan_cap: float,
        net_monthly: float,
        liabilities: float,
    ) -> list[str]:
        loan = loan_from_price(target_price, self.deposit_pct)
        actual_payment = monthly_repayment(loan, self.rate)
        assessed_payment = monthly_repayment(loan, self.rate + APRA_BUFFER_PCT)
        monthly_after_target = (
            net_monthly
            - self.living_expenses_monthly
            - liabilities
            - actual_payment
        )

        required_gross = required_gross_for_loan(
            target_loan=loan,
            actual_rate_pct=self.rate,
            current_salaries=self.salaries,
            living_expenses_monthly=self.living_expenses_monthly,
            liabilities_monthly=liabilities,
            dependent_children=self.dependent_children,
            private_hospital_cover=self.private_hospital_cover,
            work_deduction=self.work_deduction,
            help_debt_rate_pct=self.help_debt_rate_pct,
        )

        can_service = loan <= bank_loan_cap
        gross_gap = max(0.0, required_gross - sum(self.salaries))

        warnings = self.target_warnings(target_price)

        lines = [
            "",
            "-" * 74,
            f"  TARGET PROPERTY: {money(target_price)}",
            "-" * 74,
            f"    Loan amount              : {money(loan):>14}",
            f"    Actual repayment         : {money(actual_payment):>14} /month",
            f"    Assessed repayment       : {money(assessed_payment):>14} /month",
            f"    Net left after target    : {money(monthly_after_target):>14} /month",
            f"    Required gross household : {money(required_gross):>14} /year",
            f"    Serviceability status    : {'LIKELY PASS model' if can_service else 'NOT PASS model'}",
            f"    Gross income gap         : {money(gross_gap):>14} /year",
            "",
            self.cash_breakdown(target_price, label="TARGET PRICE"),
        ]

        if warnings:
            lines.append("  WARNINGS")
            lines.extend(f"    - {warning}" for warning in warnings)

        return lines

    def duty_for_price(self, price: float) -> float:
        return nsw_fhbas_duty(price) if self.use_fhbas else nsw_transfer_duty(price)

    def cash_breakdown(self, price: float, label: str) -> str:
        deposit = price * (self.deposit_pct / 100)
        duty = self.duty_for_price(price)
        total_needed = deposit + duty + self.misc_buying_costs
        leftover = self.cash - total_needed
        offset_text = "surplus -> offset/buffer" if leftover >= 0 else "SHORTFALL"
        duty_label = "FHBAS duty" if self.use_fhbas else "standard duty"

        return (
            f"  CASH AT SETTLEMENT — {label} ({money(price)})\n"
            f"    Deposit                 : {money(deposit):>14}\n"
            f"    NSW {duty_label:<13}: {money(duty):>14}\n"
            f"    Buying costs buffer      : {money(self.misc_buying_costs):>14}\n"
            f"    Total cash needed        : {money(total_needed):>14}\n"
            f"    Cash available           : {money(self.cash):>14}\n"
            f"    Remaining / shortfall    : {money(leftover):>14}  -> {offset_text}\n"
        )

    def target_warnings(self, target_price: float) -> list[str]:
        warnings: list[str] = []
        if self.use_fhg and target_price > fhg_price_cap(self.area):
            warnings.append(
                f"Target price exceeds 5% Deposit Scheme cap for {self.area}: "
                f"{money(fhg_price_cap(self.area))}."
            )
        if self.use_fhbas and target_price >= FHBAS_CONCESSION_END:
            warnings.append("FHBAS concession does not apply at $1m or above; standard duty is used.")
        if self.deposit_pct <= 5 and not self.use_fhg:
            warnings.append("Deposit <=5% without FHG may trigger LMI or may not be accepted by lender.")
        if self.private_hospital_cover is False and sum(self.salaries) >= MLS_FAMILY_BASE_THRESHOLD:
            warnings.append("No private hospital cover selected; simplified Medicare Levy Surcharge may reduce net income.")
        return warnings

    def notes(self) -> str:
        return (
            "\n"
            "  NOTES\n"
            "    - Bank max is not approval. Lender policy can be stricter.\n"
            "    - FHBAS concessional duty between $800k-$1m is an estimate; verify with Revenue NSW/conveyancer.\n"
            "    - For your family decision, use FAMILY SAFE more than BANK MAX.\n"
        )

    def _scheme_cap_text(self) -> str:
        if not self.use_fhg:
            return "FHG disabled"
        return money(fhg_price_cap(self.area))

    def _validate(self) -> None:
        if not self.salaries or any(s < 0 for s in self.salaries):
            raise ValueError("--salary must contain one or more positive gross incomes")
        if self.rate < 0:
            raise ValueError("--rate cannot be negative")
        if not (0 < self.deposit_pct < 100):
            raise ValueError("--deposit-pct must be between 0 and 100")
        if self.area not in FHG_PRICE_CAPS_NSW:
            raise ValueError(f"--area must be one of: {', '.join(FHG_PRICE_CAPS_NSW)}")


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Kalkulator KPR NSW — PR/citizen + first home buyer assumption"
    )

    parser.add_argument(
        "--salary",
        nargs="+",
        type=float,
        required=True,
        metavar="GROSS",
        help="Gross annual salary per person, e.g. --salary 115000 80000",
    )
    parser.add_argument("--cash", type=float, default=0.0, help="Cash available for deposit/costs")
    parser.add_argument("--rate", type=float, default=6.25, help="Actual interest rate in percent")
    parser.add_argument("--target-price", type=float, default=None, help="Target purchase price")

    parser.add_argument(
        "--area",
        choices=sorted(FHG_PRICE_CAPS_NSW.keys()),
        default="sydney",
        help="NSW area for 5%% Deposit Scheme price cap",
    )
    parser.add_argument(
        "--deposit-pct",
        type=float,
        default=DEFAULT_DEPOSIT_PCT,
        help="Deposit percentage. Default 5 for 5%% Deposit Scheme simulation",
    )
    parser.add_argument("--no-fhg", action="store_true", help="Disable 5%% Deposit Scheme price cap")
    parser.add_argument("--no-fhbas", action="store_true", help="Disable NSW First Home Buyers Assistance Scheme")

    parser.add_argument(
        "--living-expenses",
        type=float,
        default=DEFAULT_LIVING_EXPENSES_MONTHLY,
        help="Monthly living expenses used for serviceability",
    )
    parser.add_argument(
        "--min-surplus",
        type=float,
        default=DEFAULT_MIN_SURPLUS_MONTHLY,
        help="Minimum monthly surplus after expenses and actual mortgage payment",
    )
    parser.add_argument(
        "--misc-costs",
        type=float,
        default=DEFAULT_MISC_BUYING_COSTS,
        help="Buying costs buffer: conveyancing, inspection, moving, initial repairs",
    )

    parser.add_argument("--cc-limit", type=float, default=0.0, help="Total credit card limit")
    parser.add_argument("--car-loan", type=float, default=0.0, help="Monthly car loan repayment")
    parser.add_argument("--personal-loan", type=float, default=0.0, help="Monthly personal loan repayment")
    parser.add_argument("--other-commitments", type=float, default=0.0, help="Other monthly commitments")

    parser.add_argument("--children", type=int, default=2, help="Dependent children for simplified MLS threshold")
    parser.add_argument(
        "--private-hospital-cover",
        action="store_true",
        help="Set if household has eligible private hospital cover; avoids simplified MLS",
    )
    parser.add_argument(
        "--work-deduction",
        type=float,
        default=0.0,
        help="Optional annual work deduction per person. Default 0 for conservative estimate",
    )
    parser.add_argument(
        "--help-debt-rate",
        type=float,
        default=0.0,
        help="Simplified HELP/HECS repayment as percent of gross income. Default 0",
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()

    scenario = Scenario(
        salaries=args.salary,
        cash=args.cash,
        rate=args.rate,
        area=args.area,
        deposit_pct=args.deposit_pct,
        use_fhg=not args.no_fhg,
        use_fhbas=not args.no_fhbas,
        living_expenses_monthly=args.living_expenses,
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
    )

    print(scenario.run(target_price=args.target_price))


if __name__ == "__main__":
    main()
