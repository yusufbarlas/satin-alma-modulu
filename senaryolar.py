from decimal import Decimal

from ayarlar import TEST_VERI_DOSYASI
from depolama import kaydet, bos_veri_olustur
from servis import SatinAlmaServisi
from modeller import ToleransKopyasi


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


def senaryolari_calistir():
    """Bütün senaryoları sırayla çalıştırır ve sonunda özet yazar.

    Her senaryo kendi satırını ("A1 tam eşleşme: GEÇTİ") kendisi yazar;
    bu fonksiyon dönen sonuçları sayar (E54). Yeni senaryo listeye
    parantezsiz eklenir.
    """
    senaryolar = [senaryo_a1, senaryo_f1]
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