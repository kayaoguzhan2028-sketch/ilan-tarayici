# -*- coding: utf-8 -*-
"""
Mimarlık Araştırma Görevlisi ilan tarayıcı
Kaynaklar: YÖK Akademik İlan Sistemi + ilan.gov.tr (Akademik Personel)

Ne yapar:
  1. Kaynak sayfalarını açar, ilan bağlantılarını toplar.
  2. Her ilanı ve ekindeki PDF'leri okur.
  3. Metinde hem "mimar" hem "araştırma görevlisi" geçen ilanları raporlar.
Sonuç: bu klasörde rapor_arsgor_YYYY-MM-DD.html (otomatik açılır).
Haftada bir çalıştırmak yeterli. Siteyi yormamak için sayfalar arasında bekler.
"""
import re, io, json, time, html, datetime, webbrowser
from pathlib import Path

from playwright.sync_api import sync_playwright
import ortak

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# ---------------- AYARLAR ----------------
GORUNUR = False      # True: tarayıcı penceresi açık çalışır (site engellerse dene)
BEKLEME = 2.0        # sayfalar arası bekleme (saniye)
MAX_DETAY = 80       # kaynak başına açılacak en fazla ilan sayfası
MAX_PDF = 40         # kaynak başına okunacak en fazla PDF
SAYFA_LIMIT = 3      # liste sayfasında "sonraki" ile en fazla kaç sayfa ilerlensin

KAYNAKLAR = {
    "YÖK Akademik İlan": {
        "baslangic": ["https://ilan.yok.gov.tr/",
                      "https://www.ilan.yok.gov.tr/ilanlar/akademik"],
        "alan": "yok.gov.tr",
    },
    "ilan.gov.tr": {
        "baslangic": ["https://www.ilan.gov.tr/ilan/kategori/9/akademik-personel-alimlari"],
        "alan": "ilan.gov.tr",
    },
}
# -----------------------------------------

KLASOR = ortak.CIKTI
DEBUG = KLASOR / "debug"
GORULEN = KLASOR / "gorulen_arsgor.json"


def norm(s):
    return (s or "").replace("İ", "i").replace("I", "ı").lower()


RE_MIMAR = re.compile(r"mimar")
RE_ARSGOR = re.compile(r"ara[sş]t[ıi]rma\s+g[öo]revlisi|ar[sş]\.\s*g[öo]r")
RE_AKADEMIK = re.compile(r"üniversite|universite|öğretim|ogretim|araştırma|arastirma|akademik|fakülte|fakulte|kadro")
RE_HARIC = re.compile(r"giriş|iletişim|hakkında|kvkk|çerez|gizlilik|sss|yardım|mevzuat|duyurular$")
RE_ENGEL = re.compile(r"captcha|cloudflare|access denied|erişim engellendi|robot olmadığınızı|request blocked")
RE_SONRAKI = re.compile(r"^(sonraki|ileri|›|»|next)$")


def yukle(page, url):
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    for _ in range(5):
        page.mouse.wheel(0, 4000)
        time.sleep(0.6)


def linkler(page):
    return page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => [(e.innerText || e.title || '').trim(), e.href])")


def govde(page):
    try:
        return page.inner_text("body", timeout=10000)
    except Exception:
        return ""


def kesitler(metin, n=3):
    satirlar = [s.strip() for s in metin.splitlines() if s.strip()]
    out = []
    for i, s in enumerate(satirlar):
        if RE_MIMAR.search(norm(s)):
            out.append(" | ".join(satirlar[max(0, i - 1):i + 2])[:400])
            if len(out) >= n:
                break
    return out


def son_basvuru(metin):
    m = re.search(r"son\s*başvuru[^\n]{0,80}?(\d{1,2}[./]\d{1,2}[./]\d{4})", metin, re.I)
    return m.group(1) if m else ""


def pdf_metni(context, url):
    if not PdfReader:
        return ""
    r = context.request.get(url, timeout=45000)
    if not r.ok:
        return ""
    okuyucu = PdfReader(io.BytesIO(r.body()))
    return "\n".join((p.extract_text() or "") for p in okuyucu.pages[:30])


