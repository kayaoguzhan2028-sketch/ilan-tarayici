// Google Apps Script — GitHub Actions'tan gelen Excel dosyalarını Drive'daki
// "İlan Taramaları" klasörüne kaydeder. script.google.com'da yeni proje açıp
// bu kodu yapıştır, ANAHTAR'ı GitHub'daki DRIVE_ANAHTAR secret'ıyla aynı yap,
// Dağıt > Yeni dağıtım > Web uygulaması (Erişim: Herkes) ile yayınla.
const KLASOR_ADI = 'İlan Taramaları';
const ANAHTAR = 'BURAYA_ANAHTAR';

function doPost(e) {
  const v = JSON.parse(e.postData.contents);
  if (v.anahtar !== ANAHTAR) return ContentService.createTextOutput('yetkisiz');
  const bul = DriveApp.getFoldersByName(KLASOR_ADI);
  const klasor = bul.hasNext() ? bul.next() : DriveApp.createFolder(KLASOR_ADI);
  // Aynı adlı eski dosya varsa çöpe at (ör. "00 SON - LinkedIn.xlsx" her seferinde yenilenir)
  const eski = klasor.getFilesByName(v.ad);
  while (eski.hasNext()) eski.next().setTrashed(true);
  klasor.createFile(Utilities.newBlob(Utilities.base64Decode(v.veri), v.tur, v.ad));
  return ContentService.createTextOutput('ok');
}

// Kurulumdan sonra bir kez çalıştır: Drive izni verilir ve klasör oluşur.
function izinVer() {
  const bul = DriveApp.getFoldersByName(KLASOR_ADI);
  if (!bul.hasNext()) DriveApp.createFolder(KLASOR_ADI);
}
