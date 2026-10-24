# ilan-tarayici

Haftalık mimar ilan taraması (GitHub Actions). Bilgisayarın açık olmasına gerek yok.

- **İş ilanları:** LinkedIn (giriş yapmadan, son 7 gün) + kariyer.net + Arkitera — Ankara + İzmir.
- **Akademik:** ilan.gov.tr Kamu-Akademik Personel — mimarlık bölümü geçen arş. gör. ilanları.

**Ne zaman çalışır:** Her pazartesi 10:17. Elle başlatmak için: GitHub uygulaması → bu repo → Actions → *Ilan taramasi* → **Run workflow**.

**Sonuçlar:** Google Drive → *İlan Taramaları* klasörü (`00 SON - ...xlsx` her zaman en güncel liste). Repoda da `sonuclar/` klasöründe kopyası durur. Yeni ilanlar sarı.

**Drive bağlantısı:** `drive_posta_kutusu.gs` (Google Apps Script) + Secrets `DRIVE_WEBHOOK`, `DRIVE_ANAHTAR`.

**Bildirim:** Telefonda ntfy uygulaması; konu adı repo Secrets'ında (`NTFY_KONU`).

Bir kaynak "0 ilan" ya da uyarı veriyorsa: Actions'taki çalıştırma kaydını ve `sonuclar/debug/` klasörünü Claude'a göster.
