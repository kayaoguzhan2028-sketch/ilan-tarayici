# -*- coding: utf-8 -*-
"""
Mimar iş ilanı tarayıcı — LinkedIn + kariyer.net + Arkitera, Ankara + İzmir

LinkedIn: giriş YAPMADAN herkese açık arama sayfası (hesabın kullanılmaz), son 7 gün.
kariyer.net: "mimar" araması, ilk birkaç sayfa.
Arkitera: kariyer ilanları sayfası.
Yazılım/bilişim "mimar" ilanları ve Ankara-İzmir dışı ilanlar ayrı listede gösterilir (silinmez).

Sonuç: rapor_is_YYYY-MM-DD.html (otomatik açılır) + Excel (phyton scriptim / Google Drive).
"""
import re, json, time, html, datetime, webbrowser
from urllib.parse import quote

from playwright.sync_api import sync_playwright
import ortak

# ---------------- AYARLAR ----------------
GORUNUR = False
BEKLEME = 3.0                    # istekler arası bekleme (saniye)
LINKEDIN_SAYFA = 3               # arama başına kaç sayfa (25'er ilan)
LINKEDIN_ANAHTAR = ["mimar", "architect"]
LINKEDIN_KONUM = ["Ankara, Türkiye", "İzmir, Türkiye"]
LINKEDIN_SURE = "r604800"        # r86400 = son 24 saat, r604800 = son 7 gün
KARIYER_SAYFA = 5                # kariyer.net'te kaç sayfa (mimar, mimar-2 ...)
ARKITERA_MAX_DETAY = 40          # şehri listede yazmayan Arkitera ilanlarından en fazla kaçı açılsın
# -----------------------------------------

KLASOR = ortak.CIKTI
GORULEN = KLASOR / "gorulen_isilani.json"
GORULEN_ESKI = KLASOR / "gorulen_linkedin.json"


def norm(s):
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


RE_IT = re.compile(r"yazılım|software|solution|çözüm|cloud|bulut|data|veri|sistem|system|enterprise|kurumsal mimar"
                   r"|\bit\b|network|devops|security|güvenlik|database|platform|salesforce|sap|integration|entegrasyon")
RE_UNVAN = re.compile(r"mimar|architect|\bbim\b|restorasyon")
RE_YER = re.compile(r"ankara|izmir|çankaya|yenimahalle|keçiören|etimesgut|sincan|altındağ|mamak|gölbaşı|pursaklar"
                    r"|polatlı|kahramankazan|bornova|karşıyaka|konak|buca|çiğli|bayraklı|gaziemir|karabağlar"
                    r"|menemen|torbalı|urla|çeşme|foça|narlıdere|balçova|kemalpaşa|aliağa|menderes|seferihisar|güzelbahçe")
RE_DUVAR = re.compile(r"authwall|sign in|oturum aç|giriş yap")
RE_ENGEL = re.compile(r"captcha|cloudflare|access denied|erişim engellendi|robot olmadığınızı|request blocked")

# Bir bağlantının etrafındaki "kart" metnini toplayan JS (site yapısından bağımsız)
JS_KARTLAR = """(desen) => {
  const re = new RegExp(desen), out = [];
  for (const a of document.querySelectorAll('a[href]')) {
    if (!re.test(a.href)) continue;
    let el = a, kart = a.innerText || '';
    for (let i = 0; i < 6 && el.parentElement; i++) {
      const ust = el.parentElement;
      // Başka bir ilan bağlantısı da içeriyorsa kartın dışına çıktık demektir
      const ilanSayisi = [...ust.querySelectorAll('a[href]')].filter(x => re.test(x.href) && x.href !== a.href).length;
      const t = ust.innerText || '';
      if (ilanSayisi > 0 || t.length > 700) break;
      el = ust; kart = t;
    }
    out.push([a.href, (a.innerText || a.title || '').trim(), kart.trim()]);
  }
  return out;
}"""


def yer_bul(metin):
    m = RE_YER.search(norm(metin))
    return m.group(0).title() if m else ""


def satirlar(metin):
    return [s.strip() for s in (metin or "").splitlines() if s.strip()]


