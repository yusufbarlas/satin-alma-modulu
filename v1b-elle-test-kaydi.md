# Satın Alma Modülü — v1b menüden elle test kaydı

Tarih: 27 Kasım 2026 · `python ana.py` (v1b, 26 seçenekli menü), ayarlar.py'deki gerçek toleranslarla.
Veri dosyası yokken başlandı (ilk açılış). `◀` işaretli satırlar girilen cevaptır.
v1a'nın kaydı (eski menü numaralarıyla): `v1a-elle-test-kaydi.md`.

## Senaryolar

| No | Ne denendi | Beklenen | Sonuç |
|---|---|---|---|
| M1 | Üç tedarikçi; üçüncüsü birincinin adıyla | TED-0001 … TED-0003 | ✅ (aynı ad uyarısız kabul edildi, bkz. Gözlemler) |
| M2 | Talep açma, talep eden boş | "Hata: Talep eden boş olamaz", form yeniden sorulur; sonra TLP-0001 (2 kalem) | ✅ |
| M3 | Talep onayı; ikinci onay küçük harfle (tlp-0001) | Onaylandı; ikincisinde talep bulunur, 18b | ✅ |
| M4 | İki tedarikçiden teklif, pahalısı reddedilir | TKL-0001 (1400), TKL-0002 (1620) reddedildi | ✅ |
| M5 | Tekliften sipariş, onay | SAS-0001 · teklif TKL-0001; malzeme talepten gelir | ✅ |
| M6 | Siparişe bağlı talep kalemiyle ikinci sipariş | 20c, sipariş açılmaz | ✅ |
| M7 | Mal kabul ve fatura | MKB-0001; FTR-0001 ONAYLANDI · 1400 | ✅ |
| M8 | Ödeme: "120.00" biçimi ve olmayan fatura (12) | Tutar hatası doğru biçimi gösterir; 12 yazıldığı an reddedilir, tutar sorulmaz; ODM-0001 · 400 | ✅ |
| M9 | Kalan borcu aşan ödeme | 23e, kalemler yeniden sorulur; ODM-0002 · 1000, kalan 0 | ✅ |
| M10 | Numara sorusunda boş Enter; ödeme bekleyen liste | "Ana menüye dönülüyor."; liste boş | ✅ |
| M11 | Programı kapatıp açınca dört bekleyen liste | Hepsi boş (ödemeler dosyadan geri geldi) | ✅ |
| M12 | Ödemesi olan faturayı iptal, ödeme iptali | 9c; ODM-0002 iptal, kalan 1000 geri | ✅ |
| M13 | Talep reddi, reddedilmiş teklifin iptali | TLP-0002 reddedildi; TKL-0002 iptal edildi | ✅ |
| M14 | Zincir tersten: teklifi olan talep, siparişi olan teklif | 22a; 22b | ✅ |

## Oturum 1 — M1-M10

```
Seçiminiz: 6   ◀
Tedarikçi adı: ABC Kırtasiye   ◀
Firma adı (boş bırakılabilir):    ◀
Tedarikçi eklendi: TED-0001

Seçiminiz: 6   ◀
Tedarikçi adı: XYZ Ltd   ◀
Firma adı (boş bırakılabilir):    ◀
Tedarikçi eklendi: TED-0002

Seçiminiz: 6   ◀
Tedarikçi adı: ABC Kırtasiye   ◀
Firma adı (boş bırakılabilir):    ◀
Tedarikçi eklendi: TED-0003

Seçiminiz: 1   ◀
Talep eden (kişi ya da birim):     ◀
Malzeme adı (bitirmek için boş Enter): Defter   ◀
  Miktar: 10   ◀
  Birim: adet   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  Tahmini birim fiyat (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter):    ◀
Hata: Talep eden boş olamaz
Talep eden (kişi ya da birim): Muhasebe   ◀
Malzeme adı (bitirmek için boş Enter): Defter   ◀
  Miktar: 10   ◀
  Birim: adet   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  Tahmini birim fiyat (yoksa boş): 12,5   ◀
Malzeme adı (bitirmek için boş Enter): Toner   ◀
  Miktar: 2   ◀
  Birim: adet   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  Tahmini birim fiyat (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter):    ◀
Talep açıldı: TLP-0001 · TASLAK · 2 kalem

Seçiminiz: 2   ◀
Talep numarası: TLP-0001   ◀
Talep onaylandı: TLP-0001

Seçiminiz: 2   ◀
Talep numarası: tlp-0001   ◀
Hata: TLP-0001: sadece iptal edilmemiş TASLAK talep onaylanır (şu an ONAYLANDI)

Seçiminiz: 4   ◀
  TED-0001 - ABC Kırtasiye
  TED-0002 - XYZ Ltd
  TED-0003 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y, vazgeçmek için boş Enter): TED-0001   ◀
Tedarikçinin teklif numarası (boş bırakılabilir): T-55   ◀
Talep numarası (talepsiz için boş Enter): TLP-0001   ◀
Talep kalemi 10 · Defter (10 adet, tahmini 12.5)
  Miktar (almamak için 0): 10   ◀
  Birim fiyat: 100   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Talep kalemi 20 · Toner (2 adet)
  Miktar (almamak için 0): 2   ◀
  Birim fiyat: 200   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Talepte olmayan ek kalem varsa girin.
Malzeme adı (bitirmek için boş Enter):    ◀
Teklif kaydedildi: TKL-0001 · ACIK · toplam 1400.00

Seçiminiz: 4   ◀
  TED-0001 - ABC Kırtasiye
  TED-0002 - XYZ Ltd
  TED-0003 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y, vazgeçmek için boş Enter): TED-0002   ◀
Tedarikçinin teklif numarası (boş bırakılabilir):    ◀
Talep numarası (talepsiz için boş Enter): TLP-0001   ◀
Talep kalemi 10 · Defter (10 adet, tahmini 12.5)
  Miktar (almamak için 0): 10   ◀
  Birim fiyat: 120   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Talep kalemi 20 · Toner (2 adet)
  Miktar (almamak için 0): 2   ◀
  Birim fiyat: 210   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Talepte olmayan ek kalem varsa girin.
Malzeme adı (bitirmek için boş Enter):    ◀
Teklif kaydedildi: TKL-0002 · ACIK · toplam 1620.00

Seçiminiz: 5   ◀
Teklif numarası: TKL-0002   ◀
  1 - Daha iyi bir teklif var
  2 - Teslim süresi uygun değil
  3 - Teklif şartları uygun değil
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Teklif reddedildi: TKL-0002

Seçiminiz: 8   ◀
Teklif numarası: TKL-0001   ◀
Sipariş açıldı: SAS-0001 · TASLAK · toplam 1400.00 · teklif TKL-0001

Seçiminiz: 9   ◀
Sipariş numarası: SAS-0001   ◀
Sipariş onaylandı: SAS-0001

Seçiminiz: 7   ◀
  TED-0001 - ABC Kırtasiye
  TED-0002 - XYZ Ltd
  TED-0003 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y, vazgeçmek için boş Enter): TED-0002   ◀
Talep numarası (talepsiz için boş Enter): TLP-0001   ◀
Talep kalemi 10 · Defter (10 adet, tahmini 12.5)
  Miktar (almamak için 0): 5   ◀
  Birim fiyat: 120   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Talep kalemi 20 · Toner (2 adet)
  Miktar (almamak için 0): 0   ◀
Talepte olmayan ek kalem varsa girin.
Malzeme adı (bitirmek için boş Enter):    ◀
Hata: TLP-0001 / 10: talep kalemi zaten SAS-0001 siparişine bağlı

Seçiminiz: 10   ◀
Sipariş numarası: SAS-0001   ◀
Tır hâlâ kapıda mı? (E / H, boş = E):    ◀
Kalem 10 · Defter (sipariş 10 adet)
  Gelen miktar: 10   ◀
  Yanlış ürün miktarı (yoksa boş):    ◀
Kalem 20 · Toner (sipariş 2 adet)
  Gelen miktar: 2   ◀
  Yanlış ürün miktarı (yoksa boş):    ◀
Mal kabul kaydedildi: MKB-0001
Kalem 10: kabul 10 · karantina yok · kapıda red yok
Kalem 20: kabul 2 · karantina yok · kapıda red yok

Seçiminiz: 11   ◀
Sipariş numarası: SAS-0001   ◀
Tedarikçinin fatura numarası: F-1001   ◀
Kalem 10 · Defter (sipariş 10 adet × 100)
  Faturadaki miktar: 10   ◀
  Faturadaki birim fiyat: 100   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Kalem 20 · Toner (sipariş 2 adet × 200)
  Faturadaki miktar: 2   ◀
  Faturadaki birim fiyat: 200   ◀
  İskonto türü (ORAN / TUTAR, yoksa boş):    ◀
Fatura kaydedildi: FTR-0001 · ONAYLANDI · toplam 1400.00

Seçiminiz: 20   ◀
  FTR-0001 · TED-0001 · toplam 1400.00 · kalan 1400.00

Seçiminiz: 16   ◀
  TED-0001 - ABC Kırtasiye
  TED-0002 - XYZ Ltd
  TED-0003 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y, vazgeçmek için boş Enter): TED-0001   ◀
  FTR-0001 · TED-0001 · toplam 1400.00 · kalan 1400.00
Fatura numarası (bitirmek için boş Enter): FTR-0001   ◀
  Ödenen tutar: 120.00   ◀
Hata: Geçersiz tutar: 120.00 (örnek: 120,50 ya da 1.250,50)
  Ödenen tutar: 400   ◀
Fatura numarası (bitirmek için boş Enter): 12   ◀
Hata: Fatura bulunamadı: 12
Fatura numarası (bitirmek için boş Enter):    ◀
  1 - HAVALE_EFT
  2 - NAKIT
Ödeme yöntemi numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Ödeme kaydedildi: ODM-0001 · HAVALE_EFT · toplam 400
  FTR-0001: ödenen 400 · kalan 1000.00

Seçiminiz: 16   ◀
  TED-0001 - ABC Kırtasiye
  TED-0002 - XYZ Ltd
  TED-0003 - ABC Kırtasiye
Tedarikçi kodu (yeni tedarikçi için Y, vazgeçmek için boş Enter): TED-0001   ◀
  FTR-0001 · TED-0001 · toplam 1400.00 · kalan 1000.00
Fatura numarası (bitirmek için boş Enter): FTR-0001   ◀
  Ödenen tutar: 5000   ◀
Fatura numarası (bitirmek için boş Enter):    ◀
  1 - HAVALE_EFT
  2 - NAKIT
Ödeme yöntemi numarası: 2   ◀
Not (boş bırakılabilir):    ◀
Hata: FTR-0001: tutar (5000) kalan borcu (1000.00) aşıyor
  FTR-0001 · TED-0001 · toplam 1400.00 · kalan 1000.00
Fatura numarası (bitirmek için boş Enter): FTR-0001   ◀
  Ödenen tutar: 1000   ◀
Fatura numarası (bitirmek için boş Enter):    ◀
  1 - HAVALE_EFT
  2 - NAKIT
Ödeme yöntemi numarası: 2   ◀
Not (boş bırakılabilir): kalan   ◀
Ödeme kaydedildi: ODM-0002 · NAKIT · toplam 1000
  FTR-0001: ödenen 1000 · kalan 0.00

Seçiminiz: 22   ◀
Fatura numarası:    ◀
Ana menüye dönülüyor.

Seçiminiz: 20   ◀
Ödeme bekleyen fatura yok.

Seçiminiz: 0   ◀
Çıkış yapılıyor...
```

## Oturum 2 — programı kapatıp açtıktan sonra (M11-M14)

```
Seçiminiz: 17   ◀
Eşleşme bekleyen fatura yok.

Seçiminiz: 18   ◀
Bloke fatura yok.

Seçiminiz: 19   ◀
Karantinada bekleyen mal yok.

Seçiminiz: 20   ◀
Ödeme bekleyen fatura yok.

Seçiminiz: 22   ◀
Fatura numarası: FTR-0001   ◀
  1 - Yanlış sipariş seçildi
  2 - Miktar / fiyat yanlış girildi
  3 - Mükerrer giriş
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Hata: FTR-0001: faturanın aktif ödemesi var, önce ödemeyi iptal edin

Seçiminiz: 21   ◀
Ödeme numarası: ODM-0002   ◀
  1 - Yanlış fatura seçildi
  2 - Tutar yanlış girildi
  3 - Mükerrer giriş
  4 - Banka ödemeyi iade etti
  5 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Ödeme iptal edildi: ODM-0002

Seçiminiz: 20   ◀
  FTR-0001 · TED-0001 · toplam 1400.00 · kalan 1000.00

Seçiminiz: 1   ◀
Talep eden (kişi ya da birim): Depo   ◀
Malzeme adı (bitirmek için boş Enter): Kalem   ◀
  Miktar: 5   ◀
  Birim: adet   ◀
  Kategori (SARF / STRATEJIK): SARF   ◀
  Tahmini birim fiyat (yoksa boş):    ◀
Malzeme adı (bitirmek için boş Enter):    ◀
Talep açıldı: TLP-0002 · TASLAK · 1 kalem

Seçiminiz: 3   ◀
Talep numarası: TLP-0002   ◀
  1 - Bütçe yok
  2 - İhtiyaç yok
  3 - Malzeme stokta var
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Talep reddedildi: TLP-0002

Seçiminiz: 25   ◀
Teklif numarası: TKL-0002   ◀
  1 - Yanlış tedarikçi seçildi
  2 - Miktar / fiyat yanlış girildi
  3 - Mükerrer giriş
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Teklif iptal edildi: TKL-0002

Seçiminiz: 26   ◀
Talep numarası: TLP-0001   ◀
  1 - Miktar yanlış girildi
  2 - Mükerrer giriş
  3 - Talepten vazgeçildi
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Hata: TLP-0001: talebe bağlı aktif teklif var (TKL-0001), önce teklifi iptal edin

Seçiminiz: 25   ◀
Teklif numarası: TKL-0001   ◀
  1 - Yanlış tedarikçi seçildi
  2 - Miktar / fiyat yanlış girildi
  3 - Mükerrer giriş
  4 - Diğer
Gerekçe numarası: 1   ◀
Not (boş bırakılabilir):    ◀
Hata: TKL-0001: teklife bağlı aktif sipariş var, önce siparişi iptal edin

Seçiminiz: 0   ◀
Çıkış yapılıyor...
```

## Gözlemler

- Aynı adla ikinci bir tedarikçi uyarısız açılıyor (M1); mükerrer tedarikçi kontrolü vergi numarasıyla birlikte v2'de.
- Menü her işlemden sonra 26 satır olarak yeniden basılıyor, sonuç yukarıda kalıyor; iç kodlar (HAVALE_EFT, ONAYLANDI) ekranda olduğu gibi görünüyor. İkisi de v2'de (ekran düzeni, Enum ile Türkçe etiketler).
- Teklifi siparişe dönüşmüş talepte iptal mesajı önce teklifi gösteriyor; teklif de siparişe bağlı olduğu için iptal zinciri sipariş → teklif → talep sırasıyla yürüyor (M14).
