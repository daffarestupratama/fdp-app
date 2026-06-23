# Dokumentasi API Prediksi Financial Distress

API ini memprediksi potensi *financial distress* perusahaan publik Indonesia untuk dua
tahun ke depan menggunakan model *tree-based ensemble*. API bersifat publik dan dapat
diintegrasikan oleh aplikasi pihak ketiga tanpa autentikasi.

- **Base URL:** `https://fdp.daffa.me`
- **Format:** JSON (request dan response)
- **Autentikasi:** tidak diperlukan
- **CORS:** terbuka untuk semua sumber (dapat dipanggil langsung dari browser)
- **Dokumentasi interaktif:** `https://fdp.daffa.me/docs` (Swagger UI) dan `https://fdp.daffa.me/redoc`

---

## 1. Indikator yang Tersedia

API menyediakan tiga indikator financial distress yang dapat dipilih melalui field `indicator`:

| Kode | Indikator |
|------|-----------|
| `ppk` | Masuk Papan Pemantauan Khusus (BEI) |
| `negeq` | Ekuitas negatif |
| `conloss` | Rugi bersih dua tahun berturut-turut |

---

## 2. Endpoint

### 2.1 `GET /api/meta`

Mengembalikan daftar indikator dan daftar sektor industri yang valid untuk field `industry_group`.

**Contoh response:**

```json
{
  "indicators": [
    {"id": "ppk", "label": "Masuk Papan Pemantauan Khusus (BEI)"},
    {"id": "negeq", "label": "Ekuitas negatif"},
    {"id": "conloss", "label": "Rugi bersih dua tahun berturut-turut"}
  ],
  "industry_groups": ["Automobiles and Components", "Banks", "..."]
}
```

### 2.2 `POST /api/predict`

Memprediksi financial distress satu perusahaan. Body berupa JSON berisi akun keuangan.

**Aturan input:**

- Field `indicator` wajib diisi.
- Seluruh field akun bersifat opsional. Field yang tidak diketahui boleh dikosongkan
  (tidak disertakan atau bernilai `null`); model menangani nilai kosong secara langsung.
- Nilai akun dalam satuan **Rupiah juta**, kecuali `shares_outstanding` (lembar),
  `market_cap` (Rp juta), persentase kepemilikan (%), dan field tahun.
- `current_ratio` dan `quick_ratio` opsional; bila dikosongkan, keduanya dihitung otomatis
  dari komponennya.
- Field tahun sebelumnya (`prev_*`) diperlukan untuk menghitung fitur pertumbuhan.
- Angka dikirim dalam format polos (pemisah desimal titik, tanpa pemisah ribuan), mis. `13520935.54`.

---

## 3. Field Request

### Tahun berjalan
| Field | Tipe | Keterangan |
|-------|------|------------|
| `indicator` | string | **Wajib.** `ppk`, `negeq`, atau `conloss` |
| `total_assets` | number | Total aset |
| `total_liabilities` | number | Total liabilitas |
| `total_equity` | number | Total ekuitas (boleh negatif) |
| `total_current_assets` | number | Aset lancar |
| `total_current_liabilities` | number | Kewajiban lancar |
| `total_debt` | number | Total utang berbunga |
| `inventory` | number | Persediaan |
| `prepaid_exp` | number | Biaya dibayar di muka |
| `net_ppe` | number | Aset tetap bersih |
| `cash_st` | number | Kas & investasi jangka pendek |
| `net_intangibles` | number | Aset tak berwujud bersih |
| `working_capital` | number | Modal kerja (boleh negatif) |
| `total_revenue` | number | Pendapatan |
| `cogs` | number | Beban pokok penjualan |
| `operating_income` | number | Laba operasi (boleh negatif) |
| `ebitda` | number | EBITDA (boleh negatif) |
| `ebit` | number | EBIT (boleh negatif) |
| `net_income` | number | Laba bersih (boleh negatif) |
| `cfo` | number | Arus kas operasi (boleh negatif) |
| `net_change_in_cash` | number | Perubahan kas bersih (boleh negatif) |
| `market_cap` | number | Kapitalisasi pasar (Rp juta) |
| `shares_outstanding` | number | Jumlah saham beredar (lembar) |
| `current_ratio` | number | Current ratio (opsional) |
| `quick_ratio` | number | Quick ratio (opsional) |

### Tahun sebelumnya (untuk pertumbuhan)
| Field | Tipe | Keterangan |
|-------|------|------------|
| `prev_total_revenue` | number | Pendapatan tahun sebelumnya |
| `prev_net_income` | number | Laba bersih tahun sebelumnya |
| `prev_total_assets` | number | Total aset tahun sebelumnya |
| `prev_total_equity` | number | Total ekuitas tahun sebelumnya |
| `prev_cfo` | number | Arus kas operasi tahun sebelumnya |

