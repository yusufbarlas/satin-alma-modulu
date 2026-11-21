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