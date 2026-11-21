"""Satın Alma Modülü'nün test senaryoları (pytest).

Her test kendi geçici klasöründe (tmp_path) temiz veriyle çalışır;
sonuç assert ile, beklenen hatalar pytest.raises ile kontrol edilir
(E119). Çalıştırma: proje klasöründe `pytest -v`.
"""

import json
from decimal import Decimal

import pytest

from depolama import bos_veri_olustur, kaydet
from hatalar import DepolamaError
from modeller import ToleransKopyasi
from servis import SatinAlmaServisi


def baslangic_verisini_kur(dosya_yolu):
    """Senaryolar için temiz başlangıç verisini kurar ve servisi döndürür.

    Verilen dosya boş veriyle temizlenir, o dosyayla yeni servis açılır,
    ortak test verisi (D madde 8) servis metotlarıyla kurulur: 2 tedarikçi,
    5 onaylı sipariş. Toleranslar ayarlar.py'den değil, varsayılan test
    ayarlarından gelir (E47, E55); tarih sabit "2026-11-02" (E53). Her
    test ilk iş bunu kendi tmp_path yoluyla çağırır (E49, E88, E119).

    Args:
        dosya_yolu: Verinin yazılacağı dosya; testte tmp_path / "veri.json".

    Returns:
        SatinAlmaServisi: TED-0001, TED-0002 ve SAS-0001 … SAS-0005
        (ONAYLANDI) kurulu servis.
    """
    bos_veri = bos_veri_olustur()
    kaydet(bos_veri, dosya_yolu)
    servis = SatinAlmaServisi(dosya_yolu)
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


def test_f1(tmp_path):
    """F1 — kapat-aç: kaydedilen belgeler ve sayaçlar dosyadan geri gelir.

    A1 yürütülür (SAS-0001'e mal kabul + fatura), sonra aynı geçici
    dosyayla yeni bir servis açılır (programın kapanıp açılması) ve
    yeni sipariş açılır (E6, E7, E53).
    """
    veri_dosyasi = tmp_path / "veri.json"
    servis = baslangic_verisini_kur(veri_dosyasi)
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

    yeni_servis = SatinAlmaServisi(veri_dosyasi)
    yeni_siparis = yeni_servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("1"), "birim": "adet",
         "birim_fiyat": Decimal("100"), "kategori": "SARF"},
    ], tarih=test_tarihi)

    assert yeni_siparis.siparis_no == "SAS-0006"
    assert "MKB-0001" in yeni_servis.mal_kabuller
    assert "FTR-0001" in yeni_servis.faturalar
    assert yeni_servis.faturalar["FTR-0001"].durum == "ONAYLANDI"
    assert yeni_servis.faturalar["FTR-0001"].kayit_tarihi == test_tarihi


def test_a1(tmp_path):
    """A1 — tam eşleşme: sipariş = mal kabul = fatura, fatura onaylanır.

    SAS-0001'e tam miktarda mal kabul (10 / 4) ve sipariş fiyatlarıyla
    fatura F-1001 (10 × 100, 4 × 250) kaydedilir. Fatura ONAYLANDI olmalı,
    bloke nedeni olmamalı; her kalem MKB-0001'den kendi miktarı kadar
    kapanmalı (E5, E41).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
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

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.bloke_neden_kodlari == []
    assert kaydedilen_fatura.fatura_kalemleri[0].mal_kabul_dagitimi[0].mal_kabul_no == "MKB-0001"
    assert kaydedilen_fatura.fatura_kalemleri[0].mal_kabul_dagitimi[0].miktar == Decimal("10")
    assert kaydedilen_fatura.fatura_kalemleri[1].mal_kabul_dagitimi[0].mal_kabul_no == "MKB-0001"
    assert kaydedilen_fatura.fatura_kalemleri[1].mal_kabul_dagitimi[0].miktar == Decimal("4")


def test_b1(tmp_path):
    """B1 — tam sınırda geçer: izin 2 TL, fatura 102,00 onaylanır (E33).

    Sınır dahildir: fiyat tam sınırdaysa fatura bloke olmaz.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("102.00")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.bloke_neden_kodlari == []


def test_b2(tmp_path):
    """B2 — 1 kuruş üstü: izin 2 TL, fatura 102,01 → FIYAT_YUKSEK (E33)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("102.01")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]


def test_b3(tmp_path):
    """B3 — düşük fiyat: izin 2 TL, fatura 97,99 → FIYAT_DUSUK (E29, E39)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("97.99")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_DUSUK"]


def test_b4(tmp_path):
    """B4 — küçük fark eşiği kurtarır: net 0,45, fatura 0,46 (E40).

    Yüzde izni 0,009; eşik 10 TL ÷ 1.000 = 0,01 → izin 0,01, onaylanır.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0004", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("1000")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0004", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("1000"),
         "birim_fiyat": Decimal("0.46")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.bloke_neden_kodlari == []


def test_b5(tmp_path):
    """B5 — TL tavanı belirler: izin 50 TL ÷ 5 = 10, fatura 10.011 (E33)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0003", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("5")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0003", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("5"),
         "birim_fiyat": Decimal("10011")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]


