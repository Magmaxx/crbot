# Trading Bot Production Runbook

## 1) Amaç
Bu runbook, OOP mimarili trading bot + Streamlit dashboard sistemini güvenli şekilde çalıştırmak, izlemek ve gerektiğinde geri almak için operasyon adımlarını içerir.

## 2) Ön Koşullar
- Python 3.13+
- Windows PowerShell / CMD
- Ağ erişimi (Binance + News API)
- Proje dizini: `c:/Users/mrtas/Desktop/telegram_bot`

## 3) Kurulum
```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Eğer `requirements.txt` güncel değilse, şu paketler kritik:
- streamlit, plotly
- pandas, numpy
- scikit-learn, xgboost, pandas-ta
- ccxt, requests

## 4) Konfigürasyon
`.env.example` dosyasını `.env` olarak kopyalayın ve alanları doldurun:

- `NEWS_API_KEY`
- `SYMBOL`, `TIMEFRAME`
- `DEFAULT_RISK_PROFILE`: `low|balanced|aggressive`
- `DEFAULT_TRADE_MODE`: `SCALP_SPOT|LEVERAGED_FUTURES`
- `STRICT_TESTNET=1` (önerilir)
- `MAX_NOTIONAL_PCT` ve `CONFIDENCE_THRESHOLD`
- `EXECUTION_ENABLED=0|1`
- `PAPER_ONLY=0|1`
- `USE_TESTNET=0|1`
- `BINANCE_API_KEY`, `BINANCE_API_SECRET`
- `ORDER_SIZE_PCT` (örn: `0.01` = bakiyenin %1’i)

## 5) Çalıştırma

### Dashboard (CLI)
```powershell
.\.venv\Scripts\python -m streamlit run src/gui/dashboard.py --server.port 8501
```

### Dashboard (Desktop Launcher / Program Penceresi)
Tek tık başlatma için:
```powershell
.\launcher\start_dashboard.bat
```

Opsiyonel port parametresi:
```powershell
.\launcher\start_dashboard.bat -Port 8502
```

Launcher log dosyası:
- `logs/launcher.log`

### Orchestrator (backend loop)
`bot.py` veya `src/app/main.py` entegre giriş noktasından başlatılır.

### İşlem Modu Kullanımı
Dashboard sol menüde **İşlem Modu** seçeneği bulunur:
- `SCALP_SPOT`: spot ağırlıklı kısa periyot yaklaşımı
- `LEVERAGED_FUTURES`: kaldıraçlı futures yaklaşımı

Seçilen mod:
- TradingEngine snapshot metriklerinde görünür
- İşlem geçmişi kayıtlarına `trade_mode` alanı olarak yazılır
- Orchestrator loglarında `mode=...` ile izlenir

## 6) Güvenlik Modu ve Geçiş Stratejisi
Varsayılan davranış güvenlidir:

1. `EXECUTION_ENABLED=0`  
   - Emir gönderimi tamamen kapalı (kill-switch).

2. `EXECUTION_ENABLED=1` ve `PAPER_ONLY=1`  
   - Sistem yalnızca paper/simülasyon akışında çalışır.

3. `EXECUTION_ENABLED=1`, `PAPER_ONLY=0`, `USE_TESTNET=1`  
   - Binance Testnet’e gerçek API çağrısı ile düşük boyutlu emir gönderimi (önerilen ara aşama).

4. `EXECUTION_ENABLED=1`, `PAPER_ONLY=0`, `USE_TESTNET=0`  
   - Gerçek live market emirleri (yalnızca testnet doğrulamasından sonra).

Önerilen güvenli geçiş:
- Aşama-1: 24 saat paper gözlem
- Aşama-2: testnet canlı emir (küçük `ORDER_SIZE_PCT`, düşük risk profili)
- Aşama-3: canlı markette kademeli sermaye artışı

Ek güvenlik önerileri:
- API key yetkilerini minimum tut
- IP whitelist uygula
- `low` risk profili ile başla
- `ORDER_SIZE_PCT`, `MAX_NOTIONAL_PCT`, daily loss limitlerini düşük tut

## 7) İzleme ve Loglama
- Logging setup: `src/utils/logging_setup.py`
- Konsol + dosya logları aktif
- İzlenecek metrikler:
  - model direction/probability
  - open/closed position sayısı
  - equity/balance değişimi
  - API hata/fallback mesajları

## 8) Sağlık Kontrolleri
- Dashboard erişimi: `http://localhost:8501`
- Pytest:
```powershell
.\.venv\Scripts\python -m pytest -q
```
- Beklenen: testlerin başarıyla geçmesi

