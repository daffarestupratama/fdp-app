"""
commentary.py — menghasilkan peringatan & saran per rasio keuangan.

Membandingkan rasio perusahaan terhadap rentang sehat (kuartil kelas sehat)
dari commentary_stats.json, per indikator, terurut menurut kekuatan SHAP.
Tidak menyentuh model — murni berbasis aturan agar mudah dijelaskan.
"""
import json
import math

# Saran spesifik per rasio. Rasio yang tidak ada di sini memakai saran generik
# berdasarkan arahnya.
ADVICE = {
    "Debt_Equity": "Ketergantungan utang terhadap ekuitas tinggi. Pertimbangkan menahan ekspansi berbiaya utang, restrukturisasi tenor, atau memperkuat ekuitas.",
    "Debt_TA": "Porsi utang berbunga terhadap aset besar. Tinjau ulang struktur pendanaan dan prioritaskan pelunasan utang berbiaya tinggi.",
    "TL_TA": "Total liabilitas mendominasi aset. Perkuat permodalan dan kurangi kewajiban yang tidak produktif.",
    "NetDebt_EBITDA": "Beban utang bersih besar relatif terhadap kemampuan menghasilkan EBITDA. Tingkatkan EBITDA atau turunkan utang bersih.",
    "ROE": "Imbal hasil terhadap ekuitas rendah. Tinjau profitabilitas inti dan efisiensi penggunaan modal pemegang saham.",
    "ROA": "Aset belum menghasilkan laba secara efisien. Evaluasi produktivitas aset dan margin operasi.",
    "NetMargin": "Margin laba bersih tipis. Tinjau struktur biaya, harga jual, dan beban non-operasional.",
    "OpMargin": "Margin operasi lemah. Fokus pada efisiensi biaya operasional inti.",
    "GrossMargin": "Margin kotor rendah. Periksa harga pokok penjualan dan daya tawar harga.",
    "CR": "Likuiditas jangka pendek tertekan; aset lancar tipis menutup kewajiban lancar. Perbaiki manajemen modal kerja.",
    "CashST_CL": "Kas terhadap kewajiban lancar rendah. Jaga cadangan kas dan kelola jatuh tempo utang jangka pendek.",
    "CashST_TA": "Porsi kas terhadap aset rendah. Perkuat posisi kas untuk menahan tekanan likuiditas.",
    "Equity_TA": "Bantalan ekuitas terhadap aset tipis. Tambah permodalan untuk memperkuat solvabilitas.",
    "Sales_growth": "Pertumbuhan penjualan melemah. Tinjau strategi pasar dan permintaan produk.",
    "NI_growth": "Pertumbuhan laba bersih menurun. Telusuri sumber penurunan profitabilitas.",
    "Equity_growth": "Pertumbuhan ekuitas melambat, bisa menandakan akumulasi laba ditahan yang lemah.",
    "CFO_growth": "Pertumbuhan arus kas operasi melemah. Perhatikan kualitas laba dan konversi kas.",
    "CFO_TL": "Arus kas operasi tipis terhadap total liabilitas. Tingkatkan kas dari operasi untuk menutup kewajiban.",
    "Altman_X3_EBIT_TA": "Kemampuan aset menghasilkan EBIT rendah. Fokus pada profitabilitas operasi.",
    "Altman_X4_MVE_TL": "Nilai pasar ekuitas kecil dibanding liabilitas; persepsi pasar atas solvabilitas lemah.",
    "Altman_X5_SalesTA_AssetTurnover": "Perputaran aset rendah. Tingkatkan utilisasi aset untuk menghasilkan penjualan.",
    "PPE_TA": "Porsi aset tetap rendah relatif terhadap pola perusahaan sehat sektor ini.",
}

GENERIC = {
    "high_good": "Nilainya lebih rendah dari kebanyakan perusahaan sehat. Perlu diperbaiki agar mendekati rentang sehat.",
    "low_good": "Nilainya lebih tinggi dari kebanyakan perusahaan sehat. Perlu diturunkan agar mendekati rentang sehat.",
}


def load_commentary_stats(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_nan(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def _fmt(x) -> str:
    return f"{x:.3f}"


def generate_commentary(indicator: str, ratios: dict, stats: dict, max_items: int = 8) -> list:
    """
    indicator : 'ppk' | 'negeq' | 'conloss'
    ratios    : dict nama_rasio -> nilai (dari baris fitur perusahaan)
    stats     : commentary_stats penuh (hasil load_commentary_stats)
    Mengembalikan daftar peringatan untuk rasio yang berada di sisi tidak sehat,
    terurut menurut kekuatan SHAP (shap_rank) dan dibatasi max_items.
    """
    flagged = []
    for item in stats.get(indicator, []):
        name = item["ratio"]
        v = ratios.get(name)
        if _is_nan(v):
            continue

        direction = item["direction"]
        p25, p75 = item["healthy_p25"], item["healthy_p75"]
        iqr = max(p75 - p25, 1e-9)

        if direction == "high_good":
            if v >= p25:
                continue  # sehat
            distance = (p25 - v) / iqr
            posisi = f"di bawah kuartil bawah perusahaan sehat ({_fmt(p25)})"
        else:  # low_good
            if v <= p75:
                continue  # sehat
            distance = (v - p75) / iqr
            posisi = f"di atas kuartil atas perusahaan sehat ({_fmt(p75)})"

        severity = "tinggi" if distance >= 1.0 else ("sedang" if distance >= 0.4 else "ringan")

        flagged.append({
            "ratio": name,
            "label": item["label"],
            "value": round(float(v), 4),
            "healthy_range": f"{_fmt(p25)} – {_fmt(p75)}",
            "shap_rank": item["shap_rank"],
            "severity": severity,
            "message": f"{item['label']} ({_fmt(v)}) {posisi}.",
            "suggestion": ADVICE.get(name, GENERIC[direction]),
        })

    flagged.sort(key=lambda d: d["shap_rank"])  # paling berpengaruh dulu
    return flagged[:max_items]
