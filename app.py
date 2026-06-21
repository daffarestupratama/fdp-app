"""
app.py — API prediksi financial distress (3 indikator).

Memuat ketiga artefak model + commentary_stats sekali saat startup, lalu
melayani endpoint prediksi dan halaman web statis.
"""
from pathlib import Path
from typing import Optional

import joblib
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from features import build_feature_row, align_to_model
from commentary import load_commentary_stats, generate_commentary
from validation import validate_accounting

BASE = Path(__file__).parent

# --- muat artefak & commentary sekali di startup ---
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


class PredictRequest(BaseModel):
    indicator: str = Field(..., description="ppk | negeq | conloss")

    # akun tahun berjalan (boleh kosong -> NaN, ditangani model)
    total_current_assets: Optional[float] = None
    total_current_liabilities: Optional[float] = None
    total_assets: Optional[float] = None
    total_liabilities: Optional[float] = None
    total_equity: Optional[float] = None
    total_debt: Optional[float] = None
    inventory: Optional[float] = None
    prepaid_exp: Optional[float] = None
    net_ppe: Optional[float] = None
    total_revenue: Optional[float] = None
    cogs: Optional[float] = None
    operating_income: Optional[float] = None
    ebitda: Optional[float] = None
    ebit: Optional[float] = None
    net_income: Optional[float] = None
    cfo: Optional[float] = None
    net_change_in_cash: Optional[float] = None
    cash_st: Optional[float] = None
    net_intangibles: Optional[float] = None
    shares_outstanding: Optional[float] = None
    market_cap: Optional[float] = None
    working_capital: Optional[float] = None
    current_ratio: Optional[float] = None
    quick_ratio: Optional[float] = None

    # tahun sebelumnya (untuk growth YoY)
    prev_total_revenue: Optional[float] = None
    prev_net_income: Optional[float] = None
    prev_total_assets: Optional[float] = None
    prev_total_equity: Optional[float] = None
    prev_cfo: Optional[float] = None

    # metadata
    industry_group: Optional[str] = None
    year: Optional[float] = None
    ipo_year: Optional[float] = None
    year_established: Optional[float] = None
    parent_percent_owned: Optional[float] = None
    pct_owned_all_institutions: Optional[float] = None
    pct_owned_insiders: Optional[float] = None


app = FastAPI(title="Prediksi Financial Distress 2 Tahun")


@app.get("/api/meta")
def meta():
    return {
        "indicators": [{"id": k, "label": v} for k, v in INDICATORS.items()],
        "industry_groups": INDUSTRY_GROUPS,
    }


@app.post("/api/predict")
def predict(req: PredictRequest):
    if req.indicator not in ARTIFACTS:
        raise HTTPException(status_code=400, detail=f"Indikator '{req.indicator}' tidak dikenal")

    art = ARTIFACTS[req.indicator]
    payload = req.model_dump()

    row = build_feature_row(payload)
    X = align_to_model(row, art["feature_order"])
    proba = float(art["model"].predict_proba(X)[0, 1])
    thr = float(art["threshold"])

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
        "risk_score": round(proba * 100, 2),
        "risk_level": level,
        "commentary": notes,
        "model_name": art["model_name"],
        "input_warnings": validate_accounting(payload),
    }


# halaman web statis (didaftarkan terakhir agar tidak menutup route /api)
app.mount("/", StaticFiles(directory=str(BASE / "static"), html=True), name="static")
