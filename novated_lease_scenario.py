#!/usr/bin/env python3
"""
novated_lease_scenario.py
=========================

Estimator pribadi untuk membandingkan novated lease kendaraan di Australia,
dengan contoh utama Tesla Model Y RWD via Maxxia.

Tujuan script
-------------
Script ini dibuat untuk membantu membaca quote novated lease secara realistis,
bukan hanya melihat angka marketing seperti "monthly cost" atau "tax saving".

Script menghitung:
1. Net salary Adien sebelum dan sesudah novated lease.
2. Net salary Sekar jika mulai bekerja pada tahun tertentu.
3. Estimasi FTB Part A dan FTB Part B.
4. Adjusted Taxable Income (ATI), termasuk RFBA untuk kendaraan FBT-exempt.
5. Household cashflow per bulan.
6. Residual / balloon akhir lease.
7. Tabungan bulanan yang harus disisihkan agar balloon siap dibayar.
8. Perbandingan 2 / 3 / 5 tahun, atau kendaraan lain seperti CR-V Hybrid.

Dua mode penggunaan
-------------------
MODE A — Quote Mode, paling akurat:
    Masukkan angka dari Maxxia / provider:
    - annual_package_pretax
    - annual_admin_fee
    - annual_input_tax_credit
    - annual_post_tax_ecm, jika ada
    - residual_override, jika provider memberi residual resmi

MODE B — Estimate Mode, kasar:
    Jika belum ada quote formal, script bisa membuat estimasi annual package
    dari harga mobil, running cost, term, interest rate, dan residual.
    Ini hanya untuk screening awal, bukan keputusan final.

Catatan penting untuk EV vs Hybrid/Bensin
-----------------------------------------
Tesla Model Y battery-electric vehicle (BEV) biasanya FBT-exempt jika memenuhi
syarat harga dan first-held/use rules. Karena itu FBT = 0, ECM = 0, tetapi tetap
ada RFBA yang bisa memengaruhi FTB, CCS, Medicare Levy Surcharge, dll.

Honda CR-V Hybrid biasa bukan BEV dan bukan plug-in hybrid yang eligible.
Jadi novated lease-nya biasanya punya FBT/ECM treatment yang berbeda.
Untuk kendaraan non-EV, JANGAN percaya estimasi RFBA otomatis di script ini.
Masukkan quote resmi dari provider, terutama:
    - FBT
    - ECM post-tax contribution
    - RFBA / reportable fringe benefit
    - residual
    - effective interest rate

Disclaimer
----------
Ini estimator pribadi, bukan financial advice, tax advice, atau Services Australia
determination. Validasi dengan:
- formal quote Maxxia / provider
- accountant / tax agent
- Services Australia
- lender jika akan apply mortgage

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Literal


# =============================================================================
# 1. GLOBAL SCENARIO SETTINGS — paling sering diubah
# =============================================================================

BASE_USER_SALARY = 111_000
USER_SALARY_GROWTH_PER_YEAR = 0.03

# Partner income per lease year.
# Contoh: Sekar belum kerja di tahun 1, lalu kerja $80k dari tahun 2.
PARTNER_INCOME_BY_YEAR = {
    1: 0,
    2: 80_000,
    3: 80_000,
    4: 80_000,
    5: 80_000,
}

# Cash yang sudah disiapkan khusus untuk residual/balloon.
INITIAL_RESIDUAL_FUND = 10_000

# FTB eligibility toggles.
# Untuk kondisi PR / newly arrived resident, FTB A bisa perlu dicek lagi.
FTB_A_ELIGIBLE = True
FTB_B_ELIGIBLE = True

KIDS_UNDER_13 = 2
YOUNGEST_UNDER_5 = True

# Pilih tax year yang mau dipakai.
# Screenshot Maxxia kamu lebih dekat ke FY2025-26.
TAX_YEAR = "2025-26"


# =============================================================================
# 2. TAX, FTB, FBT, GST PARAMETERS — update jika aturan berubah
# =============================================================================

TAX_BRACKETS_BY_YEAR = {
    "2025-26": [
        (18_200, 0.00),
        (45_000, 0.16),
        (135_000, 0.30),
        (190_000, 0.37),
        (float("inf"), 0.45),
    ],
    "2026-27": [
        (18_200, 0.00),
        (45_000, 0.15),
        (135_000, 0.30),
        (190_000, 0.37),
        (float("inf"), 0.45),
    ],
}

MEDICARE_LEVY = 0.02
GST_RATE = 0.10

# Lower gross-up rate for reportable fringe benefits.
RFBA_GROSSUP = 1.8868

# Statutory formula rate for car fringe benefit.
FBT_STATUTORY_RATE = 0.20

# ATO minimum residual percentages for car leases.
# 1 year = 65.63%, 2 years = 56.25%, 3 years = 46.88%, 4 years = 37.50%, 5 years = 28.13%
ATO_RESIDUAL_PERCENT = {
    1: 0.6563,
    2: 0.5625,
    3: 0.4688,
    4: 0.3750,
    5: 0.2813,
}

FTB_PARAMS = {
    # FTB Part A
    "A_max_rate_u13_ftn": 235.48,
    "A_base_rate_ftn": 75.60,
    "A_income_free_area": 69_131,
    "A_higher_free_area": 123_078,

    # FTB Part B
    "B_max_rate_ftn_u5": 200.34,
    "B_max_rate_ftn_5_to_18": 139.86,
    "B_primary_limit": 124_327,
    "B_secondary_free_area": 7_154,
}


# =============================================================================
# 3. VEHICLE + QUOTE MODELS
# =============================================================================

VehicleCategory = Literal["bev", "phev", "hybrid", "petrol", "diesel"]


@dataclass(frozen=True)
class Vehicle:
    """
    Data kendaraan.

    price:
        Harga kendaraan yang dipakai untuk residual estimate.
        Untuk Tesla screenshot kamu: $61,551.

    fbt_base_value:
        Basis untuk RFBA. Kalau None, script pakai price.
        Formal quote provider bisa memakai basis sedikit berbeda.

    category:
        - "bev"     : battery EV, contoh Tesla Model Y
        - "phev"    : plug-in hybrid
        - "hybrid"  : hybrid biasa, contoh CR-V e:HEV
        - "petrol"  : bensin
        - "diesel"  : diesel

    fbt_exempt:
        True untuk eligible BEV.
        False untuk hybrid/bensin biasa.
    """
    name: str
    price: float
    category: VehicleCategory = "bev"
    fbt_exempt: bool = True
    fbt_base_value: Optional[float] = None
    default_running_costs_year: float = 5_000

    def rfba_base(self) -> float:
        return self.fbt_base_value if self.fbt_base_value is not None else self.price


@dataclass(frozen=True)
class LeaseQuote:
    """
    Quote novated lease.

    annual_package_pretax:
        Baris "Motor Vehicle Under a Novated Lease" di Maxxia comparison.
        Ini biasanya berisi lease payment + running cost budget.

    annual_admin_fee:
        Baris administration fee.

    annual_input_tax_credit:
        Selisih GST/input-tax-credit dari quote.
        Dari screenshot Tesla 2Y:
            90,485 - (111,500 - 22,817 - 200) = 2,002

    annual_post_tax_ecm:
        Employee Contribution Method / post-tax contribution.
        Untuk Tesla EV screenshot kamu = 0.
        Untuk hybrid/bensin sering tidak nol. Masukkan dari quote.

    annual_rfba_override:
        Jika provider memberi RFBA/reportable amount resmi, masukkan di sini.
        Untuk Tesla EV, script bisa estimate sendiri.
        Untuk non-EV, lebih aman pakai angka resmi provider.

    residual_override:
        Jika provider memberi residual/balloon resmi, masukkan di sini.
        Jika None, script estimate pakai ATO minimum residual percentage.

    quote_mode:
        "formal" jika dari Maxxia/provider.
        "estimated" jika dihitung kasar oleh script.
    """
    vehicle: Vehicle
    term_years: int
    annual_package_pretax: float
    annual_admin_fee: float = 200
    annual_input_tax_credit: float = 0
    annual_post_tax_ecm: float = 0
    annual_rfba_override: Optional[float] = None
    residual_override: Optional[float] = None
    quote_mode: Literal["formal", "estimated"] = "formal"
    label: str = ""

    def display_name(self) -> str:
        base = self.label or f"{self.vehicle.name} {self.term_years} tahun"
        return f"{base} ({self.quote_mode})"


@dataclass(frozen=True)
class EstimateAssumptions:
    """
    Asumsi untuk membuat rough quote jika belum ada quote Maxxia.

    Gunakan ini hanya untuk screening awal.
    Untuk keputusan final, pakai quote formal.
    """
    annual_interest_rate: float = 0.10
    annual_running_costs: Optional[float] = None
    annual_admin_fee: float = 200
    gst_credit_on_vehicle: bool = True
    gst_credit_cap: float = 6_334


# =============================================================================
# 4. VEHICLE CATALOG — harga fleksibel
# =============================================================================

TESLA_MODEL_Y_RWD = Vehicle(
    name="2026 Tesla Model Y RWD",
    price=61_551,
    category="bev",
    fbt_exempt=True,
    fbt_base_value=61_551,
    default_running_costs_year=5_000,
)

# Contoh placeholder: ubah harga jika kamu ingin simulasi CR-V Hybrid.
# Catatan: CR-V hybrid biasa bukan BEV, jadi fbt_exempt=False.
HONDA_CRV_HYBRID_EXAMPLE = Vehicle(
    name="Honda CR-V Hybrid example",
    price=58_000,                    # ubah sesuai drive-away quote
    category="hybrid",
    fbt_exempt=False,
    fbt_base_value=58_000,
    default_running_costs_year=6_500,  # bensin/servis/rego/insurance kira-kira lebih tinggi
)

CUSTOM_VEHICLE = Vehicle(
    name="Custom vehicle",
    price=61_551,
    category="bev",
    fbt_exempt=True,
    fbt_base_value=61_551,
    default_running_costs_year=5_000,
)


# =============================================================================
# 5. QUOTES — masukkan angka Maxxia/provider di sini
# =============================================================================

# Tesla quote 2 tahun dari screenshot:
# - Annual package: $22,817
# - Admin fee: $200
# - Input tax credit derived: $2,002
TESLA_2Y_MAXXIA = LeaseQuote(
    vehicle=TESLA_MODEL_Y_RWD,
    term_years=2,
    annual_package_pretax=22_817,
    annual_admin_fee=200,
    annual_input_tax_credit=2_002,
    annual_post_tax_ecm=0,
    label="Tesla Maxxia 2 tahun",
)

# Tesla quote 3 tahun dari screenshot:
# - Annual package: $19,851
# - Admin fee: $200
# - Input tax credit derived: $1,732
TESLA_3Y_MAXXIA = LeaseQuote(
    vehicle=TESLA_MODEL_Y_RWD,
    term_years=3,
    annual_package_pretax=19_851,
    annual_admin_fee=200,
    annual_input_tax_credit=1_732,
    annual_post_tax_ecm=0,
    label="Tesla Maxxia 3 tahun",
)

# Placeholder CR-V Hybrid.
# Jangan pakai untuk keputusan final sebelum punya quote formal.
# Jika kamu dapat quote Maxxia untuk CR-V, isi:
# - annual_package_pretax
# - annual_input_tax_credit
# - annual_post_tax_ecm
# - annual_rfba_override jika ada
# - residual_override jika ada
CRV_HYBRID_PLACEHOLDER = LeaseQuote(
    vehicle=HONDA_CRV_HYBRID_EXAMPLE,
    term_years=3,
    annual_package_pretax=21_000,
    annual_admin_fee=200,
    annual_input_tax_credit=1_200,
    annual_post_tax_ecm=0,          # kemungkinan besar perlu diubah dari quote
    annual_rfba_override=None,      # isi dari quote jika ada
    quote_mode="estimated",
    label="CR-V Hybrid placeholder 3 tahun",
)

# Pilih quotes yang mau dibandingkan.
QUOTES_TO_COMPARE = [
    TESLA_2Y_MAXXIA,
    TESLA_3Y_MAXXIA,
    # CRV_HYBRID_PLACEHOLDER,  # aktifkan jika mau lihat rough comparison
]


# =============================================================================
# 6. CORE FINANCIAL FUNCTIONS
# =============================================================================

def income_tax(taxable_income: float, tax_year: str = TAX_YEAR) -> float:
    """Australian resident income tax + Medicare levy."""
    if taxable_income <= 0:
        return 0.0

    brackets = TAX_BRACKETS_BY_YEAR[tax_year]
    tax = 0.0
    previous_ceiling = 0.0

    for ceiling, rate in brackets:
        if taxable_income <= previous_ceiling:
            break

        taxable_slice = min(taxable_income, ceiling) - previous_ceiling
        tax += taxable_slice * rate
        previous_ceiling = ceiling

    tax += taxable_income * MEDICARE_LEVY
    return max(0.0, tax)


def net_income(gross_income: float, tax_year: str = TAX_YEAR) -> float:
    return gross_income - income_tax(gross_income, tax_year)


def annuity_payment(
    principal: float,
    annual_rate: float,
    months: int,
    balloon: float = 0.0,
) -> float:
    """
    Monthly payment for loan/lease with optional balloon.

    principal = amount financed
    balloon   = residual at end of term
    """
    monthly_rate = annual_rate / 12
    if months <= 0:
        raise ValueError("months must be positive")

    if monthly_rate == 0:
        return (principal - balloon) / months

    pv_balloon = balloon / ((1 + monthly_rate) ** months)
    return (principal - pv_balloon) * monthly_rate / (1 - (1 + monthly_rate) ** -months)


def user_salary_for_year(year: int) -> float:
    return BASE_USER_SALARY * ((1 + USER_SALARY_GROWTH_PER_YEAR) ** (year - 1))


def partner_income_for_year(year: int) -> float:
    return PARTNER_INCOME_BY_YEAR.get(year, 0.0)


def estimate_residual(quote: LeaseQuote) -> float:
    if quote.residual_override is not None:
        return quote.residual_override

    residual_pct = ATO_RESIDUAL_PERCENT[quote.term_years]
    return quote.vehicle.price * residual_pct


def estimate_rfba(quote: LeaseQuote) -> tuple[float, list[str]]:
    """
    Estimate RFBA used for income tests.

    For eligible EV:
        RFBA approx = fbt_base_value * 20% * 1.8868

    For non-EV:
        The correct RFBA depends on FBT/ECM treatment.
        Use annual_rfba_override from formal quote when available.
    """
    warnings: list[str] = []

    if quote.annual_rfba_override is not None:
        return quote.annual_rfba_override, warnings

    if quote.vehicle.fbt_exempt:
        return quote.vehicle.rfba_base() * FBT_STATUTORY_RATE * RFBA_GROSSUP, warnings

    warnings.append(
        "Non-EV / non-FBT-exempt vehicle: RFBA is not auto-modelled. "
        "Use formal quote and set annual_rfba_override."
    )
    return 0.0, warnings


def estimate_quote_from_vehicle(
    vehicle: Vehicle,
    term_years: int,
    assumptions: EstimateAssumptions,
    label: str = "",
) -> LeaseQuote:
    """
    Rough-estimate a lease quote when no formal quote is available.

    This is intentionally conservative and simplified.
    It does NOT replace a Maxxia quote.
    """
    residual = vehicle.price * ATO_RESIDUAL_PERCENT[term_years]

    # Simple GST credit estimate on vehicle purchase.
    gst_credit = 0.0
    if assumptions.gst_credit_on_vehicle:
        gst_credit = min(vehicle.price / 11, assumptions.gst_credit_cap)

    amount_financed = vehicle.price - gst_credit
    residual_ex_gst_style = residual / (1 + GST_RATE)

    monthly_finance = annuity_payment(
        principal=amount_financed,
        annual_rate=assumptions.annual_interest_rate,
        months=term_years * 12,
        balloon=residual_ex_gst_style,
    )

    running = (
        assumptions.annual_running_costs
        if assumptions.annual_running_costs is not None
        else vehicle.default_running_costs_year
    )

    # Approx running costs ex-GST if packaged.
    annual_running_pretax = running / (1 + GST_RATE)

    # Approx GST/input credit. Formal quotes may differ materially.
    annual_input_tax_credit = running - annual_running_pretax

    annual_package = monthly_finance * 12 + annual_running_pretax

    return LeaseQuote(
        vehicle=vehicle,
        term_years=term_years,
        annual_package_pretax=annual_package,
        annual_admin_fee=assumptions.annual_admin_fee,
        annual_input_tax_credit=annual_input_tax_credit,
        annual_post_tax_ecm=0.0,
        residual_override=residual,
        quote_mode="estimated",
        label=label or f"{vehicle.name} estimate {term_years} tahun",
    )


def ftb_estimate(
    family_ati: float,
    primary_ati: float,
    secondary_ati: float,
    kids_under_13: int = KIDS_UNDER_13,
    youngest_under_5: bool = YOUNGEST_UNDER_5,
) -> tuple[float, float, list[str]]:
    """
    Estimate annual FTB A and FTB B.

    This intentionally simplifies edge cases such as shared care, supplements,
    maintenance income, residency waiting periods, and balancing outcomes.
    """
    p = FTB_PARAMS
    warnings: list[str] = []

    # FTB Part A
    if not FTB_A_ELIGIBLE:
        ftb_a = 0.0
        warnings.append("FTB A disabled / not eligible in this scenario.")
    else:
        max_rate = kids_under_13 * p["A_max_rate_u13_ftn"] * 26
        base_rate = kids_under_13 * p["A_base_rate_ftn"] * 26

        method_1 = max(
            0.0,
            max_rate - 0.20 * max(0.0, family_ati - p["A_income_free_area"]),
        )

        method_2 = max(
            0.0,
            base_rate - 0.30 * max(0.0, family_ati - p["A_higher_free_area"]),
        )

        ftb_a = max(method_1, method_2)

        if family_ati > p["A_higher_free_area"]:
            warnings.append(
                f"FTB A higher income test applies: family ATI ${family_ati:,.0f} "
                f"> ${p['A_higher_free_area']:,.0f}."
            )

    # FTB Part B
    if not FTB_B_ELIGIBLE:
        ftb_b = 0.0
        warnings.append("FTB B disabled / not eligible in this scenario.")
    elif primary_ati > p["B_primary_limit"]:
        ftb_b = 0.0
        warnings.append(
            f"FTB B lost: primary ATI ${primary_ati:,.0f} "
            f"> cliff ${p['B_primary_limit']:,.0f}."
        )
    else:
        max_b = (
            p["B_max_rate_ftn_u5"]
            if youngest_under_5
            else p["B_max_rate_ftn_5_to_18"]
        ) * 26

        ftb_b = max(
            0.0,
            max_b - 0.20 * max(0.0, secondary_ati - p["B_secondary_free_area"]),
        )

        if secondary_ati > p["B_secondary_free_area"]:
            warnings.append(
                f"FTB B reduced by secondary income: secondary ATI ${secondary_ati:,.0f} "
                f"> free area ${p['B_secondary_free_area']:,.0f}."
            )

        margin = p["B_primary_limit"] - primary_ati
        if 0 < margin < 10_000:
            warnings.append(
                f"FTB B primary-earner cliff is close: margin only ${margin:,.0f}."
            )

    return ftb_a, ftb_b, warnings


@dataclass(frozen=True)
class YearResult:
    year: int
    user_salary: float
    partner_gross: float
    partner_net: float

    baseline_user_net: float
    baseline_ftb_a: float
    baseline_ftb_b: float
    baseline_household_cash: float

    taxable_after_lease: float
    user_net_with_lease: float
    post_tax_ecm: float
    rfba: float
    primary_ati: float
    secondary_ati: float
    family_ati: float

    lease_ftb_a: float
    lease_ftb_b: float
    household_cash_with_lease: float

    monthly_cash_impact_vs_baseline: float
    warnings: list[str]


def analyse_year(quote: LeaseQuote, year: int) -> YearResult:
    user_salary = user_salary_for_year(year)
    partner_gross = partner_income_for_year(year)
    partner_net = net_income(partner_gross)

    # Baseline: no novated lease
    baseline_user_net = net_income(user_salary)
    baseline_ftb_a, baseline_ftb_b, baseline_warnings = ftb_estimate(
        family_ati=user_salary + partner_gross,
        primary_ati=user_salary,
        secondary_ati=partner_gross,
    )
    baseline_household = baseline_user_net + partner_net + baseline_ftb_a + baseline_ftb_b

    # With lease: matches Maxxia comparison table
    taxable_after_lease = (
        user_salary
        - quote.annual_package_pretax
        - quote.annual_admin_fee
        + quote.annual_input_tax_credit
    )

    user_net_with_lease_before_ecm = taxable_after_lease - income_tax(taxable_after_lease)
    user_net_with_lease = user_net_with_lease_before_ecm - quote.annual_post_tax_ecm

    rfba, rfba_warnings = estimate_rfba(quote)
    primary_ati = taxable_after_lease + rfba
    secondary_ati = partner_gross
    family_ati = primary_ati + secondary_ati

    lease_ftb_a, lease_ftb_b, lease_warnings = ftb_estimate(
        family_ati=family_ati,
        primary_ati=primary_ati,
        secondary_ati=secondary_ati,
    )

    household_with_lease = user_net_with_lease + partner_net + lease_ftb_a + lease_ftb_b
    monthly_impact = (baseline_household - household_with_lease) / 12

    warnings = baseline_warnings + rfba_warnings + lease_warnings

    return YearResult(
        year=year,
        user_salary=user_salary,
        partner_gross=partner_gross,
        partner_net=partner_net,
        baseline_user_net=baseline_user_net,
        baseline_ftb_a=baseline_ftb_a,
        baseline_ftb_b=baseline_ftb_b,
        baseline_household_cash=baseline_household,
        taxable_after_lease=taxable_after_lease,
        user_net_with_lease=user_net_with_lease,
        post_tax_ecm=quote.annual_post_tax_ecm,
        rfba=rfba,
        primary_ati=primary_ati,
        secondary_ati=secondary_ati,
        family_ati=family_ati,
        lease_ftb_a=lease_ftb_a,
        lease_ftb_b=lease_ftb_b,
        household_cash_with_lease=household_with_lease,
        monthly_cash_impact_vs_baseline=monthly_impact,
        warnings=warnings,
    )


# =============================================================================
# 7. REPORTING
# =============================================================================

def money(x: float) -> str:
    return f"${x:,.0f}"


def report_quote(quote: LeaseQuote) -> dict:
    residual = estimate_residual(quote)
    months = quote.term_years * 12
    remaining_residual_to_save = max(0.0, residual - INITIAL_RESIDUAL_FUND)
    monthly_balloon_saving = remaining_residual_to_save / months

    print("=" * 100)
    print(f"{quote.display_name().upper()}")
    print("=" * 100)
    print(f"Vehicle                    : {quote.vehicle.name}")
    print(f"Vehicle category           : {quote.vehicle.category}")
    print(f"FBT exempt                 : {quote.vehicle.fbt_exempt}")
    print(f"Vehicle price              : {money(quote.vehicle.price)}")
    print(f"Lease term                 : {quote.term_years} tahun")
    print(f"Annual package pre-tax     : {money(quote.annual_package_pretax)}")
    print(f"Annual admin fee           : {money(quote.annual_admin_fee)}")
    print(f"Annual input tax credit    : {money(quote.annual_input_tax_credit)}")
    print(f"Annual post-tax ECM        : {money(quote.annual_post_tax_ecm)}")
    print(f"Estimated residual/balloon : {money(residual)}")
    print(f"Initial residual fund      : {money(INITIAL_RESIDUAL_FUND)}")
    print(f"Need to save for balloon   : {money(remaining_residual_to_save)}")
    print(f"Monthly balloon saving     : {money(monthly_balloon_saving)}/month")
    print("-" * 100)

    total_household_cash = 0.0
    total_household_after_saving = 0.0
    total_cash_impact = 0.0

    for year in range(1, quote.term_years + 1):
        r = analyse_year(quote, year)

        household_month = r.household_cash_with_lease / 12
        household_after_saving_month = household_month - monthly_balloon_saving

        total_household_cash += r.household_cash_with_lease
        total_household_after_saving += (
            r.household_cash_with_lease - monthly_balloon_saving * 12
        )
        total_cash_impact += r.monthly_cash_impact_vs_baseline * 12

        print(f"\nYEAR {year}")
        print(f"  Adien gross salary             : {money(r.user_salary)}")
        print(f"  Sekar gross income             : {money(r.partner_gross)}")
        print(f"  Adien net with lease           : {money(r.user_net_with_lease)}/yr "
              f"({money(r.user_net_with_lease / 12)}/mo)")
        print(f"  Sekar net income               : {money(r.partner_net)}/yr "
              f"({money(r.partner_net / 12)}/mo)")
        print(f"  FTB A with lease               : {money(r.lease_ftb_a)}/yr "
              f"({money(r.lease_ftb_a / 12)}/mo)")
        print(f"  FTB B with lease               : {money(r.lease_ftb_b)}/yr "
              f"({money(r.lease_ftb_b / 12)}/mo)")
        print(f"  Taxable after lease            : {money(r.taxable_after_lease)}")
        print(f"  RFBA estimate                  : {money(r.rfba)}")
        print(f"  Primary ATI                    : {money(r.primary_ati)}")
        print(f"  Family ATI                     : {money(r.family_ati)}")
        print(f"  Household cash with lease      : {money(household_month)}/mo")
        print(f"  Cash impact vs no lease        : {money(r.monthly_cash_impact_vs_baseline)}/mo")
        print(f"  After balloon saving           : {money(household_after_saving_month)}/mo")

        if r.warnings:
            for warning in sorted(set(r.warnings)):
                print(f"  [!] {warning}")

    average_cash = total_household_cash / months
    average_after_saving = total_household_after_saving / months
    average_impact = total_cash_impact / months

    print("\n" + "-" * 100)
    print(f"Average household cash with lease : {money(average_cash)}/month")
    print(f"Average cash impact vs no lease   : {money(average_impact)}/month")
    print(f"Average after balloon saving      : {money(average_after_saving)}/month")
    print("=" * 100)

    return {
        "name": quote.display_name(),
        "term_years": quote.term_years,
        "vehicle": quote.vehicle.name,
        "average_household_cash": average_cash,
        "average_cash_impact": average_impact,
        "average_after_balloon_saving": average_after_saving,
        "residual": residual,
        "monthly_balloon_saving": monthly_balloon_saving,
    }


def report_summary(rows: list[dict]) -> None:
    print("\n\nSUMMARY")
    print("=" * 100)
    print(
        f"{'Scenario':38} {'Term':>5} {'Residual':>12} "
        f"{'Save/mo':>10} {'Avg cash/mo':>13} {'After balloon/mo':>18}"
    )
    print("-" * 100)

    for row in rows:
        print(
            f"{row['name'][:38]:38} "
            f"{row['term_years']:>5} "
            f"{money(row['residual']):>12} "
            f"{money(row['monthly_balloon_saving']):>10} "
            f"{money(row['average_household_cash']):>13} "
            f"{money(row['average_after_balloon_saving']):>18}"
        )

    print("=" * 100)


def main() -> None:
    print("\nNOVATED LEASE SCENARIO CALCULATOR")
    print("=" * 100)
    print(f"Tax year used             : {TAX_YEAR}")
    print(f"Base Adien salary         : {money(BASE_USER_SALARY)}")
    print(f"Salary growth per year    : {USER_SALARY_GROWTH_PER_YEAR:.1%}")
    print(f"Partner income by year    : {PARTNER_INCOME_BY_YEAR}")
    print(f"FTB A eligible            : {FTB_A_ELIGIBLE}")
    print(f"FTB B eligible            : {FTB_B_ELIGIBLE}")
    print(f"Initial residual fund     : {money(INITIAL_RESIDUAL_FUND)}")
    print("=" * 100)

    rows = []
    for quote in QUOTES_TO_COMPARE:
        rows.append(report_quote(quote))

    report_summary(rows)

    print("\nHOW TO USE THIS SCRIPT")
    print("-" * 100)
    print("1. To change vehicle price, edit Vehicle(price=...).")
    print("2. To use Tesla, edit TESLA_MODEL_Y_RWD.")
    print("3. To test CR-V Hybrid, edit HONDA_CRV_HYBRID_EXAMPLE and enable CRV_HYBRID_PLACEHOLDER.")
    print("4. For a formal Maxxia quote, create a LeaseQuote with actual annual_package_pretax,")
    print("   annual_input_tax_credit, annual_post_tax_ecm, residual_override, and RFBA if provided.")
    print("5. For non-EV/hybrid cars, do not rely on automatic RFBA. Use formal quote values.")
    print("-" * 100)


if __name__ == "__main__":
    main()
