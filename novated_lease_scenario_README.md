# Novated Lease Scenario Calculator

Estimator pribadi untuk membaca novated lease secara lebih realistis, terutama untuk skenario Tesla Model Y RWD via Maxxia, tetapi struktur script sudah dibuat fleksibel untuk kendaraan lain seperti Honda CR-V Hybrid.

## Apa yang dihitung

Script menghitung:

1. Net salary Adien sebelum dan sesudah novated lease.
2. Net salary Sekar jika mulai bekerja pada tahun tertentu.
3. Estimasi FTB Part A dan FTB Part B.
4. Adjusted Taxable Income (ATI), termasuk RFBA.
5. Household cashflow per bulan.
6. Residual atau balloon akhir lease.
7. Tabungan bulanan yang perlu disisihkan agar balloon siap dibayar.
8. Perbandingan lease 2 tahun, 3 tahun, 5 tahun, atau kendaraan lain.

## Cara menjalankan

```bash
python3 novated_lease_scenario.py
```

## Bagian yang paling sering diubah

### 1. Gaji Adien

```python
BASE_USER_SALARY = 111_000
USER_SALARY_GROWTH_PER_YEAR = 0.03
```

Artinya:
- Tahun 1: $111,000
- Tahun 2: $114,330
- Tahun 3: $117,760 kira-kira

### 2. Income Sekar

```python
PARTNER_INCOME_BY_YEAR = {
    1: 0,
    2: 80_000,
    3: 80_000,
    4: 80_000,
    5: 80_000,
}
```

Artinya:
- Tahun 1 Sekar belum kerja
- Tahun 2 dan seterusnya Sekar kerja dengan gross $80,000/tahun

Kalau Sekar belum kerja selama lease 2 tahun:

```python
PARTNER_INCOME_BY_YEAR = {
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 0,
}
```

### 3. Residual fund awal

```python
INITIAL_RESIDUAL_FUND = 10_000
```

Ini cash yang kamu anggap sudah disiapkan khusus untuk bayar residual/balloon.

Kalau belum punya dana khusus, ubah ke:

```python
INITIAL_RESIDUAL_FUND = 0
```

## Cara ubah harga Tesla

Cari bagian ini:

```python
TESLA_MODEL_Y_RWD = Vehicle(
    name="2026 Tesla Model Y RWD",
    price=61_551,
    category="bev",
    fbt_exempt=True,
    fbt_base_value=61_551,
    default_running_costs_year=5_000,
)
```

Ubah `price` dan `fbt_base_value` sesuai harga baru.

Contoh kalau harga drive-away berubah jadi $63,000:

```python
TESLA_MODEL_Y_RWD = Vehicle(
    name="2026 Tesla Model Y RWD",
    price=63_000,
    category="bev",
    fbt_exempt=True,
    fbt_base_value=63_000,
    default_running_costs_year=5_000,
)
```

## Cara simulasi CR-V Hybrid

Cari bagian ini:

```python
HONDA_CRV_HYBRID_EXAMPLE = Vehicle(
    name="Honda CR-V Hybrid example",
    price=58_000,
    category="hybrid",
    fbt_exempt=False,
    fbt_base_value=58_000,
    default_running_costs_year=6_500,
)
```

Ubah harga sesuai quote CR-V.

Lalu aktifkan placeholder CR-V di `QUOTES_TO_COMPARE`:

```python
QUOTES_TO_COMPARE = [
    TESLA_2Y_MAXXIA,
    TESLA_3Y_MAXXIA,
    CRV_HYBRID_PLACEHOLDER,
]
```

## Penting untuk CR-V Hybrid

CR-V Hybrid biasa bukan BEV. Artinya:
- Tidak otomatis FBT-exempt seperti Tesla BEV.
- Kemungkinan ada ECM atau post-tax contribution.
- RFBA tidak bisa dihitung sesederhana Tesla EV.
- Wajib pakai quote formal Maxxia atau provider.

Kalau dapat quote Maxxia CR-V, buat quote seperti ini:

```python
CRV_HYBRID_MAXXIA = LeaseQuote(
    vehicle=HONDA_CRV_HYBRID_EXAMPLE,
    term_years=3,
    annual_package_pretax=21_000,
    annual_admin_fee=200,
    annual_input_tax_credit=1_200,
    annual_post_tax_ecm=3_500,
    annual_rfba_override=12_000,
    residual_override=27_000,
    quote_mode="formal",
    label="CR-V Hybrid Maxxia 3 tahun",
)
```

Lalu masukkan ke:

```python
QUOTES_TO_COMPARE = [
    TESLA_2Y_MAXXIA,
    TESLA_3Y_MAXXIA,
    CRV_HYBRID_MAXXIA,
]
```

## Cara membaca output

### Household cash with lease

Cashflow rumah tangga per bulan setelah novated lease, termasuk:
- Net salary Adien setelah lease
- Net salary Sekar
- FTB A
- FTB B

### Cash impact vs no lease

Selisih cashflow dibanding tidak mengambil lease. Ini mirip angka Maxxia monthly cost.

### After balloon saving

Ini angka paling realistis.

Rumusnya:

```text
household cash with lease - tabungan bulanan untuk balloon
```

Kalau angka ini terlalu ketat, term lease terlalu agresif.

## Interpretasi untuk Tesla 2 tahun

Dengan quote Tesla 2 tahun yang kamu input:
- Annual package: $22,817
- Residual estimate: sekitar $34,622
- Residual fund awal: $10,000
- Tabungan balloon bulanan: sekitar $1,026/bulan

Jadi walaupun Maxxia menampilkan monthly cost sekitar $1,191/bulan, secara mental accounting yang sehat kamu perlu melihatnya sebagai:

```text
$1,191 monthly cash impact
+ sekitar $1,026 saving balloon
= sekitar $2,217/bulan discipline cost
```

## Interpretasi untuk Tesla 3 tahun

Tesla 3 tahun lebih lambat selesai, tetapi:
- Annual package lebih rendah
- Residual lebih rendah
- Tabungan balloon per bulan lebih ringan
- Cashflow keluarga lebih aman

## Kapan pilih 2 tahun

2 tahun masuk akal kalau:
- Kamu ingin cepat selesai
- Kamu punya residual fund awal
- Kamu disiplin sisihkan balloon tiap bulan
- Sekar cukup realistis mulai kerja di tahun kedua
- Kamu siap cashflow tahun pertama lebih ketat

## Kapan pilih 3 tahun

3 tahun lebih masuk akal kalau:
- Kamu ingin cashflow keluarga lebih aman
- Income Sekar belum pasti
- Kamu ingin risiko emergency lebih rendah
- Kamu tidak ingin terlalu tertekan oleh balloon 2 tahun

## Kapan jangan pakai script ini sebagai keputusan final

Jangan pakai angka final sebelum kamu punya:

1. Formal quote Maxxia.
2. Residual/balloon resmi.
3. Effective interest rate.
4. Detail insurance budget.
5. Detail tyre budget.
6. Detail charging/fuel budget.
7. Early termination cost jika resign dari ILM.
8. Konfirmasi apakah bisa re-novate ke employer baru.
9. Konfirmasi FTB eligibility dari Services Australia.
10. Tax check dari accountant kalau nilainya besar.

## Disclaimer

Script ini estimator pribadi. Bukan financial advice, tax advice, legal advice, atau keputusan resmi Services Australia.
