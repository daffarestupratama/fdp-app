"""
app.py — API prediksi financial distress (3 indikator) + halaman web.

API bersifat publik agar dapat diintegrasikan oleh aplikasi pihak ketiga.
Dokumentasi interaktif tersedia otomatis di /docs (Swagger) dan /redoc.
"""
from pathlib import Path
from typing import List, Optional, Union

import joblib
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from features import build_feature_row, align_to_model
from commentary import load_commentary_stats, generate_commentary
from validation import validate_accounting

BASE = Path(__file__).parent

INDICATORS = {
    "ppk":     "Masuk Papan Pemantauan Khusus (BEI)",
    "negeq":   "Ekuitas negatif",
    "conloss": "Rugi bersih dua tahun berturut-turut",
}
ARTIFACTS = {k: joblib.load(BASE / f"artifact_{k}.joblib") for k in INDICATORS}
COMMENTARY = load_commentary_stats(BASE / "commentary_stats.json")

INDUSTRY_GROUPS = [
    "Automobiles and Components", "Banks", "Capital Goods",
    "Commercial and Professional Services",
    "Consumer Discretionary Distribution and Retail",
    "Consumer Durables and Apparel", "Consumer Services",
    "Consumer Staples Distribution and Retail", "Energy", "Financial Services",
    "Food, Beverage and Tobacco", "Health Care Equipment and Services",
    "Household and Personal Products", "Insurance", "Materials",
    "Media and Entertainment", "Pharmaceuticals, Biotechnology and Life Sciences",
    "Real Estate Management and Development", "Software and Services",
    "Technology Hardware and Equipment", "Telecommunication Services",
    "Transportation", "Utilities",
]

# contoh dipakai untuk dokumentasi /docs
_EXAMPLE = {
    "indicator": "ppk", "industry_group": "Food, Beverage and Tobacco",
    "year": 2023, "ipo_year": 1997, "year_established": 1988,
    "parent_percent_owned": 79.68, "pct_owned_all_institutions": 2.10,
    "total_assets": 28846243, "total_liabilities": 6280237, "total_equity": 22566006,
    "total_current_assets": 7118202, "total_current_liabilities": 3882141, "total_debt": 4005052,
    "inventory": 3122454, "net_ppe": 18105649, "cash_st": 2089508, "working_capital": 3236061,
    "total_revenue": 20745473, "cogs": 17950652, "operating_income": 1672092,
    "ebitda": 3007949, "ebit": 1672092, "net_income": 1088170,
    "cfo": 2538738, "net_change_in_cash": 469892, "market_cap": 13520935.54,
    "shares_outstanding": 1924688333, "current_ratio": 1.834, "quick_ratio": 0.765,
    "prev_total_revenue": 21828591, "prev_net_income": 1792050, "prev_total_assets": 29249340,
    "prev_total_equity": 22243221, "prev_cfo": 1835397,
}


