# Release Notes — v0.2.1 (Draft)

## Official Release URL
- Draft aşamasında (yayınlanmadı)

## Özet
Bu sürüm, v0.2.0 sonrası operasyonel sürdürülebilirliği artırmak için otomasyon ve hijyen güncellemeleri içerir.  
Ana amaç: CI test-gate kurulumu, runtime artifact’lerin repodan dışlanması, dashboard smoke test otomasyonu ve incident-response playbook standardizasyonu.

## Kapsam

### 1) CI Pipeline (pytest + preflight)
- `/.github/workflows/ci.yml` eklendi.
- Windows tabanlı GitHub Actions job:
  - bağımlılık kurulumu
  - `scripts/preflight_check.ps1`
  - `python -m pytest -q`
- Amaç: PR/push aşamasında release öncesi teknik kapıların otomatik doğrulanması.

### 2) Repository Hijyen / .gitignore Hardening
- `/.gitignore` eklendi.
- Aşağıdaki runtime/developer artifact’leri ignore kapsamına alındı:
  - `logs/`, `*.log`
  - `__pycache__/`, `*.py[cod]`
  - `.pytest_cache/`, `.mypy_cache/`
  - `.venv/` ve benzeri local env klasörleri
  - lokal `.env` dosyaları

### 3) Streamlit Smoke Test Automation
- `test_dashboard_smoke.py` eklendi.
- Dashboard modül import + entrypoint (`run_dashboard`) erişilebilirlik smoke testi otomatikleştirildi.
- Amaç: temel dashboard entegrasyon kırılmalarını CI’da erken yakalamak.

### 4) RUNBOOK Incident-Response Playbook Upgrade
- `RUNBOOK.md` içindeki Incident Response bölümü genişletildi:
  - Severity modeli (SEV-1/2/3)
  - İlk 5 dakika triage checklist
  - Kill-switch (`EXECUTION_ENABLED=0`) zorunlu aksiyon akışı
  - Testnet fallback ve rollback karar kriterleri
  - Post-incident kapanış ve RCA beklentileri

## Test ve Doğrulama Sonuçları

### CI Tasarımı
- Preflight + Pytest birlikte zorunlu quality gate olarak tanımlandı.

### Önerilen Lokal Doğrulama
```powershell
cd telegram_bot
powershell -ExecutionPolicy Bypass -File .\scripts\preflight_check.ps1
.\.venv\Scripts\python -m pytest -q
```

## Bilinen Notlar
- Bu doküman draft sürümdür; resmi release URL yayınlandığında güncellenecektir.
- CI bağımlılık kurulumu `requirements.txt` mevcutluğuna göre fallback davranışı içerir.

## Rollback Referansı
- Rollback planı ve operasyon adımları: `ROLLBACK.md`
- Restore aracı: `scripts/restore_project.ps1`

---

# Release Notes — v0.2.0 (Ops Automation Phase-2)

## Official Release URL
- https://github.com/Magmaxx/crbot/releases/tag/v0.2.0

## Özet
Bu sürüm, operasyonel güvenilirlik ve geri alınabilirlik odaklı bir sertleştirme paketidir.  
Ana amaç: backup/restore, preflight doğrulama, launcher/doğrulama akışları ve runbook uyumunu production hazırlık seviyesine taşımak.

## Kapsam

### 1) Ops Script Sertleştirme
- `scripts/backup_project.ps1`
  - `-WhatIf` dry-run desteği
  - `-Zip` / `-KeepFolder` ile arşivleme ve klasör saklama senaryoları
- `scripts/restore_project.ps1`
  - Klasör/zip kaynaktan restore
  - `-WhatIf` dry-run desteği
  - Güvenli restore akışı ve onay mekanizmaları
- `scripts/preflight_check.ps1`
  - `.env` kritik anahtar kontrolleri
  - Risk profile doğrulaması
  - Yüzdesel parametre aralık doğrulaması:
    - `ORDER_SIZE_PCT` in `(0,1]`
    - `MAX_NOTIONAL_PCT` in `(0,1]`
  - API key/secret eksikliğinde WARN görünürlüğü

### 2) Test Altyapısı
- `pytest.ini` ile test collection kapsamı temizlendi:
  - `backups/` gibi dizinlerin test discovery’ye dahil olup false-positive üretmesi engellendi.

### 3) Dokümantasyon ve Operasyon Kapanışı
- `RUNBOOK.md` güncellendi:
  - backup/restore prosedürleri
  - WhatIf örnekleri
  - preflight beklentileri
  - release checklist tamamlandı
- `TODO.md` tüm Ops Automation Phase-2 maddeleri tamamlandı.
- `src/gui/dashboard.py` follow-up cleanup:
  - `pd.Timestamp.utcnow()` kaldırıldı
  - `pd.Timestamp.now("UTC")` ile deprecation uyumu sağlandı

## Test ve Doğrulama Sonuçları

### Web UI (thorough manuel)
- Auto Refresh ON/OFF
- Manuel refresh
- Coin/timeframe/risk/trade mode kombinasyonları
- Trade history filtre + CSV export  
**Sonuç:** PASS

### Backend
- `python -m pytest -q`  
**Sonuç:** PASS

### Ops Komutları
- `scripts/preflight_check.ps1` => `PREFLIGHT_STATUS=OK`
- `scripts/backup_project.ps1` => WhatIf + real akışlar PASS
- `scripts/restore_project.ps1` => WhatIf + real akışlar PASS

### Launcher ve Log
- `launcher/start_dashboard.bat` smoke PASS
- `logs/launcher.log` yeni kayıt üretimi PASS

### Ek HTTP Smoke
- `http://localhost:8510/` => HTTP 200 PASS
- `http://127.0.0.1:8501/` => HTTP 200 PASS

## Bilinen Notlar
- Ortamda `git` CLI yüklü olmadığı için branch/tag/commit otomasyonu bu aşamada uygulanmadı.
- Release package dokümantasyonu dosya bazlı hazırlandı.

## Rollback Referansı
- Rollback planı ve operasyon adımları: `ROLLBACK.md`
- Restore aracı: `scripts/restore_project.ps1`

## Önerilen Yayın Öncesi Son Komutlar
```powershell
cd telegram_bot
powershell -ExecutionPolicy Bypass -File .\scripts\preflight_check.ps1
.\.venv\Scripts\python -m pytest -q
powershell -ExecutionPolicy Bypass -File .\scripts\backup_project.ps1 -Zip -KeepFolder
