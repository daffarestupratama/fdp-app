"""
features.py — feature engineering untuk SERVING (inference satu perusahaan).

Mereplikasi build_features() dari notebook secara persis, tetapi bekerja untuk
SATU perusahaan dengan data tahun berjalan + tahun sebelumnya (untuk fitur growth).

Keputusan deployment:
- Current Ratio (CR), Quick Ratio (QR), dan Working Capital (WC) DIINPUT LANGSUNG
  oleh user, tidak dihitung ulang dari akun.
- Tidak ada imputasi / PCA / missing-indicator / winsorizing (sesuai model final).
  Nilai NaN dibiarkan apa adanya; model tree (XGBoost/LightGBM/CatBoost) menanganinya.

Alur pemakaian di app:
    row = build_feature_row(payload)              # 1 baris berisi SELURUH fitur
    X   = align_to_model(row, feature_order)      # disusun sesuai kolom model
    proba = model.predict_proba(X)[0, 1]
"""

import numpy as np
import pandas as pd

_SMALL = 1e-6


# --------------------------------------------------------------------------- #
# Helper numerik (meniru perilaku notebook)
# --------------------------------------------------------------------------- #
def _num(x):
    """None / '' / nilai tak valid -> np.nan, selain itu float."""
    if x is None:
        return np.nan
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def _safe_div(num, den):
    """Meniru safe_div notebook: pembagi 0/NaN -> NaN, hasil inf -> NaN."""
    num, den = _num(num), _num(den)
    if np.isnan(num) or np.isnan(den) or den == 0:
        return np.nan
    res = num / den
    return res if np.isfinite(res) else np.nan


def _signed_log(x):
    """Meniru signed_log notebook: sign(x) * log(|x| + 1e-6)."""
    x = _num(x)
    if np.isnan(x):
        return np.nan
    return float(np.sign(x) * np.log(np.abs(x) + _SMALL))


def _growth(cur, prev):
    """Meniru pandas pct_change(fill_method=None): (cur - prev) / prev.

    - prev None/NaN  -> NaN
    - prev == 0      -> inf bila cur != 0, NaN bila cur == 0 (sama seperti pct_change,
                        sengaja tidak dibersihkan agar identik dengan notebook).
    """
    cur, prev = _num(cur), _num(prev)
    if np.isnan(cur) or np.isnan(prev):
        return np.nan
    if prev == 0:
        return np.inf if cur != 0 else np.nan
    return (cur - prev) / prev


# --------------------------------------------------------------------------- #
# Daftar field input yang diharapkan dari user (acuan untuk form & schema app)
# --------------------------------------------------------------------------- #
RAW_FIELDS_CURRENT = [
    "total_current_assets", "total_current_liabilities", "total_assets",
    "total_liabilities", "total_equity", "total_debt", "inventory",
    "prepaid_exp", "net_ppe", "total_revenue", "cogs", "operating_income",
    "ebitda", "ebit", "net_income", "cfo", "net_change_in_cash", "cash_st",
    "net_intangibles", "shares_outstanding", "market_cap",
    "working_capital", "current_ratio", "quick_ratio",  # diinput user
]
PREV_FIELDS = [
    "prev_total_revenue", "prev_net_income", "prev_total_assets",
    "prev_total_equity", "prev_cfo",
]
META_FIELDS = [
    "industry_group", "year", "ipo_year", "year_established",
    "parent_percent_owned", "pct_owned_all_institutions", "pct_owned_insiders",
]


# --------------------------------------------------------------------------- #
# Inti: bangun satu baris fitur (superset semua fitur sebelum diseleksi model)
# --------------------------------------------------------------------------- #
def build_feature_row(p: dict) -> pd.DataFrame:
    """Bangun DataFrame 1 baris berisi SELURUH fitur kandidat.

    p : dict akun mentah tahun berjalan + tahun sebelumnya + metadata.
        Field yang tidak diisi cukup dikosongkan (None) -> akan menjadi NaN.
    """
    # --- akun tahun berjalan ---
    CA     = _num(p.get("total_current_assets"))
    CL     = _num(p.get("total_current_liabilities"))
    TA     = _num(p.get("total_assets"))
    TL     = _num(p.get("total_liabilities"))
    Eq     = _num(p.get("total_equity"))
    Debt   = _num(p.get("total_debt"))
    Inv    = _num(p.get("inventory"))
    Prep   = _num(p.get("prepaid_exp"))
    PPE    = _num(p.get("net_ppe"))
    Sales  = _num(p.get("total_revenue"))
    COGS   = _num(p.get("cogs"))
    OpInc  = _num(p.get("operating_income"))
    EBITDA = _num(p.get("ebitda"))
    EBIT   = _num(p.get("ebit"))
    NI     = _num(p.get("net_income"))
    CFO    = _num(p.get("cfo"))
    NetCash = _num(p.get("net_change_in_cash"))
    CashST = _num(p.get("cash_st"))
    Intang = _num(p.get("net_intangibles"))
    Shares = _num(p.get("shares_outstanding"))
    MktCap = _num(p.get("market_cap"))
    WC     = _num(p.get("working_capital"))   # user input
    CR_in  = _num(p.get("current_ratio"))     # opsional: kalau diisi -> dipakai
    QR_in  = _num(p.get("quick_ratio"))       # opsional: kalau diisi -> dipakai

    # --- tahun sebelumnya (untuk growth YoY) ---
    Sales_prev = _num(p.get("prev_total_revenue"))
    NI_prev    = _num(p.get("prev_net_income"))
    TA_prev    = _num(p.get("prev_total_assets"))
    Eq_prev    = _num(p.get("prev_total_equity"))
    CFO_prev   = _num(p.get("prev_cfo"))

    # --- metadata ---
    year     = _num(p.get("year"))
    ipo_year = _num(p.get("ipo_year"))
    year_est = _num(p.get("year_established"))

    NetDebt = Debt - CashST  # NaN merambat otomatis bila salah satu NaN

    f = {}

    # --- LIKUIDITAS & MODAL KERJA ---
    # CR & QR: pakai input user bila diisi; bila kosong, hitung dari komponen
    # (QR dengan rumus sederhana = aproksimasi, bisa sedikit > versi S&P).
    inv0  = 0.0 if np.isnan(Inv)  else Inv
    prep0 = 0.0 if np.isnan(Prep) else Prep
    f["CR"] = CR_in if not np.isnan(CR_in) else _safe_div(CA, CL)
    f["QR"] = QR_in if not np.isnan(QR_in) else _safe_div(CA - inv0 - prep0, CL)
    f["WC_Sales"]      = _safe_div(WC, Sales)
    f["CA_TA"]         = _safe_div(CA, TA)
    f["CL_TA"]         = _safe_div(CL, TA)
    f["CashST_TA"]     = _safe_div(CashST, TA)
    f["CashST_CL"]     = _safe_div(CashST, CL)
    f["Inventory_CA"]  = _safe_div(Inv, CA)
    f["Prepaid_CA"]    = _safe_div(Prep, CA)

    # --- LEVERAGE & STRUKTUR MODAL ---
    f["TL_TA"]          = _safe_div(TL, TA)
    f["Debt_TA"]        = _safe_div(Debt, TA)
    f["Debt_Equity"]    = _safe_div(Debt, Eq)
    f["Equity_TA"]      = _safe_div(Eq, TA)
    f["NetDebt_EBITDA"] = _safe_div(NetDebt, EBITDA)
    f["PPE_TA"]         = _safe_div(PPE, TA)
    f["Intang_TA"]      = _safe_div(Intang, TA)
    f["Altman_X1_WC_TA"]              = _safe_div(WC, TA)
    f["Altman_X3_EBIT_TA"]            = _safe_div(EBIT, TA)
    f["Altman_X4_MVE_TL"]             = _safe_div(MktCap, TL)
    f["Altman_X5_SalesTA_AssetTurnover"] = _safe_div(Sales, TA)

    # --- PROFITABILITAS & MARGIN ---
    f["ROA"]         = _safe_div(NI, TA)
    f["ROE"]         = _safe_div(NI, Eq)
    f["EBITDA_TA"]   = _safe_div(EBITDA, TA)
    f["GrossMargin"] = _safe_div(Sales - COGS, Sales)
    f["OpMargin"]    = _safe_div(OpInc, Sales)
    f["NetMargin"]   = _safe_div(NI, Sales)

    # --- ARUS KAS ---
    f["CFO_TA"]     = _safe_div(CFO, TA)
    f["CFO_TL"]     = _safe_div(CFO, TL)
    f["CFO_Sales"]  = _safe_div(CFO, Sales)
    f["NetCash_TA"] = _safe_div(NetCash, TA)

    # --- PER SHARE & MARKET ---
    f["EPS_proxy"]       = _safe_div(NI, Shares) * 1_000_000
    f["Sales_per_share"] = _safe_div(Sales, Shares) * 1_000_000
    f["CFO_per_share"]   = _safe_div(CFO, Shares) * 1_000_000
    f["log_TA"]     = _signed_log(TA)
    f["log_Sales"]  = _signed_log(Sales)
    f["log_MktCap"] = _signed_log(MktCap)
    f["PB"]         = _safe_div(MktCap, Eq)

    # --- UMUR PERUSAHAAN ---
    f["Age_When_IPO"]    = ipo_year - year_est
    f["Years_Since_IPO"] = year - ipo_year

    # --- GROWTH YoY ---
    f["Sales_growth"]  = _growth(Sales, Sales_prev)
    f["NI_growth"]     = _growth(NI, NI_prev)
    f["TA_growth"]     = _growth(TA, TA_prev)
    f["Equity_growth"] = _growth(Eq, Eq_prev)
    f["CFO_growth"]    = _growth(CFO, CFO_prev)

    # --- KEPEMILIKAN (dipertahankan sebagai fitur; nama kolom = persis notebook) ---
    f["Parent Percent Owned (%)"]            = _num(p.get("parent_percent_owned"))
    f["Percent Owned - All Institutions (%)"] = _num(p.get("pct_owned_all_institutions"))
    f["Percent Owned - Insiders (%)"]        = _num(p.get("pct_owned_insiders"))

    row = pd.DataFrame([f])

    # --- ONE-HOT INDUSTRI ---
    # Notebook membuang koma lalu prefix "industry" dan drop_first=True.
    # Untuk satu baris cukup set kolom sektor user = 1; kolom sektor lain
    # akan otomatis menjadi 0 saat align_to_model (reindex). Bila sektor user
    # adalah kategori referensi (yang di-drop), kolomnya tidak ada di
    # feature_order sehingga semua dummy industri = 0 -> ini perilaku yang benar.
    sector = p.get("industry_group")
    if sector:
        col = "industry_" + str(sector).replace(",", "")
        row[col] = 1

    return row


# --------------------------------------------------------------------------- #
# Susun kolom persis seperti yang dilihat model saat training
# --------------------------------------------------------------------------- #
def align_to_model(row: pd.DataFrame, feature_order: list) -> pd.DataFrame:
    """Pilih & urutkan kolom sesuai feature_order model.

    - Kolom yang tidak ada di `row` (mis. dummy industri sektor lain) diisi 0.
    - Kolom rasio yang NaN DIBIARKAN NaN (tidak diisi 0) -> ditangani model tree.
    - Hasil akhir bertipe float agar konsisten untuk predict_proba.
    """
    aligned = row.reindex(columns=feature_order, fill_value=0)
    return aligned.astype(float)