def yukle(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except Exception:
        pass
    for _ in range(3):
        page.mouse.wheel(0, 4000)
        time.sleep(0.5)


# ---------------- LinkedIn ----------------
def linkedin(page, ilanlar, uyarilar):
    for anahtar in LINKEDIN_ANAHTAR:
        for konum in LINKEDIN_KONUM:
            for s in range(LINKEDIN_SAYFA):
                url = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
                       f"?keywords={quote(anahtar)}&location={quote(konum)}&f_TPR={LINKEDIN_SURE}&start={s * 25}")
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    uyarilar.append(f"LinkedIn {anahtar}/{konum} s.{s+1}: açılamadı ({str(e).splitlines()[0][:120]})")
                    break
                kartlar = page.query_selector_all("li")
                if not kartlar:
                    if RE_DUVAR.search(norm(page.content()[:5000])):
                        uyarilar.append("LinkedIn giriş duvarı gösterdi.")
                    break
                for k in kartlar:
                    a = k.query_selector("a.base-card__full-link, a[href*='/jobs/view/']")
                    if not a:
                        continue
                    m = re.search(r"(\d{8,})", (a.get_attribute("href") or "").split("?")[0])
                    if not m:
                        continue
                    link = f"https://www.linkedin.com/jobs/view/{m.group(1)}/"
                    if link in ilanlar:
                        continue
                    def t(sel):
                        e = k.query_selector(sel)
                        return e.inner_text().strip() if e else ""
                    z = k.query_selector("time")
                    ekle(ilanlar, "LinkedIn", t("h3"), t("h4"), t(".job-search-card__location"),
                         z.get_attribute("datetime") if z else "", link)
                print(f"→ LinkedIn {anahtar} / {konum} / s.{s+1}: toplam {len(ilanlar)}")
                time.sleep(BEKLEME)


# ---------------- kariyer.net ----------------
def kariyer(page, ilanlar, uyarilar):
    once = len(ilanlar)
    for s in range(1, KARIYER_SAYFA + 1):
        url = "https://www.kariyer.net/is-ilanlari/mimar" + ("" if s == 1 else f"-{s}")
        try:
            yukle(page, url)
        except Exception as e:
            uyarilar.append(f"kariyer.net s.{s}: açılamadı ({str(e).splitlines()[0][:120]})")
            break
        if RE_ENGEL.search(norm(page.inner_text("body")[:3000])):
            uyarilar.append(f"kariyer.net s.{s}: bot koruması (GORUNUR=True ile dene)")
            break
        kartlar = page.evaluate(JS_KARTLAR, r"kariyer\.net/is-ilani/.+-\d{5,}")
        if not kartlar:
            break
        for href, a_metin, kart in kartlar:
            link = href.split("?")[0]
            if link in ilanlar:
                continue
            sat = satirlar(kart)
            baslik = satirlar(a_metin)[0] if satirlar(a_metin) else (sat[0] if sat else "")
            firma = next((x for x in sat if x != baslik and not RE_YER.search(norm(x))), "")
            ekle(ilanlar, "kariyer.net", baslik, firma, yer_bul(kart), "", link)
        print(f"→ kariyer.net s.{s}: toplam {len(ilanlar)}")
        time.sleep(BEKLEME)
    if len(ilanlar) == once:
        uyarilar.append("kariyer.net'ten hiç ilan okunamadı — sayfa yapısı değişmiş ya da engellenmiş olabilir.")


# ---------------- Arkitera ----------------
def arkitera(page, ilanlar, uyarilar):
    once = len(ilanlar)
    try:
        yukle(page, "https://www.arkitera.com/kariyer/")
    except Exception as e:
        uyarilar.append(f"Arkitera açılamadı ({str(e).splitlines()[0][:120]})")
        return
    kartlar = page.evaluate(JS_KARTLAR, r"arkitera\.com/kariyer/[^/?#]+/?$")
    sehirsiz = []
    for href, a_metin, kart in kartlar:
        link = href.split("?")[0].split("#")[0]
        if link in ilanlar or re.search(r"/kariyer/(page|kategori|category|ilan-ver)", link):
            continue
        baslik = satirlar(a_metin)[0] if satirlar(a_metin) else (satirlar(kart) or [""])[0]
        if len(baslik) < 6:
            continue
        yer = yer_bul(kart)
        ekle(ilanlar, "Arkitera", baslik, "", yer, "", link, unvan_sart=False)
        if not yer:
            sehirsiz.append(link)
    # Listede şehri yazmayan ilanların sayfasını açıp şehri bul
    for link in sehirsiz[:ARKITERA_MAX_DETAY]:
        try:
            yukle(page, link)
            metin = page.inner_text("body")
            yer = yer_bul(metin)
            ilanlar[link]["yer"] = yer or "—"
            ilanlar[link]["elendi"] = ilanlar[link]["it"] or not yer
        except Exception:
            pass
        time.sleep(BEKLEME)
    print(f"→ Arkitera: {len(ilanlar) - once} ilan")
    if len(ilanlar) == once:
        uyarilar.append("Arkitera'dan hiç ilan okunamadı — sayfa yapısı değişmiş ya da engellenmiş olabilir.")


def ekle(ilanlar, kaynak, baslik, firma, yer, tarih, link, unvan_sart=True):
    nb = norm(baslik)
    it = bool(RE_IT.search(nb))
    unvan_yok = unvan_sart and not RE_UNVAN.search(nb)
    yer_yok = not RE_YER.search(norm(yer))
    ilanlar[link] = {"kaynak": kaynak, "baslik": baslik, "firma": firma, "yer": yer, "tarih": tarih,
                     "link": link, "it": it, "elendi": it or unvan_yok or yer_yok}


