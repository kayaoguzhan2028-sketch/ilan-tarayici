# -*- coding: utf-8 -*-
"""
LinkedIn mimar iş ilanı tarayıcı — Ankara + İzmir, son 7 gün

ÖNEMLİ: Giriş YAPMADAN, LinkedIn'in herkese açık iş arama sayfasını okur.
Hesabın hiçbir şekilde kullanılmaz, o yüzden profilin risk altında değildir.
LinkedIn bir gün "giriş yap" duvarı gösterirse script bunu raporda yazar.

Sonuç: bu klasörde rapor_linkedin_YYYY-MM-DD.html (otomatik açılır).
"""
import re, json, time, html, datetime, webbrowser
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright
import ortak

# ---------------- AYARLAR ----------------
GORUNUR = False
BEKLEME = 3.0                    # istekler arası bekleme (saniye)
SAYFA = 3                        # arama başına kaç sayfa (25'er ilan)
ANAHTARLAR = ["mimar", "architect"]
KONUMLAR = ["Ankara, Türkiye", "İzmir, Türkiye"]
SURE = "r604800"                 # r86400 = son 24 saat, r604800 = son 7 gün
# -----------------------------------------

KLASOR = ortak.CIKTI
GORULEN = KLASOR / "gorulen_linkedin.json"


def norm(s):
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


# Yazılım/bilişim "mimar"larını ele
RE_IT = re.compile(r"yazılım|software|solution|çözüm|cloud|bulut|data|veri|sistem|system|enterprise|kurumsal mimar"
                   r"|\bit\b|network|devops|security|güvenlik|database|platform|salesforce|sap|integration|entegrasyon")
RE_UNVAN = re.compile(r"mimar|architect|\bbim\b|restorasyon")
RE_YER = re.compile(r"ankara|izmir|çankaya|yenimahalle|keçiören|etimesgut|sincan|altındağ|mamak|gölbaşı|pursaklar"
                    r"|polatlı|kahramankazan|bornova|karşıyaka|konak|buca|çiğli|bayraklı|gaziemir|karabağlar"
                    r"|menemen|torbalı|urla|çeşme|foça|narlıdere|balçova|kemalpaşa|aliağa|menderes|seferihisar|güzelbahçe")
RE_DUVAR = re.compile(r"authwall|sign in|oturum aç|giriş yap")


def url(anahtar, konum, start):
    return ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            f"?keywords={quote(anahtar)}&location={quote(konum)}&f_TPR={SURE}&start={start}")


