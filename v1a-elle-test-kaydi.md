# Satın Alma Modülü — v1a menüden elle test kaydı

Tarih: 22 Kasım 2026 · `python ana.py`, ayarlar.py'deki gerçek toleranslarla (SARF: fazla %10, aşırı %25, fiyat üst %5).
Veri dosyası yokken başlandı (ilk açılış). `◀` işaretli satırlar klavyeden girilen cevaptır.
v1a menü numaralarıyla; v1b'nin kaydı (26 seçenekli menü): `v1b-elle-test-kaydi.md`.

## Oturum 1 — M1-M10

```
Seçiminiz: 1   ◀
Tedarikçi adı: ABC Kırtasiye   ◀
Firma adı (boş bırakılabilir):    ◀
Tedarikçi eklendi: TED-0001

Seçiminiz: 2   ◀
  TED-0001 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y): TED-0001   ◀
Malzeme adı (bitirmek için boş Enter): A4 kağıt   ◀
  Miktar: 10   ◀
  Birim: adet   ◀
  Birim fiyat: 100   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
  Miktar tavanı (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter): Toner   ◀
  Miktar: 4   ◀
  Birim: adet   ◀
  Birim fiyat: 250   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
  Miktar tavanı (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter):    ◀
Sipariş açıldı: SAS-0001 · TASLAK · toplam 2000.00

Seçiminiz: 3   ◀
Sipariş numarası: SAS-0001   ◀
Sipariş onaylandı: SAS-0001

Seçiminiz: 4   ◀
Sipariş numarası: SAS-0001   ◀
Tır hâlâ kapıda mı? (E / H, boş = E): E   ◀
Kalem 10 · A4 kağıt (sipariş 10 adet)
  Gelen miktar: 12   ◀
  Yanlış ürün miktarı (yoksa boş):    ◀
Kalem 20 · Toner (sipariş 4 adet)
  Gelen miktar: abc   ◀
Geçersiz tutar: abc
  Gelen miktar: 4   ◀
  Yanlış ürün miktarı (yoksa boş):    ◀
Mal kabul kaydedildi: MKB-0001
Kalem 10: kabul 11 · karantina 1 KARAR_BEKLIYOR · kapıda red yok · sınır: YUZDE
Kalem 20: kabul 4 · karantina yok · kapıda red yok

Seçiminiz: 5   ◀
Sipariş numarası: SAS-0001   ◀
Tedarikçinin fatura numarası: F-1001   ◀
Kalem 10 · A4 kağıt (sipariş 10 adet × 100)
  Faturadaki miktar: 11   ◀
  Faturadaki birim fiyat: 106   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Kalem 20 · Toner (sipariş 4 adet × 250)
  Faturadaki miktar: 4   ◀
  Faturadaki birim fiyat: 250   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Fatura kaydedildi: FTR-0001 · BLOKE · toplam 2166.00
Bloke nedeni: FIYAT_YUKSEK

Seçiminiz: 6   ◀
Fatura numarası: FTR-0001   ◀
FTR-0001 · BLOKE
Kalem 10: FIYAT_YUKSEK · beklenen 100 · gelen 106 · izin 5.00 (YUZDE)

Seçiminiz: 11   ◀
FTR-0001 · SAS-0001 · toplam 2166.00 · neden: FIYAT_YUKSEK

Seçiminiz: 7   ◀
Fatura numarası: FTR-0001   ◀
Kalem 10: FIYAT_YUKSEK · beklenen 100 · gelen 106 · izin 5.00 (YUZDE)
  1 - Fiyat farkı onaylandı
  2 - Tedarikçi habersiz indirim yaptı
  3 - Yönetici onayı
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Fatura serbest bırakıldı: FTR-0001

Seçiminiz: 12   ◀
MKB-0001 kalem 10 (SAS-0001): 1 KARAR_BEKLIYOR · toplam 1

Seçiminiz: 9   ◀
MKB-0001 kalem 10 (SAS-0001): 1 KARAR_BEKLIYOR · toplam 1
Mal kabul numarası: MKB-0001   ◀
Kalem no: 10   ◀
  1 - IADE
Karar numarası: 1   ◀
Miktar: 1   ◀
  1 - Fazla miktar kabul edilmedi
  2 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Karar kaydedildi: MKB-0001 kalem 10 · IADE 1

Seçiminiz: 12   ◀
Karantinada bekleyen mal yok.

Seçiminiz: 14   ◀
Mal kabul numarası: MKB-0001   ◀
  1 - Yanlış sipariş seçildi
  2 - Miktar yanlış girildi
  3 - Mükerrer giriş
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
MKB-0001: bu mal kabule dayanan aktif fatura var (FTR-0001), önce faturayı iptal edin

Seçiminiz: 2   ◀
  TED-0001 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y): TED-0001   ◀
Malzeme adı (bitirmek için boş Enter): Un   ◀
  Miktar: 100   ◀
  Birim: kg   ◀
  Birim fiyat: 20   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
  Miktar tavanı (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter):    ◀
Sipariş açıldı: SAS-0002 · TASLAK · toplam 2000.00

Seçiminiz: 3   ◀
Sipariş numarası: SAS-0002   ◀
Sipariş onaylandı: SAS-0002

Seçiminiz: 5   ◀
Sipariş numarası: SAS-0002   ◀
Tedarikçinin fatura numarası: F-1002   ◀
Kalem 10 · Un (sipariş 100 kg × 20)
  Faturadaki miktar: 100   ◀
  Faturadaki birim fiyat: 20   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Fatura kaydedildi: FTR-0002 · ESLESME_BEKLIYOR · toplam 2000.00
Mal kabul bekleniyor; mal gelince eşleştirilecek.

Seçiminiz: 10   ◀
FTR-0002 · SAS-0002 · tedarikçi no F-1002 · toplam 2000.00

Seçiminiz: 4   ◀
Sipariş numarası: SAS-0002   ◀
Tır hâlâ kapıda mı? (E / H, boş = E):    ◀
Kalem 10 · Un (sipariş 100 kg)
  Gelen miktar: 100   ◀
  Yanlış ürün miktarı (yoksa boş):    ◀
Mal kabul kaydedildi: MKB-0002
Kalem 10: kabul 100 · karantina yok · kapıda red yok
Bekleyen fatura eşleşti: FTR-0002 · ONAYLANDI

Seçiminiz: 5   ◀
Sipariş numarası: SAS-0002   ◀
Tedarikçinin fatura numarası: F-1001   ◀
Kalem 10 · Un (sipariş 100 kg × 20)
  Faturadaki miktar: 100   ◀
  Faturadaki birim fiyat: 20   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Bu tedarikçinin F-1001 numaralı faturası zaten FTR-0001 olarak kayıtlı

Seçiminiz: 0   ◀
Çıkış yapılıyor...
```