class PredictRequest(BaseModel):
    indicator: str = Field(..., description="Indikator distress yang diprediksi: 'ppk', 'negeq', atau 'conloss'.")
    # nilai dalam Rp juta kecuali disebutkan lain; field kosong dibiarkan null dan ditangani model.
    total_assets: Optional[float] = Field(None, description="Total aset.")
    total_liabilities: Optional[float] = Field(None, description="Total liabilitas.")
    total_equity: Optional[float] = Field(None, description="Total ekuitas (boleh negatif).")
    total_current_assets: Optional[float] = Field(None, description="Total aset lancar.")
    total_current_liabilities: Optional[float] = Field(None, description="Total kewajiban lancar.")
    total_debt: Optional[float] = Field(None, description="Total utang berbunga.")
    inventory: Optional[float] = Field(None, description="Persediaan.")
    prepaid_exp: Optional[float] = Field(None, description="Biaya dibayar di muka.")
    net_ppe: Optional[float] = Field(None, description="Aset tetap bersih (net PP&E).")
    cash_st: Optional[float] = Field(None, description="Kas & investasi jangka pendek.")
    net_intangibles: Optional[float] = Field(None, description="Aset tak berwujud bersih.")
    working_capital: Optional[float] = Field(None, description="Modal kerja (boleh negatif).")
    total_revenue: Optional[float] = Field(None, description="Pendapatan.")
    cogs: Optional[float] = Field(None, description="Beban pokok penjualan.")
    operating_income: Optional[float] = Field(None, description="Laba operasi (boleh negatif).")
    ebitda: Optional[float] = Field(None, description="EBITDA (boleh negatif).")
    ebit: Optional[float] = Field(None, description="EBIT (boleh negatif).")
    net_income: Optional[float] = Field(None, description="Laba bersih (boleh negatif).")
    cfo: Optional[float] = Field(None, description="Arus kas operasi (boleh negatif).")
    net_change_in_cash: Optional[float] = Field(None, description="Perubahan kas bersih (boleh negatif).")
    market_cap: Optional[float] = Field(None, description="Kapitalisasi pasar (Rp juta).")
    shares_outstanding: Optional[float] = Field(None, description="Jumlah saham beredar (lembar).")
    current_ratio: Optional[float] = Field(None, description="Current ratio (opsional; dihitung bila kosong).")
    quick_ratio: Optional[float] = Field(None, description="Quick ratio (opsional; dihitung bila kosong).")
    # tahun sebelumnya (untuk fitur pertumbuhan)
    prev_total_revenue: Optional[float] = Field(None, description="Pendapatan tahun sebelumnya.")
    prev_net_income: Optional[float] = Field(None, description="Laba bersih tahun sebelumnya (boleh negatif).")
    prev_total_assets: Optional[float] = Field(None, description="Total aset tahun sebelumnya.")
    prev_total_equity: Optional[float] = Field(None, description="Total ekuitas tahun sebelumnya (boleh negatif).")
    prev_cfo: Optional[float] = Field(None, description="Arus kas operasi tahun sebelumnya (boleh negatif).")
    # metadata
    industry_group: Optional[str] = Field(None, description="Sektor industri (salah satu dari daftar /api/meta).")
    year: Optional[float] = Field(None, description="Tahun laporan.")
    ipo_year: Optional[float] = Field(None, description="Tahun IPO.")
    year_established: Optional[float] = Field(None, description="Tahun perusahaan didirikan.")
    parent_percent_owned: Optional[float] = Field(None, description="Kepemilikan induk (%).")
    pct_owned_all_institutions: Optional[float] = Field(None, description="Kepemilikan institusi (%).")
    pct_owned_insiders: Optional[float] = Field(None, description="Kepemilikan insider (%).")

    model_config = {"json_schema_extra": {"example": _EXAMPLE}}


class CommentaryItem(BaseModel):
    ratio: str = Field(..., description="Nama teknis rasio.")
    label: str = Field(..., description="Label rasio yang mudah dibaca.")
    value: Union[str, float] = Field(..., description="Nilai rasio perusahaan (dapat berupa teks terformat, mis. persen).")
    healthy_range: str = Field(..., description="Rentang sehat (kuartil bawah–atas kelas sehat).")
    shap_rank: int = Field(..., description="Peringkat kepentingan fitur berdasarkan SHAP.")
    severity: str = Field(..., description="Tingkat keparahan: 'ringan', 'sedang', atau 'tinggi'.")
    message: str = Field(..., description="Penjelasan kondisi rasio.")
    suggestion: str = Field(..., description="Saran penanganan.")