### 8.1 Dashboard Refresh / Performans Doğrulama
Aşağıdaki akışlar birlikte doğrulanmalıdır:

1. **Auto Refresh ON**
   - 2-3 dakika izleyin.
   - Grafikler/sentiment/prediction paneli düzenli güncellenmeli.

2. **Auto Refresh OFF**
   - Polling durmalı.
   - Son başarılı veri ekranda kalmalı (blank olmamalı).

3. **Manuel Refresh**
   - `Veriyi Güncelle` ile tek seferlik güncelleme alınmalı.

4. **Kontrol Değişimi Tetikleme**
   - Coin / Timeframe / Risk Profile / İşlem Modu değişiminde yeni fetch-render döngüsü tetiklenmeli.

5. **Performans (cache/hash)**
   - Aynı veri imzasında model her tur yeniden train/predict etmemeli.
   - Veri değiştiğinde train/predict tekrar tetiklenmeli.

### 8.2 Trade History Filtre + CSV Export Doğrulama
1. Event / Side / Trade Mode filtrelerini ayrı ayrı ve kombinasyonlu test edin.
2. Start Date / End Date filtrelerini test edin:
   - Start = End
   - Start > End
3. Filtreli tabloda görülen satır sayısı ile indirilen CSV satır sayısı tutarlı olmalı.
4. Boş sonuç kümesinde CSV indirme butonu çalışmaya devam etmeli.

### 8.3 Risk Paneli Doğrulama
Risk panelinde şu alanları doğrulayın:
- `Risk/Trade`
- `Daily Max Loss`
- `Daily Loss Usage`
- `Open Capacity`
- Günlük kayıp limiti progress bar
- Status tablosu alanları:
  - `risk_profile`
  - `trade_mode`
  - `trading_enabled`
  - `execution_enabled`
  - `paper_only`
  - `use_testnet`

Risk profili değişiminde metriklerin güncellendiğini doğrulayın (`low/balanced/aggressive`).

## 9) Incident Response
- API hata artışı: yeniden deneme + fallback doğrula
- Anormal trade açma: trading engine risk limitlerini sıkılaştır
- Model sapması: tahmin katmanını fallback mode’a çek (sklearn veya HOLD ağırlıklı)

## 10) EXE Paketleme (Opsiyonel)

PyInstaller ile tek dosya executable üretimi:

```powershell
.\.venv\Scripts\python -m pip install pyinstaller
.\.venv\Scripts\pyinstaller --onefile --name trading-dashboard-launcher launcher/start_dashboard.bat
```

Not:
- BAT dosyası wrapper olduğu için pratikte PowerShell script tabanlı paketleme tercih edilir.
- Alternatif olarak doğrudan `launcher/start_dashboard.ps1` çağıran küçük bir Python launcher yazıp onu paketlemek daha sağlıklı olur.

## 11) Testnet Smoke Kontrolü
Aşağıdaki kombinasyonlarla log/snapshot doğrulayın:

- `EXECUTION_ENABLED=0` => snapshot/log içinde execution disabled
- `EXECUTION_ENABLED=1`, `PAPER_ONLY=1` => execution mode `paper`
- `EXECUTION_ENABLED=1`, `PAPER_ONLY=0`, `USE_TESTNET=1` => execution mode `live` (testnet)

Beklenen gözlemler:
- Dashboard/Orchestrator loglarında:
  - `mode=SCALP_SPOT|LEVERAGED_FUTURES`
  - `exec_enabled=... paper_only=... testnet=...`
