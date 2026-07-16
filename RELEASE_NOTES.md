# Release Notes — Ops Automation Phase-2

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
