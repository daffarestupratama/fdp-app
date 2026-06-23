"""
validation.py — pemeriksaan konsistensi antar-field berdasarkan identitas
akuntansi sederhana. Bersifat peringatan lunak (tidak memblokir prediksi),
dan hanya memeriksa pasangan field yang sama-sama terisi.
"""


def validate_accounting(p: dict, rel_tol: float = 0.02) -> list:
    """Kembalikan daftar peringatan bila ada ketidaksesuaian antar nilai akun.
    rel_tol = toleransi relatif (default 2%) untuk menampung selisih pembulatan.
    """
    def g(k):
        try:
            return float(p.get(k))
        except (TypeError, ValueError):
            return None

    def close(a, b):
        return abs(a - b) <= rel_tol * max(abs(a), abs(b), 1.0)

    TA, TL, EQ = g("total_assets"), g("total_liabilities"), g("total_equity")
    CA, CL, WC = g("total_current_assets"), g("total_current_liabilities"), g("working_capital")
    rev, cogs = g("total_revenue"), g("cogs")

    w = []
    if None not in (TA, TL, EQ) and not close(TA, TL + EQ):
        w.append(f"Total Aset ({TA:,.0f}) \u2260 Liabilitas + Ekuitas ({TL + EQ:,.0f}).")
    if None not in (WC, CA, CL) and not close(WC, CA - CL):
        w.append(f"Modal Kerja ({WC:,.0f}) \u2260 Aset Lancar \u2212 Kewajiban Lancar ({CA - CL:,.0f}).")
    if None not in (CA, TA) and CA > TA * (1 + rel_tol):
        w.append("Aset Lancar melebihi Total Aset.")
    if None not in (CL, TL) and CL > TL * (1 + rel_tol):
        w.append("Kewajiban Lancar melebihi Total Liabilitas.")
    if None not in (cogs, rev) and cogs > rev * (1 + rel_tol):
        w.append("Beban Pokok Penjualan melebihi Pendapatan.")
    return w
