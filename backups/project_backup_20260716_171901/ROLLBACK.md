# Rollback & Yedek Prosedürü

## 1) Amaç
Canlıda sorun yaşandığında sistemi güvenli şekilde son stabil sürüme döndürmek.

## 2) Mevcut Yedekler
- `backups/main.py.bak` (orchestrator entegrasyonu öncesi yedek)

## 3) Hızlı Rollback (Kod)
PowerShell:
```powershell
Copy-Item backups/main.py.bak src/app/main.py -Force
```

## 4) Rollback Sonrası Kontrol
1. Syntax/test:
```powershell
.\.venv\Scripts\python -m pytest -q
```
2. Dashboard:
```powershell
.\.venv\Scripts\python -m streamlit run src/gui/dashboard.py --server.headless true --server.port 8501
```
3. Loglar:
- Hata seviyeleri ve stack trace kontrol edilir.

## 5) Konfigürasyon Rollback
- `.env` bozulduysa `.env.example` üzerinden yeniden oluştur.
- Risk profilini geçici olarak `low` yap.
- `STRICT_TESTNET=1` zorla.

## 6) Operasyonel Güvenlik Adımları
- Şüpheli durumda trading loop durdur.
- Paper mode dışında çalışıyorsa canlı emirleri devre dışı bırak.
- Açık pozisyon yönetimini manuel gözden geçir.

## 7) Postmortem
- Olay zamanı, kök neden, etki, aksiyonlar yazılır.
- Kalıcı düzeltme PR’ı açılmadan canlıya tekrar çıkılmaz.
