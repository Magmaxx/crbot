# Changelog

## [v0.2.0] - 2026-07-16

### Added
- `scripts/restore_project.ps1`
  - Klasör veya `.zip` kaynaktan proje restore akışı.
  - Güvenlik odaklı korumalar ve `-NoConfirm` desteği.
  - Dry-run için `-WhatIf` desteği.
- `scripts/preflight_check.ps1`
  - `.env` kritik anahtar doğrulamaları.
  - `DEFAULT_RISK_PROFILE` değer doğrulaması (`low|balanced|aggressive`).
  - Sayısal aralık kontrolleri:
    - `ORDER_SIZE_PCT` in `(0,1]`
    - `MAX_NOTIONAL_PCT` in `(0,1]`
  - `BINANCE_API_KEY` / `BINANCE_API_SECRET` için WARN tabanlı görünürlük.
- `pytest.ini`
  - Test collection sertleştirmesi:
    - `norecursedirs = backups .venv .git __pycache__ .pytest_cache`
    - `addopts = -q`

### Changed
- `scripts/backup_project.ps1`
  - `-WhatIf` dry-run davranışı eklendi.
  - `-Zip` ve `-KeepFolder` ile birlikte senaryo bazlı çıktı ve akış iyileştirildi.
- `RUNBOOK.md`
  - Backup/restore prosedürleri güncellendi.
  - WhatIf kullanım örnekleri netleştirildi.
  - Preflight beklentileri ve release checklist revize edildi.
- `TODO.md`
  - Ops Automation Phase-2 maddeleri tamamlandı ve işaretlendi.
- `src/gui/dashboard.py`
  - Trade history zaman penceresi hesaplarında `pd.Timestamp.utcnow()` kullanımı kaldırıldı.
  - Pandas deprecation uyumu için `pd.Timestamp.now("UTC")` kullanımı standartlaştırıldı.

### Fixed
- Pytest collection çakışması:
  - `backups/` altındaki dosyaların test discovery’ye girmesi engellendi.
- Komut/shell farklılıklarından doğan test akışı sorunlarına karşı doğrulama komutları netleştirildi.

### Testing
- Web UI manuel thorough:
  - Auto Refresh ON/OFF
  - Manuel refresh
  - Coin / timeframe / risk / trade mode kombinasyonları
  - Trade history filtre + CSV export
- Backend:
  - `python -m pytest -q` PASS
- Ops:
  - `scripts/preflight_check.ps1` => `PREFLIGHT_STATUS=OK`
  - `scripts/backup_project.ps1` => WhatIf + real akışlar PASS
  - `scripts/restore_project.ps1` => WhatIf + real akışlar PASS
- Launcher:
  - `launcher/start_dashboard.bat` smoke PASS
  - `logs/launcher.log` kayıt üretimi PASS
- Curl smoke:
  - `http://localhost:8510/` => HTTP 200 PASS
  - `http://127.0.0.1:8501/` => HTTP 200 PASS
