# Satın Alma Modülü

ERP mantığında satın alma süreci: **sipariş → mal kabul → fatura** ve bunların
**üçlü eşleştirmesi** (three-way match). SAP MM'deki fatura doğrulama (MM-IV)
mantığını örnek alan, Python ile yazılmış katmanlı bir terminal uygulaması.

> **Durum:** geliştiriliyor (v1a). Yürüyen iskelet tamamlandı: tam eşleşme (A1)
> ve kapat-aç (F1) senaryoları uçtan uca çalışıyor.

## Ne yapar?

- Tedarikçi ekler, sipariş açar ve onaylar.
- Mal kabulde gelen miktarı üç kovaya ayırır: **kabul**, **karantina**, **kapıda red**
  (fazla teslimat toleransı ve aşırı sınıra göre).
- Faturayı sipariş ve mal kabulle karşılaştırır:
  - Miktar: faturalanan miktar kabul edilen miktarı aşamaz.
  - Fiyat: fatura net fiyatı, sipariş net fiyatının alt ve üst toleransı içinde olmalı.
  - Sonuç **ONAYLANDI** ya da nedeniyle birlikte **BLOKE** (ör. `FIYAT_YUKSEK`).
- Mal gelmeden gelen fatura **ESLESME_BEKLIYOR** durumunda bekler.
- Tolerans malzeme kategorisine göredir (SARF / STRATEJIK); sipariş açılırken kaleme kopyalanır.
- Tutarlar `float` değil `Decimal` ile hesaplanır.
- Bütün veri ve belge numaraları tek bir JSON dosyasında saklanır; program kapanıp açılınca geri gelir.

## Kurulum

Python 3.11 veya üstü gerekir. Program dış kütüphane kullanmaz; testler için pytest gerekir.

```bash
git clone https://github.com/yusufbarlas/satin-alma-modulu.git
cd satin-alma-modulu
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

## Çalıştırma

```bash
python ana.py          # terminal menüsü
pytest -v              # test senaryoları (her testin adı ve PASSED / FAILED)
```

Menü gerçek veriyi `veri.json`'a yazar (Git'e girmez). Testler her seferinde
pytest'in açtığı geçici bir klasörde çalışır; gerçek veriye dokunmaz.

## Elle test (menü)

`python ana.py` ile boş veri dosyasından başlanarak sırayla denendi; ikinci
oturumda program kapatılıp açıldı. Ekran çıktısının tamamı: `elle-test-kaydi.md`.

| # | Senaryo | Menü | Sonuç |
|---|---|---|---|
| M1 | İlk açılış, tedarikçi ekle | 1 | TED-0001 |
| M2 | Sipariş aç (A4 kağıt 10 × 100, toner 4 × 250) ve onayla | 2, 3 | SAS-0001 · TASLAK → ONAYLANDI · 2000.00 |
| M3 | Mal kabul: 10 yerine 12 geldi; miktara "abc" yazıldı | 4 | Kabul 11, karantina 1 KARAR_BEKLIYOR (sınır YUZDE); "abc" için miktar tekrar soruldu |
| M4 | Fatura: 11 × 106 | 5 | BLOKE · FIYAT_YUKSEK |
| M5 | Bloke nedeni ayrıntısı | 6 | Kalem 10: beklenen 100, gelen 106, izin 5 (YUZDE) |
| M6 | Bloke listesi, serbest bırak | 11, 7 | Listede FTR-0001 → SERBEST |
| M7 | Karantina kararı: 1 adet İADE | 12, 9 | Karar kaydedildi; karantina listesi boşaldı |
| M8 | Faturası olan mal kabulü iptal etme | 14 | Reddedildi: önce fatura iptal edilmeli (8c) |
| M9 | Fatura malden önce gelir (SAS-0002, un 100 kg) | 2, 3, 5, 10, 4 | ESLESME_BEKLIYOR, bekleyenlerde; mal kabulde kendiliğinden ONAYLANDI |
| M10 | Aynı tedarikçinin F-1001'i ikinci kez | 5 | Reddedildi: zaten FTR-0001 olarak kayıtlı (14a) |
| M11 | Kapat-aç: belgeler geri geliyor mu | 6, 10, 11, 12 | FTR-0001 SERBEST, ayrıntı yeniden hesaplandı; listeler boş |
| M12 | İptal zinciri: önce sipariş, sonra tersten | 15, 13, 14, 15 | Sipariş önce reddedildi (11c); fatura → mal kabul → sipariş sırasıyla iptal edildi |
| M13 | İptal edilmiş siparişe mal kabul | 4 | Reddedildi: sipariş iptal edilmiş |
| M14 | Sipariş ekranından yeni tedarikçi (Y), geçersiz kategori | 2 | TED-0002 eklendi; HAMMADDE reddedildi, kalemler tekrar soruldu; SAS-0003 |

## Proje yapısı

| Dosya | Görevi |
|---|---|
| `ayarlar.py` | Sabitler: toleranslar, belge önekleri, dosya adları |
| `hatalar.py` | Hata sınıfları (`SatinAlmaError` ve alt sınıfları) |
| `para.py` | Tutar çevirme, yuvarlama, iskontolu net fiyat |
| `modeller.py` | Belgeler: Tedarikçi, Sipariş, Mal kabul, Fatura ve kalemleri; durum geçişleri |
| `eslestirme.py` | Eşleştirme kuralları (miktar, fiyat) ve fazla teslimatın üç kova hesabı |
| `depolama.py` | JSON'a kaydetme ve geri yükleme |
| `servis.py` | İş akışı: `SatinAlmaServisi` (belgeler arası kurallar burada) |
| `ana.py` | Terminal menüsü (kullanıcıyla konuşan tek dosya) |
| `test_senaryolar.py` | Programı uçtan uca deneyen test senaryoları (pytest) |

Bağımlılık yönü tek: üstteki katman alttakini kullanır, tersi olmaz.

## Yol haritası

- **v1a:** sipariş, mal kabul, fatura, üçlü eşleştirme, iptaller, bloke faturayı serbest bırakma / reddetme, 52 test senaryosu (pytest)
- **v1b:** satın alma talebi, onay, teklif, ödeme
- **v2:** enum, tarih tipleri, loglama, tip ipuçları, CI (her push'ta testler), kısmi teslimat, KDV
- **v3:** PostgreSQL, FastAPI, kullanıcı rolleri