def tara(context, ad, ayar, ozet, bulgular):
    page = context.new_page()
    alan = ayar["alan"]
    adaylar, pdfler, gorulen_link = [], [], set()
    durum = {"liste_sayfasi": 0, "aday_ilan": 0, "acilan": 0, "pdf": 0, "hata": 0, "uyari": []}

    def ekle_linkler(lst, ust_baslik=""):
        for metin, href in lst:
            href = (href or "").split("#")[0]
            if not href or alan not in href or href in gorulen_link:
                continue
            n = norm(metin)
            if ".pdf" in href.lower():
                gorulen_link.add(href)
                pdfler.append((href, ust_baslik or metin))
            elif len(metin) >= 12 and RE_AKADEMIK.search(n) and not RE_HARIC.search(n):
                gorulen_link.add(href)
                adaylar.append((href, metin))

    # 1) Liste sayfaları
    for bas in ayar["baslangic"]:
        url, adim = bas, 0
        while url and adim < SAYFA_LIMIT:
            try:
                yukle(page, url)
                durum["liste_sayfasi"] += 1
                metin = govde(page)
                if RE_ENGEL.search(norm(metin)):
                    durum["uyari"].append(f"Bot koruması olabilir: {url} (GORUNUR=True ile dene)")
                DEBUG.mkdir(exist_ok=True)
                tag = re.sub(r"\W+", "_", ad)
                (DEBUG / f"{tag}_{adim}.html").write_text(page.content(), encoding="utf-8")
                page.screenshot(path=str(DEBUG / f"{tag}_{adim}.png"), full_page=True)
                lst = linkler(page)
                ekle_linkler(lst)
                # sonraki sayfa: "Sonraki/›/»" ya da sıradaki sayfa numarası ("2", "3"...)
                url = next((h for m, h in lst if alan in h and h != page.url and
                            (RE_SONRAKI.match(norm(m)) or m.strip() == str(adim + 2))), None)
            except Exception as e:
                durum["hata"] += 1
                durum["uyari"].append(f"Açılamadı: {url} ({type(e).__name__})")
                url = None
            adim += 1
            time.sleep(BEKLEME)

    durum["aday_ilan"] = len(adaylar)
    if not adaylar and not pdfler:
        durum["uyari"].append("İlan bağlantısı bulunamadı — sayfa yapısı tanınmadı. "
                              "'debug' klasöründeki dosyaları Claude'a gönder.")

    # 2) İlan sayfaları
    for href, baslik in adaylar[:MAX_DETAY]:
        try:
            yukle(page, href)
            durum["acilan"] += 1
            metin = govde(page)
            n = norm(metin)
            mimar, arsgor = bool(RE_MIMAR.search(n)), bool(RE_ARSGOR.search(n))
            if mimar and arsgor:
                bulgular.append({"kaynak": ad, "baslik": page.title() or baslik, "link": href,
                                 "son": son_basvuru(metin), "kesit": kesitler(metin), "tur": "ilan sayfası"})
            elif arsgor or RE_AKADEMIK.search(n):
                ekle_linkler(linkler(page), ust_baslik=page.title() or baslik)
        except Exception:
            durum["hata"] += 1
        time.sleep(BEKLEME)

    # 3) PDF ekleri
    for href, baslik in pdfler[:MAX_PDF]:
        try:
            metin = pdf_metni(context, href)
            durum["pdf"] += 1
            n = norm(metin)
            if RE_MIMAR.search(n) and RE_ARSGOR.search(n):
                bulgular.append({"kaynak": ad, "baslik": baslik, "link": href,
                                 "son": son_basvuru(metin), "kesit": kesitler(metin), "tur": "PDF"})
        except Exception:
            durum["hata"] += 1
        time.sleep(BEKLEME)

    if PdfReader is None:
        durum["uyari"].append("pypdf kurulu değil, PDF'ler okunmadı.")
    ozet[ad] = durum
    page.close()