class PredictResponse(BaseModel):
    indicator: str = Field(..., description="Indikator yang diprediksi.")
    indicator_label: str = Field(..., description="Nama indikator yang mudah dibaca.")
    distress_2y: bool = Field(..., description="True bila diprediksi berisiko distress dalam 2 tahun.")
    probability: float = Field(..., description="Probabilitas mentah kelas distress (0–1).")
    threshold: float = Field(..., description="Batas keputusan indikator (hasil tuning recall).")
    risk_ratio: float = Field(..., description="probability / threshold. Nilai 1.0 berarti tepat di batas; >1 berarti telah melewati batas.")
    risk_level: str = Field(..., description="'Relatif sehat', 'Perlu diwaspadai', atau 'Berisiko mengalami financial distress'.")
    commentary: List[CommentaryItem] = Field(..., description="Catatan rasio yang berada di luar rentang sehat.")
    input_warnings: List[str] = Field(..., description="Peringatan konsistensi akuntansi pada input (bila ada).")
    model_name: str = Field(..., description="Algoritma model yang dipakai indikator ini.")


class MetaResponse(BaseModel):
    indicators: list
    industry_groups: List[str]


DESCRIPTION = """
API prediksi *financial distress* perusahaan publik Indonesia dua tahun ke depan,
berdasarkan model *tree-based ensemble* yang dikembangkan pada penelitian tugas akhir.

Tersedia tiga indikator distress: masuk Papan Pemantauan Khusus (`ppk`),
ekuitas negatif (`negeq`), dan rugi bersih dua tahun berturut-turut (`conloss`).

Alur integrasi: panggil `GET /api/meta` untuk memperoleh daftar indikator dan sektor,
lalu kirim `POST /api/predict` berisi akun keuangan perusahaan untuk memperoleh prediksi,
tingkat risiko, dan catatan kondisi keuangan. API tidak memerlukan autentikasi.
"""

app = FastAPI(
    title="Financial Distress Prediction API",
    description=DESCRIPTION,
    version="1.0.0",
    contact={"name": "Daffa", "url": "https://fdp.daffa.me"},
)

# Izinkan pemanggilan lintas-asal agar aplikasi pihak ketiga (termasuk dari browser
# domain lain) dapat mengakses API ini.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/meta", response_model=MetaResponse, tags=["metadata"],
         summary="Daftar indikator & sektor industri")
def meta():
    """Mengembalikan daftar indikator distress yang tersedia beserta daftar sektor
    industri yang valid untuk field `industry_group`."""
    return {
        "indicators": [{"id": k, "label": v} for k, v in INDICATORS.items()],
        "industry_groups": INDUSTRY_GROUPS,
    }


@app.post("/api/predict", response_model=PredictResponse, tags=["prediction"],
          summary="Prediksi financial distress satu perusahaan")
def predict(req: PredictRequest):
    """Memprediksi potensi financial distress dua tahun ke depan untuk satu perusahaan.

    Field akun yang tidak diketahui boleh dikosongkan (null). Current/quick ratio
    akan dihitung otomatis dari komponennya bila tidak diisi.
    """
    if req.indicator not in ARTIFACTS:
        raise HTTPException(status_code=400, detail=f"Indikator '{req.indicator}' tidak dikenal")

    art = ARTIFACTS[req.indicator]
    payload = req.model_dump()

    row = build_feature_row(payload)
    X = align_to_model(row, art["feature_order"])
    proba = float(art["model"].predict_proba(X)[0, 1])
    thr = float(art["threshold"])
    risk_ratio = proba / thr if thr > 0 else 0.0

    if proba >= thr:
        level = "Berisiko mengalami financial distress"
    elif proba >= 0.5 * thr:
        level = "Perlu diwaspadai"
    else:
        level = "Relatif sehat"

    ratios = row.iloc[0].to_dict()
    notes = generate_commentary(req.indicator, ratios, COMMENTARY)

    return {
        "indicator": req.indicator,
        "indicator_label": INDICATORS[req.indicator],
        "distress_2y": bool(proba >= thr),
        "probability": round(proba, 6),
        "threshold": round(thr, 6),
        "risk_ratio": round(risk_ratio, 4),
        "risk_level": level,
        "commentary": notes,
        "input_warnings": validate_accounting(payload),
        "model_name": art["model_name"],
    }


# halaman web statis (didaftarkan terakhir agar tidak menutup route /api)
app.mount("/", StaticFiles(directory=str(BASE / "static"), html=True), name="static")