## Oturum 2 — programı kapatıp açtıktan sonra (M11-M14)

```
Seçiminiz: 6   ◀
Fatura numarası: FTR-0001   ◀
FTR-0001 · SERBEST
Kalem 10: FIYAT_YUKSEK · beklenen 100 · gelen 106 · izin 5.00 (YUZDE)

Seçiminiz: 10   ◀
Eşleşme bekleyen fatura yok.

Seçiminiz: 11   ◀
Bloke fatura yok.

Seçiminiz: 12   ◀
Karantinada bekleyen mal yok.

Seçiminiz: 15   ◀
Sipariş numarası: SAS-0002   ◀
  1 - Yanlış tedarikçi seçildi
  2 - Miktar / fiyat yanlış girildi
  3 - Mükerrer giriş
  4 - Siparişten vazgeçildi
  5 - Diğer
Gerekçe numarası: 4   ◀
Not (boş bırakılabilir):    ◀
SAS-0002: siparişin iptal edilmemiş mal kabulü var, önce mal kabulü iptal edin

Seçiminiz: 13   ◀
Fatura numarası: FTR-0002   ◀
  1 - Yanlış sipariş seçildi
  2 - Miktar / fiyat yanlış girildi
  3 - Mükerrer giriş
  4 - Diğer
Gerekçe numarası: 3   ◀
Not (boş bırakılabilir):    ◀
Fatura iptal edildi: FTR-0002

Seçiminiz: 14   ◀
Mal kabul numarası: MKB-0002   ◀
  1 - Yanlış sipariş seçildi
  2 - Miktar yanlış girildi
  3 - Mükerrer giriş
  4 - Diğer
Gerekçe numarası: 3   ◀
Not (boş bırakılabilir):    ◀
Mal kabul iptal edildi: MKB-0002

Seçiminiz: 15   ◀
Sipariş numarası: SAS-0002   ◀
  1 - Yanlış tedarikçi seçildi
  2 - Miktar / fiyat yanlış girildi
  3 - Mükerrer giriş
  4 - Siparişten vazgeçildi
  5 - Diğer
Gerekçe numarası: 4   ◀
Not (boş bırakılabilir):    ◀
Sipariş iptal edildi: SAS-0002

Seçiminiz: 4   ◀
Sipariş numarası: SAS-0002   ◀
Tır hâlâ kapıda mı? (E / H, boş = E):    ◀
Kalem 10 · Un (sipariş 100 kg)
  Gelen miktar: 1   ◀
  Yanlış ürün miktarı (yoksa boş):    ◀
SAS-0002: sipariş iptal edilmiş, mal kabul yapılamaz

Seçiminiz: 2   ◀
  TED-0001 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y): Y   ◀
Tedarikçi adı: XYZ Bilişim   ◀
Firma adı (boş bırakılabilir):    ◀
Tedarikçi eklendi: TED-0002
Malzeme adı (bitirmek için boş Enter): Kalem   ◀
  Miktar: 1   ◀
  Birim: adet   ◀
  Birim fiyat: 50   ◀
  Kategori (SARF / STRATEJIK): HAMMADDE   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
  Miktar tavanı (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter):    ◀
Geçersiz kategori: HAMMADDE
Kalemleri yeniden girin.
Malzeme adı (bitirmek için boş Enter): Kalem   ◀
  Miktar: 1   ◀
  Birim: adet   ◀
  Birim fiyat: 50   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
  Miktar tavanı (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter):    ◀
Sipariş açıldı: SAS-0003 · TASLAK · toplam 50.00

Seçiminiz: 0   ◀
Çıkış yapılıyor...
```