def rapor(bulgular, ozet):
    eski = set(json.loads(GORULEN.read_text(encoding="utf-8"))) if GORULEN.exists() else set()
    for b in bulgular:
        b["yeni"] = b["link"] not in eski
    GORULEN.write_text(json.dumps(sorted(eski | {b["link"] for b in bulgular}), ensure_ascii=False, indent=1),
                       encoding="utf-8")
    bugun = datetime.date.today().isoformat()
    satirlar = "".join(
        f"<tr class='{'yeni' if b['yeni'] else ''}'><td>{'YENİ' if b['yeni'] else ''}</td>"
        f"<td>{html.escape(b['kaynak'])}</td><td><a href='{html.escape(b['link'])}' target='_blank'>"
        f"{html.escape(b['baslik'][:140])}</a><br><small>{b['tur']}</small></td>"
        f"<td>{html.escape(b['son'] or '—')}</td>"
        f"<td><small>{'<br>'.join(html.escape(k) for k in b['kesit'])}</small></td></tr>"
        for b in sorted(bulgular, key=lambda x: not x["yeni"]))
    ozet_html = "".join(
        f"<li><b>{html.escape(k)}</b>: {v['liste_sayfasi']} liste sayfası, {v['aday_ilan']} aday ilan, "
        f"{v['acilan']} ilan açıldı, {v['pdf']} PDF okundu, {v['hata']} hata"
        + "".join(f"<br>⚠ {html.escape(u)}" for u in v["uyari"]) + "</li>"
        for k, v in ozet.items())
    sayfa = f"""<!doctype html><meta charset="utf-8"><title>Arş. Gör. taraması {bugun}</title>
<style>body{{font-family:Segoe UI,Arial;margin:24px;color:#222}}table{{border-collapse:collapse;width:100%}}
td,th{{border:1px solid #ddd;padding:6px;vertical-align:top;text-align:left}}tr.yeni{{background:#fff6d6}}
th{{background:#f2f2f2}}</style>
<h2>Mimarlık Araştırma Görevlisi ilanları — {bugun}</h2>
<p>{len(bulgular)} eşleşme ({sum(b['yeni'] for b in bulgular)} yeni). Son başvuru tarihini ilan metninden mutlaka kontrol et.</p>
<table><tr><th></th><th>Kaynak</th><th>İlan</th><th>Son başvuru</th><th>Metinde "mimar" geçen yer</th></tr>{satirlar}</table>
<h3>Tarama özeti</h3><ul>{ozet_html}</ul>"""
    yol = KLASOR / f"rapor_arsgor_{bugun}.html"
    yol.write_text(sayfa, encoding="utf-8")
    return yol


def main():
    bulgular, ozet = [], {}
    with sync_playwright() as p:
        tarayici = p.chromium.launch(headless=not GORUNUR)
        context = tarayici.new_context(locale="tr-TR")
        for ad, ayar in KAYNAKLAR.items():
            print(f"→ {ad} taranıyor...")
            tara(context, ad, ayar, ozet, bulgular)
            d = ozet[ad]
            print(f"   {d['aday_ilan']} aday ilan, {d['acilan']} açıldı, {d['pdf']} PDF, {d['hata']} hata")
            for u in d["uyari"]:
                print("   ⚠", u)
        tarayici.close()
    yol = rapor(bulgular, ozet)
    yeni = [b for b in bulgular if b["yeni"]]
    excel = ortak.excel_kaydet(
        f"arsgor_{ortak.bugun()}.xlsx", ["Yeni", "Kaynak", "İlan", "Son başvuru", "Mimar geçen yer", "Link"],
        [["YENİ" if b["yeni"] else "", b["kaynak"], b["baslik"], b["son"], " | ".join(b["kesit"]), b["link"]]
         for b in bulgular], link_sutunu=5, yeni_sutunu=0)
    uyarilar = [u for d in ozet.values() for u in d["uyari"]]
    if yeni:
        ozet_metin = "\n".join(f"• {b['baslik'][:70]} (son: {b['son'] or '?'})" for b in yeni[:6])
        ortak.bildir(f"Ars. Gor.: {len(yeni)} yeni mimarlik ilani", ozet_metin + "\n\nExcel: " + ortak.EXCEL_YERI,
                     oncelik="high")
    elif uyarilar:
        ortak.bildir("Ars. Gor. taramasi: sorun var", "\n".join(uyarilar[:3]), oncelik="low")
    print(f"\n{len(bulgular)} eşleşme ({len(yeni)} yeni). Rapor: {yol}")
    for e in excel:
        print("Excel:", e)
    if not ortak.ACTIONS:
        webbrowser.open(yol.as_uri())


if __name__ == "__main__":
    main()