def main():
    ilanlar, uyarilar = {}, []
    with sync_playwright() as p:
        tarayici = p.chromium.launch(headless=not GORUNUR)
        page = tarayici.new_context(locale="tr-TR").new_page()
        for anahtar in ANAHTARLAR:
            for konum in KONUMLAR:
                for s in range(SAYFA):
                    try:
                        page.goto(url(anahtar, konum, s * 25), wait_until="domcontentloaded", timeout=30000)
                    except Exception as e:
                        uyarilar.append(f"{anahtar}/{konum} sayfa {s+1}: açılamadı ({type(e).__name__})")
                        break
                    kartlar = page.query_selector_all("li")
                    if not kartlar:
                        if RE_DUVAR.search(norm(page.content()[:5000])):
                            uyarilar.append("LinkedIn giriş duvarı gösterdi — bu hafta e-posta alarmına bak.")
                        break
                    for k in kartlar:
                        a = k.query_selector("a.base-card__full-link, a[href*='/jobs/view/']")
                        if not a:
                            continue
                        link = (a.get_attribute("href") or "").split("?")[0]
                        m = re.search(r"(\d{8,})", link)
                        if not m:
                            continue
                        # aynı ilan tr.linkedin.com / www.linkedin.com gibi farklı adreslerle gelebilir:
                        # anahtar = ilan numarası, link = tek tip adres
                        link = f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
                        def t(sel):
                            e = k.query_selector(sel)
                            return e.inner_text().strip() if e else ""
                        baslik = t("h3")
                        firma = t("h4")
                        yer = t(".job-search-card__location")
                        zaman_el = k.query_selector("time")
                        tarih = zaman_el.get_attribute("datetime") if zaman_el else ""
                        if not link or link in ilanlar:
                            continue
                        nb, ny = norm(baslik), norm(yer)
                        it = bool(RE_IT.search(nb))
                        kapsam_disi = (not RE_UNVAN.search(nb)) or (not RE_YER.search(ny))
                        ilanlar[link] = {"baslik": baslik, "firma": firma, "yer": yer,
                                         "tarih": tarih, "link": link, "it": it or kapsam_disi}
                    print(f"→ {anahtar} / {konum} / sayfa {s+1}: toplam {len(ilanlar)} ilan")
                    time.sleep(BEKLEME)
        tarayici.close()

    eski = set(json.loads(GORULEN.read_text(encoding="utf-8"))) if GORULEN.exists() else set()
    for i in ilanlar.values():
        i["yeni"] = i["link"] not in eski
    GORULEN.write_text(json.dumps(sorted(eski | set(ilanlar)), ensure_ascii=False, indent=1), encoding="utf-8")

    bina = [i for i in ilanlar.values() if not i["it"]]
    elenen = [i for i in ilanlar.values() if i["it"]]
    bina.sort(key=lambda x: (not x["yeni"], x["tarih"]), reverse=False)

    def satir(i):
        return (f"<tr class='{'yeni' if i['yeni'] else ''}'><td>{'YENİ' if i['yeni'] else ''}</td>"
                f"<td><a href='{html.escape(i['link'])}' target='_blank'>{html.escape(i['baslik'])}</a></td>"
                f"<td>{html.escape(i['firma'])}</td><td>{html.escape(i['yer'])}</td>"
                f"<td>{html.escape(i['tarih'] or '—')}</td></tr>")

    bugun = datetime.date.today().isoformat()
    sayfa = f"""<!doctype html><meta charset="utf-8"><title>LinkedIn mimar ilanları {bugun}</title>
<style>body{{font-family:Segoe UI,Arial;margin:24px;color:#222}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ddd;padding:6px;text-align:left}}tr.yeni{{background:#fff6d6}}th{{background:#f2f2f2}}
details{{margin-top:20px}}</style>
<h2>LinkedIn mimar ilanları — Ankara + İzmir, son 7 gün — {bugun}</h2>
<p>{len(bina)} ilan ({sum(i['yeni'] for i in bina)} yeni). Yazılım/bilişim "mimar" ilanları ayrıca listelendi.</p>
{''.join(f'<p>⚠ {html.escape(u)}</p>' for u in uyarilar)}
<table><tr><th></th><th>Pozisyon</th><th>Firma</th><th>Konum</th><th>Tarih</th></tr>{''.join(map(satir, bina))}</table>
<details><summary>Elenenler: yazılım/bilişim, Ankara-İzmir dışı ya da başlığında "mimar" geçmeyenler ({len(elenen)}) — yanlış elenen var mı kontrol et</summary>
<table>{''.join(map(satir, elenen))}</table></details>"""
    yol = KLASOR / f"rapor_linkedin_{bugun}.html"
    yol.write_text(sayfa, encoding="utf-8")
    # Excel (yerel + Google Drive) ve telefona bildirim
    yeni = [i for i in bina if i["yeni"]]
    excel = ortak.excel_kaydet(
        f"linkedin_{bugun}.xlsx", ["Yeni", "Pozisyon", "Firma", "Konum", "Tarih", "Link"],
        [["YENİ" if i["yeni"] else "", i["baslik"], i["firma"], i["yer"], i["tarih"], i["link"]] for i in bina],
        link_sutunu=5, yeni_sutunu=0, son_adi="00 SON - LinkedIn.xlsx")
    if yeni:
        ozet = "\n".join(f"• {i['baslik']} — {i['firma']} ({i['yer'].split(',')[0]})" for i in yeni[:8])
        ortak.bildir(f"LinkedIn: {len(yeni)} yeni mimar ilani", ozet + "\n\nExcel: " + ortak.EXCEL_YERI)
    elif uyarilar:
        ortak.bildir("LinkedIn taramasi: sorun var", "\n".join(uyarilar[:3]), oncelik="low")
    print(f"\n{len(bina)} ilan ({len(yeni)} yeni, {len(elenen)} yazılım ilanı elendi). Rapor: {yol}")
    for e in excel:
        print("Excel:", e)
    for u in uyarilar:
        print("⚠", u)
    if not ortak.ACTIONS:
        webbrowser.open(yol.as_uri())


if __name__ == "__main__":
    main()