- Trade history satırlarında:
  - `execution_mode`
  - `execution_ok`

## 12) Backup ve Restore Prosedürü

### 12.1 Tam Proje Backup (Timestamp'li)
Önerilen komut:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup_project.ps1
```

Opsiyonel parametreler:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\backup_project.ps1 -ProjectRoot "telegram_bot" -BackupRoot "telegram_bot\backups"
```

Beklenen çıktı:
- `Backup created: telegram_bot\backups\project_backup_YYYYMMDD_HHMMSS`

### 12.2 Restore (Geri Yükleme)
1. Streamlit/bot süreçlerini durdurun.
2. Geri dönmek istediğiniz backup klasörünü seçin:
   - `telegram_bot\backups\project_backup_YYYYMMDD_HHMMSS`
3. Projeyi geri yükleyin (mevcut dosyaları ezerek):
```powershell
robocopy "telegram_bot\backups\project_backup_YYYYMMDD_HHMMSS" "telegram_bot" /E /R:1 /W:1
```
4. Sanity check:
```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m streamlit run src/gui/dashboard.py --server.port 8501
```

### 12.3 Restore Sonrası Doğrulama
- Dashboard açılıyor mu?
- Reset Paper State çalışıyor mu?
- Trade history filtre/CSV ve risk paneli beklendiği gibi mi?
- Loglarda kritik hata var mı?

## 13) Canlı Trade Öncesi Güvenlik Checklist'i (Zorunlu)

### 13.1 Kill-Switch ve Emir Kontrolü
- [ ] `EXECUTION_ENABLED=0` acil kapatma davranışı doğrulandı
- [ ] UI/konfig üzerinden execution kapatıldığında yeni emir açılmıyor
- [ ] Canlıda açmadan önce son 24 saat paper akışı hatasız

### 13.2 Hard Risk Limits
- [ ] `daily_max_loss` limit aşımında trading disable doğrulandı
- [ ] `max_positions` limiti zorlandığında yeni pozisyon engelleniyor
- [ ] `ORDER_SIZE_PCT` ve `MAX_NOTIONAL_PCT` konservatif seviyede
- [ ] İlk canlı geçişte `low` risk profile kullanılıyor

### 13.3 API Güvenliği
- [ ] API key yalnızca gerekli izinlerle üretildi (trade + read, withdraw kapalı)
- [ ] IP whitelist aktif
- [ ] Testnet ve live key’ler ayrıştırıldı
- [ ] Anahtarlar `.env` dışında loglanmıyor

### 13.4 Operasyonel Güvenlik
- [ ] Backup + restore adımları dry-run edildi
- [ ] Incident response adımları ekipçe biliniyor
- [ ] Launcher ve uygulama logları düzenli rotasyona alındı
- [ ] Tek tık rollback komutu/runbook adımı doğrulandı

### 13.5 Canlıya Geçiş Rotası
- [ ] Aşama-1: Paper (24 saat)
- [ ] Aşama-2: Testnet live emir (küçük boyut)
- [ ] Aşama-3: Live market (kademeli sermaye)

## 14) Release Checklist
- [ ] `.env` doğrulandı
- [ ] Paper mode doğrulandı
- [ ] Risk profilleri test edildi
- [ ] Dashboard smoke test tamam
- [ ] Dashboard refresh ON/OFF + manuel + kontrol değişimi test edildi
- [ ] Dashboard performans (cache/hash) davranışı doğrulandı
- [ ] Trade history filtre + CSV export senaryoları doğrulandı
- [ ] Risk paneli metrik/progress/status doğrulandı
- [ ] Pytest geçti
- [ ] Launcher smoke test tamam (`start_dashboard.bat`)
- [ ] Launcher log yazımı doğrulandı (`logs/launcher.log`)
- [ ] Backup script çalıştı (`scripts/backup_project.ps1`)
- [ ] Restore adımı dry-run tamamlandı
- [ ] Canlı trade öncesi güvenlik checklist’i tamamlandı
- [ ] Geri alma planı hazır (`ROLLBACK.md`)
