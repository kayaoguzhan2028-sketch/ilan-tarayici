# ilan-tarayici

Haftalık mimar ilan taraması (GitHub Actions). Bilgisayarın açık olmasına gerek yok.

- **LinkedIn:** Ankara + İzmir, "mimar" / "architect", son 7 gün (giriş yapmadan).
- **Araştırma görevlisi:** YÖK Akademik İlan + ilan.gov.tr, mimarlık geçen arş. gör. ilanları.

**Ne zaman çalışır:** Her pazartesi 10:17. Elle başlatmak için: GitHub uygulaması → bu repo → Actions → *Ilan taramasi* → **Run workflow**.

**Sonuçlar:** `sonuclar/` klasörü — `.xlsx` (telefonda açılır), `.html` rapor, `.csv`. Yeni ilanlar sarı.

**Bildirim:** Telefonda ntfy uygulaması; konu adı repo Secrets'ında (`NTFY_KONU`).

Bir kaynak "0 ilan" ya da uyarı veriyorsa: Actions'taki çalıştırma kaydını ve `sonuclar/debug/` klasörünü Claude'a göster.
