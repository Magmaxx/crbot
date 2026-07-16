- [x] 1) Refresh toggle için gerçek durdur/başlat davranışını dashboard akışında düzelt
- [x] 2) Dashboard UI için thorough test turu yap (coin/timeframe/risk/trade_mode kombinasyonları ve manuel güncelle)
- [x] 3) Test bulgularına göre gerekli düzeltmeleri uygula
- [x] 4) Son doğrulama özeti ile görevi kapat

## Yeni Faz (Operasyonel Sertleştirme)
- [x] 5) Timestamp’li tam proje backup scripti ekle (`scripts/backup_project.ps1`)
- [x] 6) RUNBOOK’a backup + restore prosedürü ekle
- [x] 7) Canlı trade öncesi güvenlik checklist’ini RUNBOOK’a ekle (kill-switch, hard stop, API yetki denetimi, rota)
- [x] 8) Son doğrulama özeti + kullanım komutları ile kapat

## Yeni Faz-2 (Ops Otomasyon)
- [ ] 9) `backup_project.ps1` için opsiyonel zip arşivleme (`-Zip`) ve klasör saklama kontrolü (`-KeepFolder`) ekle
- [ ] 10) `scripts/restore_project.ps1` oluştur (klasör/zip kaynaktan restore + güvenlik kontrolleri)
- [ ] 11) `scripts/preflight_check.ps1` oluştur (RUNBOOK checklist otomatik doğrulama)
- [ ] 12) RUNBOOK.md’yi yeni script komutları ve örnek akışla güncelle
- [ ] 13) Komut bazlı smoke testleri çalıştır ve sonuçları doğrula
- [ ] 14) Final doğrulama özeti yayınla