### Metadata
| Field | Tipe | Keterangan |
|-------|------|------------|
| `industry_group` | string | Sektor industri (lihat `/api/meta`) |
| `year` | number | Tahun laporan |
| `ipo_year` | number | Tahun IPO |
| `year_established` | number | Tahun didirikan |
| `parent_percent_owned` | number | Kepemilikan induk (%) |
| `pct_owned_all_institutions` | number | Kepemilikan institusi (%) |
| `pct_owned_insiders` | number | Kepemilikan insider (%) |

---

## 4. Field Response

| Field | Tipe | Keterangan |
|-------|------|------------|
| `indicator` | string | Indikator yang diprediksi |
| `indicator_label` | string | Nama indikator yang mudah dibaca |
| `distress_2y` | boolean | `true` bila diprediksi berisiko distress dalam 2 tahun |
| `probability` | number | Probabilitas mentah kelas distress (0–1) |
| `threshold` | number | Batas keputusan indikator (hasil tuning recall) |
| `risk_ratio` | number | `probability / threshold`. Nilai `1.0` berarti tepat di batas; `>1` berarti telah melewati batas |
| `risk_level` | string | `Relatif sehat`, `Perlu diwaspadai`, atau `Berisiko mengalami financial distress` |
| `commentary` | array | Daftar catatan rasio di luar rentang sehat |
| `input_warnings` | array | Peringatan konsistensi akuntansi pada input (bila ada) |
| `model_name` | string | Algoritma model indikator ini |

Setiap elemen `commentary` berisi: `ratio`, `label`, `value`, `healthy_range`,
`shap_rank`, `severity` (`ringan`/`sedang`/`tinggi`), `message`, dan `suggestion`.

**Interpretasi `risk_ratio`:** nilai ini menunjukkan seberapa dekat probabilitas perusahaan
terhadap batas keputusan, bukan probabilitas distress secara langsung. Misalnya `risk_ratio`
`0.5` berarti probabilitas perusahaan berada di setengah jalan menuju batas. Karena batas
ditetapkan dengan memprioritaskan recall, perusahaan yang mencapai `risk_ratio` `1.0` ke atas
ditandai berisiko distress.

---

## 5. Contoh Pemanggilan

### cURL

```bash
curl -X POST https://fdp.daffa.me/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "indicator": "ppk",
    "industry_group": "Food, Beverage and Tobacco",
    "year": 2023,
    "total_assets": 28846243,
    "total_liabilities": 6280237,
    "total_equity": 22566006,
    "total_revenue": 20745473,
    "net_income": 1088170,
    "prev_total_revenue": 21828591,
    "prev_net_income": 1792050
  }'
```

### Python

```python
import requests

payload = {
    "indicator": "ppk",
    "industry_group": "Food, Beverage and Tobacco",
    "year": 2023,
    "total_assets": 28846243,
    "total_liabilities": 6280237,
    "total_equity": 22566006,
    "total_revenue": 20745473,
    "net_income": 1088170,
    "prev_total_revenue": 21828591,
    "prev_net_income": 1792050,
}
res = requests.post("https://fdp.daffa.me/api/predict", json=payload)
data = res.json()
print(data["distress_2y"], data["risk_ratio"], data["risk_level"])
```

### JavaScript (fetch)

```javascript
const res = await fetch("https://fdp.daffa.me/api/predict", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    indicator: "ppk",
    industry_group: "Food, Beverage and Tobacco",
    year: 2023,
    total_assets: 28846243,
    total_liabilities: 6280237,
    total_equity: 22566006,
    total_revenue: 20745473,
    net_income: 1088170,
    prev_total_revenue: 21828591,
    prev_net_income: 1792050,
  }),
});
const data = await res.json();
console.log(data.distress_2y, data.risk_ratio, data.risk_level);
```

### Contoh response

```json
{
  "indicator": "ppk",
  "indicator_label": "Masuk Papan Pemantauan Khusus (BEI)",
  "distress_2y": false,
  "probability": 0.011489,
  "threshold": 0.102608,
  "risk_ratio": 0.112,
  "risk_level": "Relatif sehat",
  "commentary": [],
  "input_warnings": [],
  "model_name": "RandomForest"
}
```

---

## 6. Kode Status & Error

| Status | Arti |
|--------|------|
| `200 OK` | Prediksi berhasil |
| `400 Bad Request` | Nilai `indicator` tidak dikenal |
| `422 Unprocessable Entity` | Format body tidak valid (mis. tipe field salah) |

Contoh error indikator tidak dikenal:

```json
{ "detail": "Indikator 'xxx' tidak dikenal" }
```

---

## 7. Catatan Penggunaan

- Output API diposisikan sebagai alat bantu decision support, bukan pengganti analisis.
  fundamental dan audit keuangan secara menyeluruh.
- API tidak memerlukan access key/token.
