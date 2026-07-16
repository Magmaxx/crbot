# GUI Manual Test Checklist (CCXT + Binance Sentiment)

## Scope
Aşağıdaki akışlar `bot.py` masaüstü GUI için manuel doğrulanacaktır:
- Start/Stop
- Settings Apply
- Risk profile switch
- Logs panel
- Positions table
- Runtime behavior indicators

## Preconditions
- Python environment hazır
- Gerekli paketler kurulu (`ccxt/ccxt.pro`, `requests`, `tkinter` erişilebilir)
- İnternet bağlantısı açık
- Binance public endpoint erişimi var

## Test Cases

### 1) App Launch
- [ ] `python bot.py` ile uygulama açılır.
- [ ] Ana pencere render edilir (Dashboard/Settings/Positions/Logs sekmeleri görünür).
- [ ] Başlangıç durum metni "Hazır" benzeri görünür.

### 2) Start/Stop Engine
- [ ] Start butonuna basınca engine başlar, status "Çalışıyor" olur.
- [ ] Logs sekmesinde başlangıç logları görünür.
- [ ] Stop butonuna basınca engine durur, status "Durduruldu" olur.
- [ ] Tekrar Start sonrası yeniden çalışabilir (idempotent davranış).

### 3) Risk Profile Switch
- [ ] Risk dropdown'dan `low` seçildiğinde log/status güncellenir.
- [ ] `balanced` seçildiğinde güncellenir.
- [ ] `aggressive` seçildiğinde güncellenir.
- [ ] Engine çalışırken risk değişimi uygulamayı bozmaz.

### 4) Settings Apply
- [ ] Settings sekmesinde symbol/timeframe değiştirilir.
- [ ] "Apply Settings" sonrası log'a ayar uygulandı kaydı düşer.
- [ ] Engine çalışıyorsa kontrollü durdurup yeniden başlatma akışı doğru görünür.
- [ ] Yeni ayarlar status satırında görünür.

### 5) Dashboard Values
- [ ] Price kartı veri geldikçe güncellenir.
- [ ] Signal kartı (`LONG/SHORT/HOLD + confidence`) güncellenir.
- [ ] Balance kartı işlem kapanışlarına bağlı güncellenir.
- [ ] Open positions kartı açılan/kapatılan işlemlerle değişir.

### 6) Logs Panel
- [ ] Zaman damgalı log satırları sürekli akar.
- [ ] Hata/reconnect durumunda anlamlı log mesajı görünür.
- [ ] Uygulama kapanırken stop logları düzgün yazılır.

### 7) Positions Table
- [ ] Pozisyon açıldığında tabloya yeni satır eklenir.
- [ ] Pozisyon kapanınca status `CLOSED` ve PnL görünür.
- [ ] Saat/Yön/Entry/Exit/Qty/PnL kolonları doğru formatta.

### 8) Runtime Resilience (Short Manual)
- [ ] Ağ geçici kesintisinde uygulama donmaz.
- [ ] Reconnect sonrası akış devam eder (log’dan doğrulanır).
- [ ] Uygulama kapatma (window close) sonrası thread temiz kapanır.

## Result Summary Template
- Date:
- Tester:
- Pass:
- Fail:
- Notes:
