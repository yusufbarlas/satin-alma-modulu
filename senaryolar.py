import json
from decimal import Decimal

from ayarlar import TEST_VERI_DOSYASI
from depolama import bos_veri_olustur, kaydet
from hatalar import DepolamaError
from modeller import ToleransKopyasi
from servis import SatinAlmaServisi


def baslangic_verisini_kur():
    """Senaryolar için temiz başlangıç verisini kurar ve servisi döndürür.

    Test dosyası boş veriyle temizlenir, o dosyayla yeni servis açılır,
    ortak test verisi (D madde 8) servis metotlarıyla kurulur: 2 tedarikçi,
    5 onaylı sipariş. Toleranslar ayarlar.py'den değil, varsayılan test
    ayarlarından gelir (E47, E55); tarih sabit "2026-11-02" (E53). Her
    senaryo ilk iş bunu çağırır (E49, E88).

    Returns:
        SatinAlmaServisi: TED-0001, TED-0002 ve SAS-0001 … SAS-0005
        (ONAYLANDI) kurulu servis.
    """
    bos_veri = bos_veri_olustur()
    kaydet(bos_veri, TEST_VERI_DOSYASI)
    servis = SatinAlmaServisi(TEST_VERI_DOSYASI)
    servis.tedarikci_ekle(tedarikci_adi="ABC Kırtasiye")
    servis.tedarikci_ekle(tedarikci_adi="XYZ Bilişim")
    sarf_tolerans = ToleransKopyasi(
        fazla_teslimat_yuzde=Decimal("10"),
        fazla_teslimat_tl=Decimal("500"),
        asiri_sinir_yuzde=Decimal("30"),
        asiri_sinir_tl=Decimal("2000"),
        fiyat_ust_yuzde=Decimal("2"),
        fiyat_ust_tl=Decimal("100"),
        fiyat_alt_yuzde=Decimal("2"),
        fiyat_alt_tl=Decimal("100"),
        kucuk_fark_esigi=Decimal("10"),
    )
    stratejik_tolerans = ToleransKopyasi(
        fazla_teslimat_yuzde=Decimal("2"),
        fazla_teslimat_tl=Decimal("1000"),
        asiri_sinir_yuzde=Decimal("5"),
        asiri_sinir_tl=Decimal("5000"),
        fiyat_ust_yuzde=Decimal("1"),
        fiyat_ust_tl=Decimal("50"),
        fiyat_alt_yuzde=Decimal("1"),
        fiyat_alt_tl=Decimal("50"),
        kucuk_fark_esigi=Decimal("10"),
    )


    
    test_tarihi = "2026-11-02"

    siparis = servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("10"), "birim": "adet",
         "birim_fiyat": Decimal("100"), "kategori": "SARF"},
        {"malzeme_adi": "Toner", "miktar": Decimal("4"), "birim": "adet",
         "birim_fiyat": Decimal("250"), "kategori": "SARF"},
    ], tolerans=sarf_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(siparis.siparis_no)

    siparis = servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "Un", "miktar": Decimal("100"), "birim": "kg",
         "birim_fiyat": Decimal("20"), "kategori": "SARF"},
    ], tolerans=sarf_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(siparis.siparis_no)

    siparis = servis.siparis_ac("TED-0002", [
        {"malzeme_adi": "Dizüstü bilgisayar", "miktar": Decimal("5"), "birim": "adet",
         "birim_fiyat": Decimal("10000"), "kategori": "STRATEJIK"},
    ], tolerans=stratejik_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(siparis.siparis_no)

    siparis = servis.siparis_ac("TED-0002", [
        {"malzeme_adi": "Kurşun kalem", "miktar": Decimal("1000"), "birim": "adet",
         "birim_fiyat": Decimal("0.50"), "kategori": "SARF",
         "iskonto_turu": "ORAN", "iskonto_degeri": Decimal("10"),
         "miktar_tavani": Decimal("50")},
    ], tolerans=sarf_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(siparis.siparis_no)

    siparis = servis.siparis_ac("TED-0002", [
        {"malzeme_adi": "Dosya", "miktar": Decimal("3"), "birim": "adet",
         "birim_fiyat": Decimal("33.33"), "kategori": "SARF",
         "iskonto_turu": "ORAN", "iskonto_degeri": Decimal("7")},
    ], tolerans=sarf_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(siparis.siparis_no)
    
    return servis


def senaryo_f1():
    """F1 — kapat-aç: kaydedilen belgeler ve sayaçlar dosyadan geri gelir.

    A1 yürütülür (SAS-0001'e mal kabul + fatura), sonra aynı test
    dosyasıyla yeni bir servis açılır (programın kapanıp açılması) ve
    yeni sipariş açılır (E6, E7, E53).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    yeni_servis = SatinAlmaServisi(TEST_VERI_DOSYASI)
    yeni_siparis = yeni_servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("1"), "birim": "adet",
         "birim_fiyat": Decimal("100"), "kategori": "SARF"},
    ], tarih=test_tarihi)

    if (yeni_siparis.siparis_no == "SAS-0006"
            and "MKB-0001" in yeni_servis.mal_kabuller
            and "FTR-0001" in yeni_servis.faturalar
            and yeni_servis.faturalar["FTR-0001"].durum == "ONAYLANDI"
            and yeni_servis.faturalar["FTR-0001"].kayit_tarihi == test_tarihi):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"F1 kapat-aç: {sonuc}")
    return sonuc


def senaryo_a1():
    """A1 — tam eşleşme: sipariş = mal kabul = fatura, fatura onaylanır.

    SAS-0001'e tam miktarda mal kabul (10 / 4) ve sipariş fiyatlarıyla
    fatura F-1001 (10 × 100, 4 × 250) kaydedilir. Fatura ONAYLANDI olmalı,
    bloke nedeni olmamalı; her kalem MKB-0001'den kendi miktarı kadar
    kapanmalı (E5, E41).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet(siparis_no="SAS-0001", kalemler=[
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)

    kaydedilen_fatura = servis.fatura_kaydet(
        siparis_no="SAS-0001", tedarikci_fatura_no="F-1001", kalemler=[
            {"siparis_kalem_no": 10, "miktar": Decimal("10"),
             "birim_fiyat": Decimal("100")},
            {"siparis_kalem_no": 20, "miktar": Decimal("4"),
             "birim_fiyat": Decimal("250")},
        ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "ONAYLANDI"
            and kaydedilen_fatura.bloke_neden_kodlari == []
            and kaydedilen_fatura.fatura_kalemleri[0].mal_kabul_dagitimi[0].mal_kabul_no == "MKB-0001"
            and kaydedilen_fatura.fatura_kalemleri[0].mal_kabul_dagitimi[0].miktar == Decimal("10")
            and kaydedilen_fatura.fatura_kalemleri[1].mal_kabul_dagitimi[0].mal_kabul_no == "MKB-0001"
            and kaydedilen_fatura.fatura_kalemleri[1].mal_kabul_dagitimi[0].miktar == Decimal("4")):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"A1 tam eşleşme: {sonuc}")
    return sonuc


def senaryo_b1():
    """B1 — tam sınırda geçer: izin 2 TL, fatura 102,00 onaylanır (E33).

    Sınır dahildir: fiyat tam sınırdaysa fatura bloke olmaz.

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("102.00")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "ONAYLANDI"
            and kaydedilen_fatura.bloke_neden_kodlari == []):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B1 tam sınırda geçer: {sonuc}")
    return sonuc


def senaryo_b2():
    """B2 — 1 kuruş üstü: izin 2 TL, fatura 102,01 → FIYAT_YUKSEK (E33).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("102.01")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "BLOKE"
            and kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B2 1 kuruş üstü: {sonuc}")
    return sonuc


def senaryo_b3():
    """B3 — düşük fiyat: izin 2 TL, fatura 97,99 → FIYAT_DUSUK (E29, E39).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("97.99")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "BLOKE"
            and kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_DUSUK"]):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B3 düşük fiyat: {sonuc}")
    return sonuc


def senaryo_b4():
    """B4 — küçük fark eşiği kurtarır: net 0,45, fatura 0,46 (E40).

    Yüzde izni 0,009; eşik 10 TL ÷ 1.000 = 0,01 → izin 0,01, onaylanır.

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0004", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("1000")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0004", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("1000"),
         "birim_fiyat": Decimal("0.46")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "ONAYLANDI"
            and kaydedilen_fatura.bloke_neden_kodlari == []):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B4 küçük fark eşiği: {sonuc}")
    return sonuc


def senaryo_b5():
    """B5 — TL tavanı belirler: izin 50 TL ÷ 5 = 10, fatura 10.011 (E33).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0003", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("5")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0003", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("5"),
         "birim_fiyat": Decimal("10011")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "BLOKE"
            and kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B5 TL tavanı: {sonuc}")
    return sonuc

def senaryo_b6():
    """B6 — tanımsız sınır: fiyat alt sınırı boşsa alta bakılmaz.

    SARF test toleransı, fiyat alt sınırının iki sınırı boş (None).
    100 TL'lik kaleme 90 TL fatura gelir; onaylanır (E29, Karar 2c).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    alt_siniri_bos_tolerans = ToleransKopyasi(
        fazla_teslimat_yuzde=Decimal("10"),
        fazla_teslimat_tl=Decimal("500"),
        asiri_sinir_yuzde=Decimal("30"),
        asiri_sinir_tl=Decimal("2000"),
        fiyat_ust_yuzde=Decimal("2"),
        fiyat_ust_tl=Decimal("100"),
        fiyat_alt_yuzde=None,
        fiyat_alt_tl=None,
        kucuk_fark_esigi=Decimal("10"),
    )
    siparis = servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("10"), "birim": "adet",
         "birim_fiyat": Decimal("100"), "kategori": "SARF"},
    ], tolerans=alt_siniri_bos_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(siparis.siparis_no)
    servis.mal_kabul_kaydet(siparis.siparis_no, [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet(siparis.siparis_no, "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("90")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "ONAYLANDI"
            and kaydedilen_fatura.bloke_neden_kodlari == []):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B6 tanımsız sınır: {sonuc}")
    return sonuc



def senaryo_b7():
    """B7 — net fiyat karşılaştırması: sipariş 0,50 − %10 = 0,45 (E30).

    Fatura iskontosuz 0,45; net fiyatlar eşit, onaylanır.

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0004", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("1000")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0004", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("1000"),
         "birim_fiyat": Decimal("0.45")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "ONAYLANDI"
            and kaydedilen_fatura.bloke_neden_kodlari == []):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B7 net fiyat: {sonuc}")
    return sonuc


def senaryo_b8():
    """B8 — ayar değişti, eski sipariş: kalemdeki tolerans kopyası geçer.

    SAS-0001 %2 kopyayla açıldı; fatura 101,50 onaylanır. Aynı fatura,
    üst sınırı %1'e indirilmiş yeni bir siparişte bloke olur (Karar 1b, E47).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    eski_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("101.50")},
    ], tarih=test_tarihi)

    yeni_tolerans = ToleransKopyasi(
        fazla_teslimat_yuzde=Decimal("10"),
        fazla_teslimat_tl=Decimal("500"),
        asiri_sinir_yuzde=Decimal("30"),
        asiri_sinir_tl=Decimal("2000"),
        fiyat_ust_yuzde=Decimal("1"),
        fiyat_ust_tl=Decimal("100"),
        fiyat_alt_yuzde=Decimal("2"),
        fiyat_alt_tl=Decimal("100"),
        kucuk_fark_esigi=Decimal("10"),
    )
    yeni_siparis = servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("10"), "birim": "adet",
         "birim_fiyat": Decimal("100"), "kategori": "SARF"},
    ], tolerans=yeni_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(yeni_siparis.siparis_no)
    servis.mal_kabul_kaydet(yeni_siparis.siparis_no, [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    yeni_fatura = servis.fatura_kaydet(yeni_siparis.siparis_no, "F-1002", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("101.50")},
    ], tarih=test_tarihi)

    if (eski_fatura.durum == "ONAYLANDI"
            and yeni_fatura.durum == "BLOKE"
            and yeni_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B8 eski ayarlı sipariş: {sonuc}")
    return sonuc


def senaryo_b9():
    """B9 — kalem yer değiştirme: k10 250, k20 100 faturalanır (E29).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("250")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("100")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "BLOKE"
            and kaydedilen_fatura.bloke_neden_kodlari
            == ["FIYAT_YUKSEK", "FIYAT_DUSUK"]):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B9 kalem yer değiştirme: {sonuc}")
    return sonuc


def senaryo_b10():
    """B10 — tek yuvarlama: 3 × 33,33, ORAN %7 → tutar 92,99 (E35).

    Ara yuvarlama yapılsaydı 93,00 çıkardı.

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0005", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("3")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0005", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("3"),
         "birim_fiyat": Decimal("33.33"),
         "iskonto_turu": "ORAN", "iskonto_degeri": Decimal("7")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "ONAYLANDI"
            and kaydedilen_fatura.fatura_kalemleri[0].tutar()
            == Decimal("92.99")):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B10 tek yuvarlama: {sonuc}")
    return sonuc


def senaryo_b11():
    """B11 — alt sınır 0 ≠ tanımsız: 0 hiç izin yok demektir.

    STRATEJIK test toleransı, fiyat alt sınırı %0 ve 0 TL. İzin küçük fark
    eşiğine çıkar (10 ÷ 5 = 2); 9.997 < 9.998 → FIYAT_DUSUK. Alt sınır
    tanımsız olsaydı onaylanırdı (B6) (E29, E40, Karar 2c).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    servis = baslangic_verisini_kur()
    test_tarihi = "2026-11-02"
    sifir_alt_tolerans = ToleransKopyasi(
        fazla_teslimat_yuzde=Decimal("2"),
        fazla_teslimat_tl=Decimal("1000"),
        asiri_sinir_yuzde=Decimal("5"),
        asiri_sinir_tl=Decimal("5000"),
        fiyat_ust_yuzde=Decimal("1"),
        fiyat_ust_tl=Decimal("50"),
        fiyat_alt_yuzde=Decimal("0"),
        fiyat_alt_tl=Decimal("0"),
        kucuk_fark_esigi=Decimal("10"),
    )
    siparis = servis.siparis_ac("TED-0002", [
        {"malzeme_adi": "Dizüstü bilgisayar", "miktar": Decimal("5"),
         "birim": "adet", "birim_fiyat": Decimal("10000"),
         "kategori": "STRATEJIK"},
    ], tolerans=sifir_alt_tolerans, tarih=test_tarihi)
    servis.siparis_onayla(siparis.siparis_no)
    servis.mal_kabul_kaydet(siparis.siparis_no, [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("5")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet(siparis.siparis_no, "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("5"),
         "birim_fiyat": Decimal("9997")},
    ], tarih=test_tarihi)

    if (kaydedilen_fatura.durum == "BLOKE"
            and kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_DUSUK"]):
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"B11 alt sınır 0: {sonuc}")
    return sonuc


def senaryo_f2():
    """F2 — bozuk dosya: program asla boş başlamaz, veri kaybolmaz.

    Test dosyasına JSON olmayan bir metin yazılır, servis bu dosyayla
    açılmaya çalışılır. DepolamaError gelmeli ve dosyanın üstüne
    yazılmamış olmalı (10a, E61).

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    bozuk_metin = "{bozuk}"
    with open(TEST_VERI_DOSYASI, "w", encoding="utf-8") as dosya:
        dosya.write(bozuk_metin)
    try:
        SatinAlmaServisi(TEST_VERI_DOSYASI)
        hata_geldi = False
    except DepolamaError:
        hata_geldi = True
    with open(TEST_VERI_DOSYASI, "r", encoding="utf-8") as dosya:
        icerik = dosya.read()

    if hata_geldi and icerik == bozuk_metin:
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"F2 bozuk dosya: {sonuc}")
    return sonuc


def senaryo_f3():
    """F3 — veri sürümü: kaydedilen dosyada "veri_surumu": 1 yazar (R5).

    Ortak test verisi kurulur (her işlem dosyaya kaydedilir), sonra
    dosya doğrudan JSON olarak okunur.

    Returns:
        "GEÇTİ" ya da "KALDI".
    """
    baslangic_verisini_kur()
    with open(TEST_VERI_DOSYASI, "r", encoding="utf-8") as dosya:
        ham_veri = json.load(dosya)

    if ham_veri["veri_surumu"] == 1:
        sonuc = "GEÇTİ"
    else:
        sonuc = "KALDI"
    print(f"F3 veri sürümü: {sonuc}")
    return sonuc




def senaryolari_calistir():
    """Bütün senaryoları sırayla çalıştırır ve sonunda özet yazar.

    Her senaryo kendi satırını ("A1 tam eşleşme: GEÇTİ") kendisi yazar;
    bu fonksiyon dönen sonuçları sayar (E54). Yeni senaryo listeye
    parantezsiz eklenir.
    """
    senaryolar = [senaryo_a1, senaryo_b1, senaryo_b2, senaryo_b3, senaryo_b4,
                  senaryo_b5, senaryo_b6, senaryo_b7, senaryo_b8, senaryo_b9,
                  senaryo_b10, senaryo_b11,
                  senaryo_f1, senaryo_f2, senaryo_f3]
    gecenler = 0
    kalanler = 0
    for senaryo in senaryolar:
        senaryo_cagir = senaryo()
        if senaryo_cagir == "GEÇTİ":
            gecenler += 1
        else:
            kalanler += 1
    print(f"Sonuç: {gecenler} geçti, {kalanler} kaldı")


if __name__ == "__main__":
    senaryolari_calistir()