def test_b6(tmp_path):
    """B6 — tanımsız sınır: fiyat alt sınırı boşsa alta bakılmaz.

    SARF test toleransı, fiyat alt sınırının iki sınırı boş (None).
    100 TL'lik kaleme 90 TL fatura gelir; onaylanır (E29, Karar 2c).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
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

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.bloke_neden_kodlari == []


def test_b7(tmp_path):
    """B7 — net fiyat karşılaştırması: sipariş 0,50 − %10 = 0,45 (E30).

    Fatura iskontosuz 0,45; net fiyatlar eşit, onaylanır.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0004", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("1000")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0004", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("1000"),
         "birim_fiyat": Decimal("0.45")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.bloke_neden_kodlari == []


def test_b8(tmp_path):
    """B8 — ayar değişti, eski sipariş: kalemdeki tolerans kopyası geçer.

    SAS-0001 %2 kopyayla açıldı; fatura 101,50 onaylanır. Aynı fatura,
    üst sınırı %1'e indirilmiş yeni bir siparişte bloke olur (Karar 1b, E47).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
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

    assert eski_fatura.durum == "ONAYLANDI"
    assert yeni_fatura.durum == "BLOKE"
    assert yeni_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]


def test_b9(tmp_path):
    """B9 — kalem yer değiştirme: k10 250, k20 100 faturalanır (E29)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
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

    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK", "FIYAT_DUSUK"]


def test_b10(tmp_path):
    """B10 — tek yuvarlama: 3 × 33,33, ORAN %7 → tutar 92,99 (E35).

    Ara yuvarlama yapılsaydı 93,00 çıkardı.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0005", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("3")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0005", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("3"),
         "birim_fiyat": Decimal("33.33"),
         "iskonto_turu": "ORAN", "iskonto_degeri": Decimal("7")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.fatura_kalemleri[0].tutar() == Decimal("92.99")


def test_b11(tmp_path):
    """B11 — alt sınır 0 ≠ tanımsız: 0 hiç izin yok demektir.

    STRATEJIK test toleransı, fiyat alt sınırı %0 ve 0 TL. İzin küçük fark
    eşiğine çıkar (10 ÷ 5 = 2); 9.997 < 9.998 → FIYAT_DUSUK. Alt sınır
    tanımsız olsaydı onaylanırdı (B6) (E29, E40, Karar 2c).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
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

    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_DUSUK"]


def test_f2(tmp_path):
    """F2 — bozuk dosya: program asla boş başlamaz, veri kaybolmaz.

    Test dosyasına JSON olmayan bir metin yazılır, servis bu dosyayla
    açılmaya çalışılır. DepolamaError gelmeli ve dosyanın üstüne
    yazılmamış olmalı (10a, E61).
    """
    bozuk_metin = "{bozuk}"
    veri_dosyasi = tmp_path / "veri.json"
    veri_dosyasi.write_text(bozuk_metin, encoding="utf-8")
    with pytest.raises(DepolamaError):
        SatinAlmaServisi(veri_dosyasi)
    icerik = veri_dosyasi.read_text(encoding="utf-8")
    assert icerik == bozuk_metin


def test_f3(tmp_path):
    """F3 — veri sürümü: kaydedilen dosyada "veri_surumu": 1 yazar (R5).

    Ortak test verisi kurulur (her işlem dosyaya kaydedilir), sonra
    dosya doğrudan JSON olarak okunur.
    """
    veri_dosyasi = tmp_path / "veri.json"
    baslangic_verisini_kur(veri_dosyasi)
    ham_veri = json.loads(veri_dosyasi.read_text(encoding="utf-8"))
    assert ham_veri["veri_surumu"] == 1

def test_f4(tmp_path):
    """F4 — ilk açılış: veri dosyası yokken program boş başlar (E77, E109).

    Dosya yokken servis hata vermeden açılır ve dosya oluşturmaz; bütün
    listeler boş, ilk tedarikçi TED-0001 alır. İlk kayıttan sonra dosya
    oluşur ve içinde "veri_surumu": 1 yazar (4.5, E6, R5).
    """
    veri_dosyasi = tmp_path / "veri.json"
    servis = SatinAlmaServisi(veri_dosyasi)
    assert not veri_dosyasi.exists()
    assert servis.tedarikciler == {}
    assert servis.siparisler == {}
    assert servis.mal_kabuller == {}
    assert servis.faturalar == {}

    eklenen_tedarikci = servis.tedarikci_ekle("ABC Kırtasiye")
    assert eklenen_tedarikci.tedarikci_kodu == "TED-0001"
    assert veri_dosyasi.exists()
    ham_veri = json.loads(veri_dosyasi.read_text(encoding="utf-8"))
    assert ham_veri["veri_surumu"] == 1
