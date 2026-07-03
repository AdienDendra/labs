#!/usr/bin/env python3
"""
mortgage_calc.py — Kalkulator KPR Australia (NSW) untuk first home buyer.

Menghitung:
  1. Net income dari gross (tarif pajak resident FY2026-27 + Medicare levy)
  2. Borrowing capacity ala bank (assessment rate = bunga aktual + buffer APRA 3%)
  3. Cicilan bulanan/mingguan pada bunga aktual
  4. Stamp duty NSW + konsesi First Home Buyers Assistance Scheme (FHBAS)
  5. Skenario maju : gaji -> harga rumah maksimal (bank) & harga "aman" (30% gross)
  6. Skenario mundur: harga rumah target -> gaji gross yang dibutuhkan

Contoh pakai:
  python mortgage_calc.py --salary 115000 80000 --cash 130000 --rate 6.25
  python mortgage_calc.py --salary 115000 80000 --target-price 1000000
  python mortgage_calc.py --salary 115000 80000 --rate 5.75   # simulasi rate cut
  python3 mortgage_calc.py --salary 115000 80000 --cash 130000 --rate 6.25 --target-price 1000000

Catatan: angka HEM, buffer, dan bracket duty adalah aproksimasi aturan publik.
Ini alat edukasi, bukan nasihat finansial — kalkulator tiap lender berbeda.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

# ----------------------------------------------------------------------------
# KONFIGURASI — semua asumsi di satu tempat, gampang di-update
# ----------------------------------------------------------------------------

# Tarif pajak resident FY2026-27 (bracket 16% turun ke 15% per 1 Juli 2026).
# Format: (batas_atas_bracket, tarif). Bracket terakhir pakai float("inf").
TAX_BRACKETS_2026_27 = [
    (18_200, 0.00),
    (45_000, 0.15),
    (135_000, 0.30),
    (190_000, 0.37),
    (float("inf"), 0.45),
]
MEDICARE_LEVY = 0.02

# Serviceability (aturan APRA + praktik umum lender)
APRA_BUFFER = 3.0            # % di atas bunga aktual saat bank menilai kemampuan
HEM_FAMILY4_MONTHLY = 5_200  # estimasi biaya hidup keluarga 4 orang, Sydney
CREDIT_CARD_FACTOR = 0.038   # ~3.8%/bulan dari LIMIT kartu dianggap komitmen

# Pinjaman
LOAN_TERM_YEARS = 30
DEPOSIT_PCT = 0.05           # First Home Guarantee: 5% deposit, tanpa LMI
FHG_PRICE_CAP_NSW = 1_500_000

# Stamp duty NSW (transfer duty, aproksimasi bracket FY2025-26)
NSW_DUTY_BRACKETS = [
    #  (batas_atas,   duty_dasar,  tarif_marginal, mulai_dari)
    (17_000, 0, 0.0125, 0),
    (36_000, 212, 0.0150, 17_000),
    (97_000, 497, 0.0175, 36_000),
    (364_000, 1_564, 0.0350, 97_000),
    (1_212_000, 10_909, 0.0450, 364_000),
    (float("inf"), 49_069, 0.0550, 1_212_000),
]
# FHBAS: bebas duty penuh <= $800k, konsesi linear $800k-$1jt (rumah baru/bekas)
FHBAS_FULL_EXEMPT = 800_000
FHBAS_PHASE_OUT_END = 1_000_000

MISC_BUYING_COSTS = 6_000    # conveyancing, building & pest, pindahan, dll.


# ----------------------------------------------------------------------------
# FUNGSI INTI — tiap fungsi satu tanggung jawab (single responsibility)
# ----------------------------------------------------------------------------

def income_tax(gross: float) -> float:
    """Pajak penghasilan tahunan (belum termasuk Medicare levy)."""
    tax, lower = 0.0, 0.0
    for upper, rate in TAX_BRACKETS_2026_27:
        if gross > lower:
            tax += (min(gross, upper) - lower) * rate
            lower = upper
        else:
            break
    return tax


def net_annual(gross: float) -> float:
    """Gross -> net setahun, termasuk Medicare levy 2%."""
    return gross - income_tax(gross) - gross * MEDICARE_LEVY


def monthly_repayment(principal: float, annual_rate_pct: float,
                      years: int = LOAN_TERM_YEARS) -> float:
    """Cicilan bulanan — rumus anuitas standar M = P.r(1+r)^n / ((1+r)^n - 1)."""
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return principal / n
    factor = (1 + r) ** n
    return principal * r * factor / (factor - 1)


def max_loan(net_monthly: float, actual_rate_pct: float,
             hem: float = HEM_FAMILY4_MONTHLY,
             credit_card_limit: float = 0,
             years: int = LOAN_TERM_YEARS) -> float:
    """
    Borrowing capacity: berapa pinjaman maksimal yang 'lolos komputer bank'.
    Bank menilai di assessment rate (aktual + buffer 3%), lalu mencari P
    sedemikian sehingga cicilan_assessed = sisa income setelah biaya hidup.
    Ini kebalikan (inverse) dari rumus anuitas.
    """
    assessed_rate = actual_rate_pct + APRA_BUFFER
    surplus = net_monthly - hem - credit_card_limit * CREDIT_CARD_FACTOR
    if surplus <= 0:
        return 0.0
    r = assessed_rate / 100 / 12
    n = years * 12
    factor = (1 + r) ** n
    return surplus * (factor - 1) / (r * factor)


def nsw_stamp_duty(price: float) -> float:
    """Transfer duty NSW standar (tanpa konsesi)."""
    for upper, base, rate, start in NSW_DUTY_BRACKETS:
        if price <= upper:
            return base + (price - start) * rate
    return 0.0  # tak terjangkau


def nsw_duty_first_home(price: float) -> float:
    """Duty setelah konsesi FHBAS: gratis <=$800k, linear sampai $1jt."""
    full = nsw_stamp_duty(price)
    if price <= FHBAS_FULL_EXEMPT:
        return 0.0
    if price >= FHBAS_PHASE_OUT_END:
        return full
    span = FHBAS_PHASE_OUT_END - FHBAS_FULL_EXEMPT
    return full * (price - FHBAS_FULL_EXEMPT) / span


def required_gross_for_loan(loan: float, actual_rate_pct: float,
                            hem: float = HEM_FAMILY4_MONTHLY,
                            split: tuple[float, float] = (115_000, 80_000)
                            ) -> float:
    """
    Hitung mundur: pinjaman target -> gross rumah tangga yang dibutuhkan.
    Gross tidak bisa dihitung langsung (pajak progresif = fungsi non-linear),
    jadi dipecahkan numerik dengan binary search — teknik yang sama seperti
    mencari nilai di sorted array, hanya targetnya 'net income yang cukup'.
    `split` = proporsi gaji berdua, agar pajak dihitung per orang (lebih akurat
    daripada mengasumsikan satu penghasilan besar, karena bracket progresif).
    """
    assessed_pmt = monthly_repayment(loan, actual_rate_pct + APRA_BUFFER)
    need_net_monthly = assessed_pmt + hem
    ratio = split[0] / (split[0] + split[1])

    lo, hi = 50_000.0, 1_000_000.0
    for _ in range(60):  # 60 iterasi ~ presisi < $1
        mid = (lo + hi) / 2
        net = net_annual(mid * ratio) + net_annual(mid * (1 - ratio))
        if net / 12 < need_net_monthly:
            lo = mid
        else:
            hi = mid
    return hi


# ----------------------------------------------------------------------------
# LAPORAN SKENARIO
# ----------------------------------------------------------------------------

@dataclass
class Scenario:
    salaries: list[float]
    cash: float
    rate: float
    credit_card_limit: float = 0.0

    def run(self, target_price: float | None = None) -> str:
        nets = [net_annual(s) for s in self.salaries]
        net_month = sum(nets) / 12
        gross = sum(self.salaries)

        loan_cap = max_loan(net_month, self.rate,
                            credit_card_limit=self.credit_card_limit)
        price_cap = min(loan_cap / (1 - DEPOSIT_PCT), FHG_PRICE_CAP_NSW)

        # Definisi "aman": cicilan aktual <= 30% gross bulanan
        safe_pmt = gross / 12 * 0.30
        r = self.rate / 100 / 12
        n = LOAN_TERM_YEARS * 12
        factor = (1 + r) ** n
        safe_loan = safe_pmt * (factor - 1) / (r * factor)
        safe_price = min(safe_loan / (1 - DEPOSIT_PCT), price_cap)

        lines = [
            "=" * 62,
            f"  Gaji gross gabungan : ${gross:>12,.0f} /tahun",
            f"  Net income          : ${sum(nets):>12,.0f} /tahun "
            f"(${net_month:,.0f}/bulan)",
            f"  Bunga aktual        : {self.rate:.2f}%   "
            f"(dinilai bank di {self.rate + APRA_BUFFER:.2f}%)",
            "=" * 62,
            "",
            f"  KAPASITAS MAKSIMAL BANK",
            f"    Pinjaman maksimal : ${loan_cap:>12,.0f}",
            f"    Harga rumah maks  : ${price_cap:>12,.0f}  (deposit 5%)",
            f"    Cicilan aktual    : ${monthly_repayment(price_cap * 0.95, self.rate):>12,.0f} /bulan",
            "",
            f"  ZONA AMAN (cicilan <= 30% gross)",
            f"    Harga rumah aman  : ${safe_price:>12,.0f}",
            f"    Cicilan           : ${monthly_repayment(safe_price * 0.95, self.rate):>12,.0f} /bulan "
            f"(${monthly_repayment(safe_price * 0.95, self.rate) * 12 / 52:,.0f}/minggu)",
            "",
            self._cash_breakdown(safe_price),
        ]

        if target_price:
            loan = target_price * (1 - DEPOSIT_PCT)
            need_gross = required_gross_for_loan(
                loan, self.rate,
                split=(self.salaries[0], self.salaries[-1] or 1))
            pmt = monthly_repayment(loan, self.rate)
            verdict = ("LOLOS serviceability" if loan <= loan_cap
                       else f"BELUM lolos — kurang ${need_gross - gross:,.0f} gross/tahun")
            lines += [
                f"  TARGET: RUMAH ${target_price:,.0f}",
                f"    Pinjaman          : ${loan:>12,.0f}",
                f"    Cicilan aktual    : ${pmt:>12,.0f} /bulan",
                f"    Butuh gross       : ${need_gross:>12,.0f} /tahun gabungan",
                f"    Status sekarang   : {verdict}",
                "",
                self._cash_breakdown(target_price),
            ]
        return "\n".join(lines)

    def _cash_breakdown(self, price: float) -> str:
        deposit = price * DEPOSIT_PCT
        duty = nsw_duty_first_home(price)
        total = deposit + duty + MISC_BUYING_COSTS
        leftover = self.cash - total
        return (
            f"  CASH DI SETTLEMENT (harga ${price:,.0f})\n"
            f"    Deposit 5%        : ${deposit:>12,.0f}\n"
            f"    Stamp duty (FHBAS): ${duty:>12,.0f}\n"
            f"    Biaya lain-lain   : ${MISC_BUYING_COSTS:>12,.0f}\n"
            f"    Total dibutuhkan  : ${total:>12,.0f}\n"
            f"    Sisa dari ${self.cash:,.0f}: ${leftover:>12,.0f}"
            f"  -> {'masuk offset account' if leftover > 0 else 'KURANG!'}\n"
        )


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(
        description="Kalkulator KPR NSW — first home buyer (FHG 5% deposit)")
    p.add_argument("--salary", nargs="+", type=float, required=True,
                   metavar="GROSS", help="gaji gross per orang, mis: 115000 80000")
    p.add_argument("--cash", type=float, default=0, help="cash tersedia")
    p.add_argument("--rate", type=float, default=6.25,
                   help="bunga aktual %% (default 6.25)")
    p.add_argument("--target-price", type=float, default=None,
                   help="harga rumah target untuk hitung-mundur gaji")
    p.add_argument("--cc-limit", type=float, default=0,
                   help="total LIMIT kartu kredit (memotong kapasitas!)")
    args = p.parse_args()

    scenario = Scenario(salaries=args.salary, cash=args.cash,
                        rate=args.rate, credit_card_limit=args.cc_limit)
    print(scenario.run(target_price=args.target_price))


if __name__ == "__main__":
    main()