def main():
    ilanlar, uyarilar = {}, []
    with sync_playwright() as p:
        tarayici = p.chromium.launch(headless=not GORUNUR)
        page = tarayici.new_context(locale="tr-TR").new_page()
        for kaynak in (linkedin, kariyer, arkitera):
            try:
                kaynak(page, ilanlar, uyarilar)
            except Exception as e:
                uyarilar.append(f"{kaynak.__name__}: beklenmeyen hata ({str(e).splitlines()[0][:120]})")
        tarayici.close()

    eski = set()
    for f in (GORULEN, GORULEN_ESKI):
        if f.exists():
            eski |= set(json.loads(f.read_text(encoding="utf-8")))
    for i in ilanlar.values():
        i["yeni"] = i["link"] not in eski
    GORULEN.write_text(json.dumps(sorted(eski | set(ilanlar)), ensure_ascii=False, indent=1), encoding="utf-8")

    uygun = sorted([i for i in ilanlar.values() if not i["elendi"]], key=lambda x: (not x["yeni"], x["kaynak"]))
    elenen = [i for i in ilanlar.values() if i["elendi"]]
    yeni = [i for i in uygun if i["yeni"]]

    def satir(i):
        return (f"<tr class='{'yeni' if i['yeni'] else ''}'><td>{'YENİ' if i['yeni'] else ''}</td>"
                f"<td>{html.escape(i['kaynak'])}</td>"
                f"<td><a href='{html.escape(i['link'])}' target='_blank'>{html.escape(i['baslik'])}</a></td>"
                f"<td>{html.escape(i['firma'])}</td><td>{html.escape(i['yer'])}</td>"
                f"<td>{html.escape(i['tarih'] or '—')}</td></tr>")

    bugun = datetime.date.today().isoformat()
    sayilar = ", ".join(f"{k}: {sum(1 for i in uygun if i['kaynak'] == k)}" for k in ("LinkedIn", "kariyer.net", "Arkitera"))
    sayfa = f"""<!doctype html><meta charset="utf-8"><title>Mimar iş ilanları {bugun}</title>
<style>body{{font-family:Segoe UI,Arial;margin:24px;color:#222}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ddd;padding:6px;text-align:left}}tr.yeni{{background:#fff6d6}}th{{background:#f2f2f2}}
details{{margin-top:20px}}</style>
<h2>Mimar iş ilanları — Ankara + İzmir — {bugun}</h2>
<p>{len(uygun)} ilan ({len(yeni)} yeni) — {sayilar}</p>
{''.join(f'<p>⚠ {html.escape(u)}</p>' for u in uyarilar)}
<table><tr><th></th><th>Kaynak</th><th>Pozisyon</th><th>Firma</th><th>Konum</th><th>Tarih</th></tr>{''.join(map(satir, uygun))}</table>
<details><summary>Elenenler: yazılım/bilişim, Ankara-İzmir dışı ya da başlığında "mimar" geçmeyenler ({len(elenen)}) — yanlış elenen var mı kontrol et</summary>
<table>{''.join(map(satir, elenen))}</table></details>"""
    yol = KLASOR / f"rapor_is_{bugun}.html"
    yol.write_text(sayfa, encoding="utf-8")

    excel = ortak.excel_kaydet(
        f"is_ilanlari_{bugun}.xlsx", ["Yeni", "Kaynak", "Pozisyon", "Firma", "Konum", "Tarih", "Link"],
        [["YENİ" if i["yeni"] else "", i["kaynak"], i["baslik"], i["firma"], i["yer"], i["tarih"], i["link"]]
         for i in uygun], link_sutunu=6, yeni_sutunu=0, son_adi="00 SON - Is Ilanlari.xlsx")
    if yeni:
        ozet = "\n".join(f"• {i['baslik']} — {i['firma'] or i['kaynak']} ({i['yer']})" for i in yeni[:8])
        ortak.bildir(f"{len(yeni)} yeni mimar is ilani", ozet + "\n\nExcel: " + ortak.EXCEL_YERI)
    elif uyarilar:
        ortak.bildir("Is ilani taramasi: sorun var", "\n".join(uyarilar[:3]), oncelik="low")

    print(f"\n{len(uygun)} ilan ({len(yeni)} yeni) — {sayilar}. Elenen: {len(elenen)}. Rapor: {yol}")
    for e in excel:
        print("Excel:", e)
    for u in uyarilar:
        print("⚠", u)
    if not ortak.ACTIONS:
        webbrowser.open(yol.as_uri())


if __name__ == "__main__":
    main()
