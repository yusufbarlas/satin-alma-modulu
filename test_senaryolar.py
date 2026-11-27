"""Satın Alma Modülü'nün test senaryoları (pytest).

Her test kendi geçici klasöründe (tmp_path) temiz veriyle çalışır;
sonuç assert ile, beklenen hatalar pytest.raises ile kontrol edilir
(E119). Senaryolar harf sırasıyla dizilir: v1a A … G, v1b H … M ve
denetim bulguları (B5, B6, B8, B10); senaryo tablosu: D · Karar
kayıtları → madde 8. Çalıştırma: proje klasöründe `pytest -v`.
"""

import json
from decimal import Decimal

import pytest

from depolama import bos_veri_olustur, kaydet
from hatalar import DepolamaError, GecersizGirisError, IslemYapilamazError
from modeller import NedenliMiktar, ToleransKopyasi
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


def test_a2(tmp_path):
    """A2 — fiyat yüksek: k10 103 TL faturalanır, bütün fatura bloke olur.

    SAS-0001'e tam mal kabul (10 / 4), fatura k10 10 × 103, k20 4 × 250.
    İzin 2 TL (YUZDE); k10 FIYAT_YUKSEK, k20 sorunsuz ama tek kalem bütün
    faturayı bloke eder; neden kodu sadece k10'dan gelir (E5, E29).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("103")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]


def test_a3(tmp_path):
    """A3 — miktar fazla: 8 kabul edildi, 10 faturalandı → MIKTAR_FAZLA (E25, R1)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("8")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["MIKTAR_FAZLA"]


def test_a4(tmp_path):
    """A4 — BLOKE → SERBEST: gerekçeyle serbest bırakılır, iz kalır (E36).

    A2'nin adımları (k10 10 × 103 → FIYAT_YUKSEK) kurulur, fatura
    FIYAT_FARKI_ONAYLANDI gerekçesiyle serbest bırakılır. serbest_birak
    değer döndürmez; aynı fatura nesnesinin alanlarına bakılır (E113).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("103")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    servis.serbest_birak(kaydedilen_fatura.fatura_no, "FIYAT_FARKI_ONAYLANDI",
                         tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "SERBEST"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]
    assert kaydedilen_fatura.karar_gerekcesi == "FIYAT_FARKI_ONAYLANDI"
    assert kaydedilen_fatura.karar_tarihi == test_tarihi


def test_a5(tmp_path):
    """A5 — BLOKE → REDDEDILDI → yeni fatura: reddedilen aktif sayılmaz (E27).

    A2 kurulur, FTR-0001 FIYAT_HATALI gerekçesiyle reddedilir. Tedarikçi
    doğru fiyatla yeni fatura (F-1002) keser; 5c engellemez, ONAYLANDI.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    reddedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("103")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    servis.reddet(reddedilen_fatura.fatura_no, "FIYAT_HATALI", tarih=test_tarihi)
    yeni_fatura = servis.fatura_kaydet("SAS-0001", "F-1002", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert reddedilen_fatura.durum == "REDDEDILDI"
    assert reddedilen_fatura.karar_gerekcesi == "FIYAT_HATALI"
    assert yeni_fatura.durum == "ONAYLANDI"
    assert yeni_fatura.bloke_neden_kodlari == []


def test_a6(tmp_path):
    """A6 — fatura önce gelir: önce bekler, mal gelince kendiliğinden onaylanır.

    SAS-0001'e mal kabulsüz fatura F-1001 (10 × 100, 4 × 250) kaydedilir;
    ESLESME_BEKLIYOR olmalı. Mal kabul (10 / 4) kaydedilince servis bekleyen
    faturayı kendisi eşleştirir: fatura ONAYLANDI olur ve mal kabul sonucu
    onu eşleşen faturalarda bildirir (E18, R2).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "ESLESME_BEKLIYOR"
    assert kaydedilen_fatura.bloke_neden_kodlari == []

    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.bloke_neden_kodlari == []
    assert mal_kabul_sonucu.eslesen_faturalar == [kaydedilen_fatura.fatura_no]


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


def test_c1(tmp_path):
    """C1 — tam tolerans sınırında: 10 sipariş, 11 gelir, hepsi kabul (E25).

    SARF test toleransı %10 → izin 1 adet (YUZDE); sınır dahil olduğu için
    karantina ve kapıda red boş kalır. Kovalar saklanan mal kabul
    belgesinden, belirleyici sınır saklanmayan kova sonucundan okunur.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("11")},
    ], tarih=test_tarihi)

    assert mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0].kabul_edilen_miktar == Decimal("11")
    assert mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0].karantinalar == []
    assert mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0].kapida_redler == []
    assert mal_kabul_sonucu.kova_sonuclari[10].belirleyici_sinir == "YUZDE"


def test_c2(tmp_path):
    """C2 — iki eşik arası: 12 gelir → kabul 11, karantina 1 KARAR_BEKLIYOR (E25).

    İzin 1 (%10), aşırı sınır 3 (%30); 1 fazlalık iznin üstünde, aşırı
    sınırın altında kalır.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("12")},
    ], tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("11")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("1")),
    ]
    assert mal_kabul_kalemi.kapida_redler == []


def test_c3(tmp_path):
    """C3 — aşırı sınır üstü, tır kapıda: üstteki 2 adet kapıda geri verilir (E25).

    15 gelir: kabul 11, karantina 2 KARAR_BEKLIYOR (11-13 arası),
    kapıda red 2 ASIRI_TESLIMAT (13'ün üstü).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("15")},
    ], tir_kapida=True, tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("11")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("2")),
    ]
    assert mal_kabul_kalemi.kapida_redler == [
        NedenliMiktar(neden="ASIRI_TESLIMAT", miktar=Decimal("2")),
    ]


def test_c4(tmp_path):
    """C4 — aşırı sınır üstü, tır gitti: üstteki 2 adet IADE_BEKLIYOR olur (E25).

    15 gelir: kabul 11, karantina 2 KARAR_BEKLIYOR + 2 IADE_BEKLIYOR;
    tır gittiği için kapıda red yok.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("15")},
    ], tir_kapida=False, tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("11")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("2")),
        NedenliMiktar(neden="IADE_BEKLIYOR", miktar=Decimal("2")),
    ]
    assert mal_kabul_kalemi.kapida_redler == []


def test_c5(tmp_path):
    """C5 — miktar tavanı belirler: 1.000 sipariş, tavan 50 → kabul 1.050 (E48).

    Yüzde izni 100, TL izni 500 ÷ 0,45 ≈ 1.111; en küçüğü kalemdeki
    miktar tavanı 50. 1.080 gelir: 30'u karantinaya.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0004", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("1080")},
    ], tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("1050")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("30")),
    ]
    assert mal_kabul_sonucu.kova_sonuclari[10].belirleyici_sinir == "MIKTAR_TAVANI"


def test_c6(tmp_path):
    """C6 — kg kalemi: ondalık kalır, aşağı yuvarlanmaz (Karar 2c).

    100 kg sipariş, izin 10 kg; 112,5 kg gelir → kabul 110, karantina 2,5.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0002", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("112.5")},
    ], tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("110")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("2.5")),
    ]


def test_c7(tmp_path):
    """C7 — karantina İADE (kısmi): kalan hesaplanır, belge değişmez.

    C4 kurulur (k10 gelen 15, tır gitti → kabul 11; karantina 2
    KARAR_BEKLIYOR + 2 IADE_BEKLIYOR = 4). 3'ü için İADE kararı verilir.
    Karar ayrı kayıttır; kalan 1 saklanmaz, karantinadakileri_listele
    hesaplar; mal kabul belgesinde karantina hâlâ 4 (Parça 5 Karar 6-7).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("15")},
    ], tir_kapida=False, tarih=test_tarihi)

    karantina_karari = servis.karantina_karari_ver(
        mal_kabul_sonucu.mal_kabul.mal_kabul_no, 10, "IADE", Decimal("3"),
        "FAZLA_KABUL_EDILMEDI", tarih=test_tarihi)

    assert karantina_karari.miktar == Decimal("3")
    assert servis.karantinadakileri_listele()[0].kalan_miktar() == Decimal("1")
    assert mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0].karantina_miktari() == Decimal("4")


def test_c8(tmp_path):
    """C8 — aşırı sınırın tam üstünde: 13 gelir, kapıda red yok (E25).

    Aşırı sınır 3 dahildir: kabul 11, karantina 2 KARAR_BEKLIYOR,
    kapıda red boş.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("13")},
    ], tir_kapida=True, tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("11")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("2")),
    ]
    assert mal_kabul_kalemi.kapida_redler == []


def test_c9(tmp_path):
    """C9 — kapıda yanlış ürün + fazla fatura: kabul 8, fatura 10 → BLOKE (E25, R1).

    k10'a 10 gelir, 2'si yanlış ürün kapıda reddedilir (YANLIS_URUN).
    Fatura 10 adet keser: faturalanan 10 > kabul 8 → MIKTAR_FAZLA.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10"),
         "yanlis_urun_miktari": Decimal("2")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("8")
    assert mal_kabul_kalemi.kapida_redler == [
        NedenliMiktar(neden="YANLIS_URUN", miktar=Decimal("2")),
    ]
    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["MIKTAR_FAZLA"]


def test_c10(tmp_path):
    """C10 — adette aşağı yuvarlama: 4 adet sipariş, 5 gelir (Karar 2c).

    k20 izni 0,4 → 0, aşırı sınır 1,2 → 1 (adet aşağı yuvarlanır):
    kabul 4, karantina 1 KARAR_BEKLIYOR. k20 mal kabulün 2. satırıdır.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("5")},
    ], tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[1]

    assert mal_kabul_kalemi.siparis_kalem_no == 20
    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("4")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("1")),
    ]
    assert mal_kabul_kalemi.kapida_redler == []


def test_d1(tmp_path):
    """D1 — faturalı mal kabul iptali: önce fatura iptal edilmeli (8c, E22, R3).

    A1 kurulur; MKB-0001'e dayanan aktif fatura olduğu için iptal
    IslemYapilamazError verir ve mal kabul iptal edilmemiş kalır.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError):
        servis.mal_kabul_iptal_et(mal_kabul_sonucu.mal_kabul.mal_kabul_no,
                                  "MUKERRER_GIRIS", tarih=test_tarihi)
    assert mal_kabul_sonucu.mal_kabul.iptal_bilgisi.iptal_edildi is False


def test_d2(tmp_path):
    """D2 — iptal edilen numara yeniden girilir (14a engellemez, E37, E53).

    F-1001 yanlış fiyatla (10 × 110) girilir, MIKTAR_FIYAT_YANLIS_GIRILDI
    gerekçesiyle iptal edilir; iptal kartına tarih yazılır. Aynı numara
    doğru fiyatla yeniden girilir: 5c ve 14a iptal edileni saymaz.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    yanlis_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("110")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    servis.fatura_iptal_et(yanlis_fatura.fatura_no,
                           "MIKTAR_FIYAT_YANLIS_GIRILDI", tarih=test_tarihi)
    dogru_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert yanlis_fatura.iptal_bilgisi.iptal_edildi is True
    assert yanlis_fatura.iptal_bilgisi.iptal_tarihi == test_tarihi
    assert dogru_fatura.fatura_no == "FTR-0002"
    assert dogru_fatura.durum == "ONAYLANDI"


def test_d3(tmp_path):
    """D3 — bekleyen faturayla sipariş iptali: önce fatura (11c, E14, R3).

    A6'nın 1. adımı: SAS-0001'e mal kabulsüz fatura (ESLESME_BEKLIYOR).
    Aktif fatura olduğu için sipariş iptali IslemYapilamazError verir.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError):
        servis.siparis_iptal_et("SAS-0001", "VAZGECILDI", tarih=test_tarihi)
    assert servis.siparis_bul("SAS-0001").iptal_bilgisi.iptal_edildi is False


def test_d4(tmp_path):
    """D4 — eksik teslimat, doğru fatura: 8 gelir, 8 faturalanır → ONAYLANDI (R1, R4).

    Eksik miktar (10 − 8 = 2) saklanmaz; sipariş ve mal kabulden hesaplanır.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("8")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("8"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)
    siparis_kalemi = servis.siparis_bul("SAS-0001").siparis_kalemleri[0]
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_fatura.bloke_neden_kodlari == []
    assert siparis_kalemi.miktar - mal_kabul_kalemi.kabul_edilen_miktar == Decimal("2")


def test_d5(tmp_path):
    """D5 — mal gelmedi: bekleyen fatura reddedilir, sipariş iptal edilir (E27, E53).

    A6'nın 1. adımı; fatura MAL_TESLIM_EDILMEDI ile reddedilir. Reddedilen
    fatura aktif sayılmadığı için 11c sipariş iptalini engellemez.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    servis.reddet(kaydedilen_fatura.fatura_no, "MAL_TESLIM_EDILMEDI",
                  tarih=test_tarihi)
    servis.siparis_iptal_et("SAS-0001", "VAZGECILDI", tarih=test_tarihi)
    siparis = servis.siparis_bul("SAS-0001")

    assert kaydedilen_fatura.durum == "REDDEDILDI"
    assert siparis.iptal_bilgisi.iptal_edildi is True
    assert siparis.iptal_bilgisi.iptal_tarihi == test_tarihi


def test_d6(tmp_path):
    """D6 — reddedilen fatura mal kabul iptalini engellemez (8c, Parça 5 (d), E53).

    A3 kurulur (MIKTAR_FAZLA, BLOKE); fatura MIKTAR_HATALI ile reddedilir,
    mal kabul MIKTAR_YANLIS_GIRILDI ile iptal edilir.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("8")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    servis.reddet(kaydedilen_fatura.fatura_no, "MIKTAR_HATALI", tarih=test_tarihi)
    servis.mal_kabul_iptal_et(mal_kabul_sonucu.mal_kabul.mal_kabul_no,
                              "MIKTAR_YANLIS_GIRILDI", tarih=test_tarihi)

    assert mal_kabul_sonucu.mal_kabul.iptal_bilgisi.iptal_edildi is True
    assert mal_kabul_sonucu.mal_kabul.iptal_bilgisi.iptal_tarihi == test_tarihi


def test_d7(tmp_path):
    """D7 — karantina kararı varken mal kabul iptali: iptal edilmez (8d, R3).

    C7 kurulur (karantinaya İADE 3 kararı verilmiş); mal kabul iptali
    IslemYapilamazError verir.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    mal_kabul_sonucu = servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("15")},
    ], tir_kapida=False, tarih=test_tarihi)
    servis.karantina_karari_ver(
        mal_kabul_sonucu.mal_kabul.mal_kabul_no, 10, "IADE", Decimal("3"),
        "FAZLA_KABUL_EDILMEDI", tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError):
        servis.mal_kabul_iptal_et(mal_kabul_sonucu.mal_kabul.mal_kabul_no,
                                  "MUKERRER_GIRIS", tarih=test_tarihi)
    assert mal_kabul_sonucu.mal_kabul.iptal_bilgisi.iptal_edildi is False


def test_e1(tmp_path):
    """E1 — mükerrer fatura: aynı tedarikçinin F-1001'i ikinci kez girilemez (14a, E37).

    A1 kurulur (SAS-0001, TED-0001). SAS-0002 de TED-0001'in; aynı
    numarayla fatura reddedilir, hata mesajı çakışan FTR-0001'i gösterir.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
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

    with pytest.raises(IslemYapilamazError, match="FTR-0001"):
        servis.fatura_kaydet("SAS-0002", "F-1001", [
            {"siparis_kalem_no": 10, "miktar": Decimal("100"),
             "birim_fiyat": Decimal("20")},
        ], tarih=test_tarihi)
    assert len(servis.faturalar) == 1


def test_e2(tmp_path):
    """E2 — ikinci aktif fatura: v1a'da siparişe tek aktif fatura (5c, E2)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
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

    with pytest.raises(IslemYapilamazError):
        servis.fatura_kaydet("SAS-0001", "F-1002", [
            {"siparis_kalem_no": 10, "miktar": Decimal("10"),
             "birim_fiyat": Decimal("100")},
        ], tarih=test_tarihi)
    assert len(servis.faturalar) == 1


def test_e3(tmp_path):
    """E3 — geçersiz iskonto: ORAN 100 kabul edilmez, fatura oluşmaz (13a, E32)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    with pytest.raises(GecersizGirisError):
        servis.fatura_kaydet("SAS-0001", "F-1001", [
            {"siparis_kalem_no": 10, "miktar": Decimal("10"),
             "birim_fiyat": Decimal("100"),
             "iskonto_turu": "ORAN", "iskonto_degeri": Decimal("100")},
        ], tarih=test_tarihi)
    assert servis.faturalar == {}


def test_e4(tmp_path):
    """E4 — miktarı 0 olan kalem: oluşturulmaz, fatura tek kalemle onaylanır (E10)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("0"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert len(kaydedilen_fatura.fatura_kalemleri) == 1
    assert kaydedilen_fatura.fatura_kalemleri[0].siparis_kalem_no == 10
    assert kaydedilen_fatura.durum == "ONAYLANDI"


def test_e5(tmp_path):
    """E5 — DIGER seçildi, not boş: fatura iptal edilmez (12a, E28)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    with pytest.raises(GecersizGirisError):
        servis.fatura_iptal_et(kaydedilen_fatura.fatura_no, "DIGER", notu="",
                               tarih=test_tarihi)
    assert kaydedilen_fatura.iptal_bilgisi.iptal_edildi is False


def test_e6(tmp_path):
    """E6 — onaylı faturayı serbest bırakma: sadece BLOKE serbest bırakılır (7b)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError):
        servis.serbest_birak(kaydedilen_fatura.fatura_no,
                             "FIYAT_FARKI_ONAYLANDI", tarih=test_tarihi)
    assert kaydedilen_fatura.durum == "ONAYLANDI"


def test_e7(tmp_path):
    """E7 — reddedilmiş faturayı eşleştirme: sadece bekleyen eşleşir (6b, E27).

    A5'in 1. adımı: A2 kurulur, FTR-0001 reddedilir; eslestir hata verir.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("103")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)
    servis.reddet(kaydedilen_fatura.fatura_no, "FIYAT_HATALI", tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError):
        servis.eslestir(kaydedilen_fatura.fatura_no)
    assert kaydedilen_fatura.durum == "REDDEDILDI"


def test_e8(tmp_path):
    """E8 — yanlış ürün > gelen: mal kabul oluşmaz, sayaç artmaz (4h, E60, E64)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    with pytest.raises(GecersizGirisError):
        servis.mal_kabul_kaydet("SAS-0001", [
            {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10"),
             "yanlis_urun_miktari": Decimal("12")},
        ], tarih=test_tarihi)
    assert servis.mal_kabuller == {}
    assert servis.sayaclar["MKB"] == 0


def test_e9(tmp_path):
    """E9 — geçersiz kategori: HAMMADDE yok, sipariş oluşmaz (2f, E62, E64)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    with pytest.raises(GecersizGirisError):
        servis.siparis_ac("TED-0001", [
            {"malzeme_adi": "Çelik sac", "miktar": Decimal("10"), "birim": "adet",
             "birim_fiyat": Decimal("100"), "kategori": "HAMMADDE"},
        ], tarih=test_tarihi)
    assert len(servis.siparisler) == 5
    assert servis.sayaclar["SAS"] == 5


def test_e10(tmp_path):
    """E10 — negatif miktar tavanı: sipariş oluşmaz (2g, E64, E77)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    with pytest.raises(GecersizGirisError):
        servis.siparis_ac("TED-0001", [
            {"malzeme_adi": "A4 kağıt", "miktar": Decimal("10"), "birim": "adet",
             "birim_fiyat": Decimal("100"), "kategori": "SARF",
             "miktar_tavani": Decimal("-5")},
        ], tarih=test_tarihi)
    assert len(servis.siparisler) == 5
    assert servis.sayaclar["SAS"] == 5


def test_e11(tmp_path):
    """E11 — serbest bırakmada DIGER, not boş: fatura BLOKE kalır (7c, E28, E76).

    A2 kurulur (FIYAT_YUKSEK, BLOKE).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("103")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    with pytest.raises(GecersizGirisError):
        servis.serbest_birak(kaydedilen_fatura.fatura_no, "DIGER", notu="",
                             tarih=test_tarihi)
    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.karar_gerekcesi is None


def test_e12(tmp_path):
    """E12 — mal kabulde aynı sipariş kalemi iki satırda: kayıt oluşmaz (4i, E126).

    SAS-0001 k10: sipariş 10, tolerans %10. 11 + 11 iki satır kabul
    edilseydi tolerans her satıra ayrı uygulanır, 22 kabul edilirdi.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    with pytest.raises(GecersizGirisError, match="iki kez"):
        servis.mal_kabul_kaydet("SAS-0001", [
            {"siparis_kalem_no": 10, "gelen_miktar": Decimal("11")},
            {"siparis_kalem_no": 10, "gelen_miktar": Decimal("11")},
        ], tarih=test_tarihi)
    assert servis.mal_kabuller == {}
    assert servis.sayaclar["MKB"] == 0


def test_e13(tmp_path):
    """E13 — faturada aynı sipariş kalemi iki satırda: fatura oluşmaz (5i, E126).

    Satırlara bölünen kalemde küçük fark eşiği her satıra ayrı
    uygulanırdı; aynı sipariş kalemi faturada tek satır olur.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)

    with pytest.raises(GecersizGirisError, match="iki kez"):
        servis.fatura_kaydet("SAS-0001", "F-1001", [
            {"siparis_kalem_no": 10, "miktar": Decimal("5"),
             "birim_fiyat": Decimal("104")},
            {"siparis_kalem_no": 10, "miktar": Decimal("5"),
             "birim_fiyat": Decimal("104")},
        ], tarih=test_tarihi)
    assert servis.faturalar == {}
    assert servis.sayaclar["FTR"] == 0


def test_e14(tmp_path):
    """E14 — mükerrer fatura, farklı yazım: boşluk ve harf farkı yok sayılır (14a, E126).

    " f-1001" girilen fatura "F-1001" olarak saklanır. SAS-0002 de
    TED-0001'in; "F-1001 " ile girilen fatura reddedilir.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", " f-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError, match="FTR-0001"):
        servis.fatura_kaydet("SAS-0002", "F-1001 ", [
            {"siparis_kalem_no": 10, "miktar": Decimal("100"),
             "birim_fiyat": Decimal("20")},
        ], tarih=test_tarihi)
    assert kaydedilen_fatura.tedarikci_fatura_no == "F-1001"
    assert len(servis.faturalar) == 1


def test_e15(tmp_path):
    """E15 — birim "Adet " yazılsa da adet kuralı çalışır (E126).

    15 adet sipariş, 17 gelir. SARF ayarı: izin %10 = 1,5 → adette 1;
    aşırı sınır %25 = 3,75 → 3. Kabul 16, karantina 1 KARAR_BEKLIYOR.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    yeni_siparis = servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "Zımba", "miktar": Decimal("15"), "birim": "Adet ",
         "birim_fiyat": Decimal("10"), "kategori": "SARF"},
    ], tarih=test_tarihi)
    servis.siparis_onayla(yeni_siparis.siparis_no)
    mal_kabul_sonucu = servis.mal_kabul_kaydet(yeni_siparis.siparis_no, [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("17")},
    ], tarih=test_tarihi)
    mal_kabul_kalemi = mal_kabul_sonucu.mal_kabul.mal_kabul_kalemleri[0]

    assert yeni_siparis.siparis_kalemleri[0].birim == "adet"
    assert mal_kabul_kalemi.kabul_edilen_miktar == Decimal("16")
    assert mal_kabul_kalemi.karantinalar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("1")),
    ]

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
    """F3 — veri sürümü: kaydedilen dosyada "veri_surumu": 2 yazar (R5, E131).

    Ortak test verisi kurulur (her işlem dosyaya kaydedilir), sonra
    dosya doğrudan JSON olarak okunur.
    """
    veri_dosyasi = tmp_path / "veri.json"
    baslangic_verisini_kur(veri_dosyasi)
    ham_veri = json.loads(veri_dosyasi.read_text(encoding="utf-8"))
    assert ham_veri["veri_surumu"] == 2


def test_f4(tmp_path):
    """F4 — ilk açılış: veri dosyası yokken program boş başlar (E77, E109).

    Dosya yokken servis hata vermeden açılır ve dosya oluşturmaz; bütün
    listeler boş, ilk tedarikçi TED-0001 alır. İlk kayıttan sonra dosya
    oluşur ve içinde "veri_surumu": 2 yazar (4.5, E6, R5, E131).
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
    assert ham_veri["veri_surumu"] == 2


def test_g1(tmp_path):
    """G1 — bekleyen faturalar listesi: fatura önce listede, mal gelince çıkar (İlke 10, E18).

    A6 akışı: mal kabulsüz fatura bekleyenlerde; mal kabulden sonra
    kendiliğinden eşleşir ve listeden çıkar.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("100")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert servis.bekleyen_faturalari_listele() == [kaydedilen_fatura]

    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)

    assert servis.bekleyen_faturalari_listele() == []


def test_g2(tmp_path):
    """G2 — karantinadakiler listesi: C2'de 1 KARAR_BEKLIYOR, C7'den sonra kalan 1 (Parça 5 Karar 8).

    İki ayrı akış, iki ayrı geçici dosya: C2 (12 gelir) ve C7 (C4 + İADE 3).
    C7'de karar önce IADE_BEKLIYOR'dan düşülür: 2 IADE + 1 KARAR → kalan
    1 KARAR_BEKLIYOR.
    """
    test_tarihi = "2026-11-02"
    servis_c2 = baslangic_verisini_kur(tmp_path / "c2.json")
    servis_c2.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("12")},
    ], tarih=test_tarihi)
    karantina_satiri = servis_c2.karantinadakileri_listele()[0]

    assert karantina_satiri.mal_kabul_no == "MKB-0001"
    assert karantina_satiri.mal_kabul_kalem_no == 10
    assert karantina_satiri.kalanlar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("1")),
    ]

    servis_c7 = baslangic_verisini_kur(tmp_path / "c7.json")
    mal_kabul_sonucu = servis_c7.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("15")},
    ], tir_kapida=False, tarih=test_tarihi)
    servis_c7.karantina_karari_ver(
        mal_kabul_sonucu.mal_kabul.mal_kabul_no, 10, "IADE", Decimal("3"),
        "FAZLA_KABUL_EDILMEDI", tarih=test_tarihi)
    karantina_satiri = servis_c7.karantinadakileri_listele()[0]

    assert karantina_satiri.kalanlar == [
        NedenliMiktar(neden="KARAR_BEKLIYOR", miktar=Decimal("1")),
    ]
    assert karantina_satiri.kalan_miktar() == Decimal("1")


def test_g3(tmp_path):
    """G3 — bloke nedeni ayrıntısı: Bulgu yeniden hesaplanır, fatura değişmez (E63).

    A2 kurulur. Ayrıntıda tek Bulgu var: k10, beklenen 100, gerçekleşen
    103, izin 2 (YUZDE), FIYAT_YUKSEK; k20'de Bulgu yok.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("103")},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    ayrinti = servis.fatura_ayrintisini_hesapla(kaydedilen_fatura.fatura_no)
    bulgular = ayrinti.bulgular()

    assert len(bulgular) == 1
    assert bulgular[0].kalem_no == 10
    assert bulgular[0].neden_kodu == "FIYAT_YUKSEK"
    assert bulgular[0].beklenen == Decimal("100")
    assert bulgular[0].gerceklesen == Decimal("103")
    assert bulgular[0].izin_verilen_sapma == Decimal("2")
    assert bulgular[0].belirleyici_sinir == "YUZDE"
    assert ayrinti.kalem_sonuclari[1].bulgular == []
    assert kaydedilen_fatura.durum == "BLOKE"
    assert kaydedilen_fatura.bloke_neden_kodlari == ["FIYAT_YUKSEK"]


# ---------------------------------------------------------------------------
# v1b senaryoları (H-M; D madde 8 → "v1b senaryoları", E125)
# ---------------------------------------------------------------------------

def onayli_talep_kur(servis, test_tarihi):
    """İki kalemli talebi (TLP-0001) açar, onaylar ve döndürür.

    Kalem 10: 10 adet Defter (SARF, tahmini 12); kalem 20: 2 adet Toner
    (SARF, tahmini fiyat yok).
    """
    talep = servis.talep_ac("Muhasebe", [
        {"malzeme_adi": "Defter", "miktar": Decimal("10"), "birim": "adet",
         "kategori": "SARF", "tahmini_birim_fiyat": Decimal("12")},
        {"malzeme_adi": "Toner", "miktar": Decimal("2"), "birim": "adet",
         "kategori": "SARF"},
    ], tarih=test_tarihi)
    servis.talep_onayla(talep.talep_no, tarih=test_tarihi)
    return talep


def sas1_faturasi_kur(servis, test_tarihi, k10_fiyati=Decimal("100")):
    """SAS-0001'e tam mal kabul ve fatura (A1 kalıbı) kaydeder, faturayı döndürür.

    k10_fiyati 100 ise fatura ONAYLANDI ve toplam 2000; 103 ise BLOKE (A2).
    """
    servis.mal_kabul_kaydet("SAS-0001", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
        {"siparis_kalem_no": 20, "gelen_miktar": Decimal("4")},
    ], tarih=test_tarihi)
    return servis.fatura_kaydet("SAS-0001", "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": k10_fiyati},
        {"siparis_kalem_no": 20, "miktar": Decimal("4"),
         "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)


def test_h1(tmp_path):
    """H1 — talep aç ve onayla: TLP-0001 ONAYLANDI (E121)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    acilan_talep = onayli_talep_kur(servis, test_tarihi)

    assert acilan_talep.talep_no == "TLP-0001"
    assert acilan_talep.durum == "ONAYLANDI"
    assert acilan_talep.karar_tarihi == test_tarihi
    assert acilan_talep.talep_kalemleri[0].kalem_no == 10
    assert acilan_talep.talep_kalemleri[1].tahmini_birim_fiyat is None


def test_h2(tmp_path):
    """H2 — reddedilen talepten teklif açılmaz (19b, E121, K2)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    acilan_talep = servis.talep_ac("Muhasebe", [
        {"malzeme_adi": "Defter", "miktar": Decimal("10"), "birim": "adet",
         "kategori": "SARF"},
    ], tarih=test_tarihi)
    servis.talep_reddet(acilan_talep.talep_no, "BUTCE_YOK", tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.teklif_kaydet("TED-0001", [
            {"talep_no": "TLP-0001", "talep_kalem_no": 10,
             "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "19b"
    assert acilan_talep.durum == "REDDEDILDI"
    assert acilan_talep.karar_gerekcesi == "BUTCE_YOK"


def test_h3(tmp_path):
    """H3 — talep_eden boş: 17a; sayaç artmaz."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.talep_ac("  ", [
            {"malzeme_adi": "Defter", "miktar": Decimal("10"), "birim": "adet",
             "kategori": "SARF"},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "17a"
    assert servis.talepler == {}


def test_h4(tmp_path):
    """H4 — onaylı talep yeniden onaylanmaz (18b, T3)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.talep_onayla("TLP-0001", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "18b"


def test_i1(tmp_path):
    """I1 — onaylı talep için iki tedarikçiden teklif: ikisi de ACIK (T4).

    Bağlı kalemde malzeme, birim ve kategori talepten kopyalanır (B6).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)

    abc_teklifi = servis.teklif_kaydet("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tedarikci_teklif_no="ABC-T1", tarih=test_tarihi)
    xyz_teklifi = servis.teklif_kaydet("TED-0002", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("11")},
    ], tarih=test_tarihi)

    assert abc_teklifi.teklif_no == "TKL-0001"
    assert xyz_teklifi.teklif_no == "TKL-0002"
    assert abc_teklifi.durum == "ACIK"
    assert xyz_teklifi.durum == "ACIK"
    assert abc_teklifi.teklif_kalemleri[0].malzeme_adi == "Defter"
    assert abc_teklifi.teklif_kalemleri[0].kategori == "SARF"
    assert abc_teklifi.genel_toplam() == Decimal("120")
    assert xyz_teklifi.genel_toplam() == Decimal("110")


def test_i2(tmp_path):
    """I2 — TASLAK talepten teklif açılmaz (19b, K2)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    servis.talep_ac("Muhasebe", [
        {"malzeme_adi": "Defter", "miktar": Decimal("10"), "birim": "adet",
         "kategori": "SARF"},
    ], tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.teklif_kaydet("TED-0001", [
            {"talep_no": "TLP-0001", "talep_kalem_no": 10,
             "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "19b"
    assert servis.teklifler == {}


def test_i3(tmp_path):
    """I3 — bağ yarım (talep_no var, talep_kalem_no yok): 19d (E120)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.teklif_kaydet("TED-0001", [
            {"talep_no": "TLP-0001", "miktar": Decimal("10"),
             "birim_fiyat": Decimal("12")},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "19d"


def test_i4(tmp_path):
    """I4 — reddedilen tekliften sipariş açılmaz (20b, E122)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    kaydedilen_teklif = servis.teklif_kaydet("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)
    servis.teklif_reddet(kaydedilen_teklif.teklif_no, "DAHA_IYI_TEKLIF_VAR",
                         tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.tekliften_siparis_ac(kaydedilen_teklif.teklif_no,
                                    tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "20b"
    assert kaydedilen_teklif.durum == "REDDEDILDI"


def test_j1(tmp_path):
    """J1 — tekliften sipariş: kalemler, fiyatlar ve bağlar kopyalanır (K1, R4).

    Teklif "siparişe dönüştü" sayılır; bu bir durum değil, hesaplanır.
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    kaydedilen_teklif = servis.teklif_kaydet("TED-0002", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("11"),
         "iskonto_turu": "ORAN", "iskonto_degeri": Decimal("5")},
    ], tarih=test_tarihi)

    yeni_siparis = servis.tekliften_siparis_ac(kaydedilen_teklif.teklif_no,
                                               tarih=test_tarihi)
    siparis_kalemi = yeni_siparis.siparis_kalemleri[0]

    assert yeni_siparis.siparis_no == "SAS-0006"
    assert yeni_siparis.durum == "TASLAK"
    assert yeni_siparis.tedarikci_kodu == "TED-0002"
    assert siparis_kalemi.malzeme_adi == "Defter"
    assert siparis_kalemi.birim_fiyat == Decimal("11")
    assert siparis_kalemi.iskonto_degeri == Decimal("5")
    assert siparis_kalemi.talep_no == "TLP-0001"
    assert siparis_kalemi.talep_kalem_no == 10
    assert siparis_kalemi.teklif_no == "TKL-0001"
    assert siparis_kalemi.teklif_kalem_no == 10
    assert servis.teklif_siparise_donustu_mu("TKL-0001") is True
    assert kaydedilen_teklif.durum == "ACIK"


def test_j2(tmp_path):
    """J2 — aynı talep kalemi için ikinci tekliften sipariş: 20c (K3)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    for tedarikci_kodu in ["TED-0001", "TED-0002"]:
        servis.teklif_kaydet(tedarikci_kodu, [
            {"talep_no": "TLP-0001", "talep_kalem_no": 10,
             "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
        ], tarih=test_tarihi)
    servis.tekliften_siparis_ac("TKL-0001", tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.tekliften_siparis_ac("TKL-0002", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "20c"
    assert servis.teklif_siparise_donustu_mu("TKL-0002") is False


def test_j3(tmp_path):
    """J3 — talepten doğrudan sipariş: bağlar sipariş kaleminde (E120)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)

    yeni_siparis = servis.siparis_ac("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 20,
         "miktar": Decimal("2"), "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)
    siparis_kalemi = yeni_siparis.siparis_kalemleri[0]

    assert siparis_kalemi.malzeme_adi == "Toner"
    assert siparis_kalemi.birim == "adet"
    assert siparis_kalemi.talep_no == "TLP-0001"
    assert siparis_kalemi.talep_kalem_no == 20
    assert siparis_kalemi.teklif_no is None


def test_j4(tmp_path):
    """J4 — talebi bölme: kalem 10 → ABC, kalem 20 → XYZ (E120)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)

    abc_siparisi = servis.siparis_ac("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)
    xyz_siparisi = servis.siparis_ac("TED-0002", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 20,
         "miktar": Decimal("2"), "birim_fiyat": Decimal("250")},
    ], tarih=test_tarihi)

    assert abc_siparisi.siparis_kalemleri[0].talep_kalem_no == 10
    assert xyz_siparisi.siparis_kalemleri[0].talep_kalem_no == 20
    assert abc_siparisi.siparis_kalemleri[0].malzeme_adi == "Defter"
    assert xyz_siparisi.siparis_kalemleri[0].malzeme_adi == "Toner"


def test_j5(tmp_path):
    """J5 — sipariş iptal edilince teklif yeniden açık, talep kalemi serbest (R4)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    servis.teklif_kaydet("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)
    ilk_siparis = servis.tekliften_siparis_ac("TKL-0001", tarih=test_tarihi)

    servis.siparis_iptal_et(ilk_siparis.siparis_no, "VAZGECILDI",
                            tarih=test_tarihi)
    ikinci_siparis = servis.tekliften_siparis_ac("TKL-0001", tarih=test_tarihi)

    assert servis.teklif_siparise_donustu_mu("TKL-0001") is True
    assert ilk_siparis.iptal_bilgisi.iptal_edildi is True
    assert ikinci_siparis.siparis_no == "SAS-0007"
    assert ikinci_siparis.siparis_kalemleri[0].talep_kalem_no == 10


def test_j6(tmp_path):
    """J6 — uçtan uca: talep → teklif → sipariş → mal kabul → fatura → ödeme.

    Her adım doğru; ödemeden sonra kalan borç 0 (E120-E123).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    servis.teklif_kaydet("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)
    yeni_siparis = servis.tekliften_siparis_ac("TKL-0001", tarih=test_tarihi)
    servis.siparis_onayla(yeni_siparis.siparis_no)
    servis.mal_kabul_kaydet(yeni_siparis.siparis_no, [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("10")},
    ], tarih=test_tarihi)
    kaydedilen_fatura = servis.fatura_kaydet(yeni_siparis.siparis_no, "F-2001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)

    kaydedilen_odeme = servis.odeme_kaydet("TED-0001", [
        {"fatura_no": kaydedilen_fatura.fatura_no, "tutar": Decimal("120")},
    ], "HAVALE_EFT", tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "ONAYLANDI"
    assert kaydedilen_odeme.odeme_no == "ODM-0001"
    assert kaydedilen_odeme.toplam() == Decimal("120")
    assert servis.fatura_kalan_borc(kaydedilen_fatura.fatura_no) == Decimal("0")
    assert servis.odeme_bekleyen_faturalari_listele() == []


def test_k1(tmp_path):
    """K1 — ONAYLANDI faturayı tam öde: kalan 0, listeden çıkar (O3, O6)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    kaydedilen_fatura = sas1_faturasi_kur(servis, test_tarihi)
    assert servis.odeme_bekleyen_faturalari_listele() == [kaydedilen_fatura]

    servis.odeme_kaydet("TED-0001", [
        {"fatura_no": "FTR-0001", "tutar": Decimal("2000")},
    ], "HAVALE_EFT", tarih=test_tarihi)

    assert servis.fatura_kalan_borc("FTR-0001") == Decimal("0")
    assert servis.odeme_bekleyen_faturalari_listele() == []


def test_k2(tmp_path):
    """K2 — kısmi ödeme: 2000'in 600'ü; kalan 1400, listede kalır (O3)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    kaydedilen_fatura = sas1_faturasi_kur(servis, test_tarihi)

    servis.odeme_kaydet("TED-0001", [
        {"fatura_no": "FTR-0001", "tutar": Decimal("600")},
    ], "NAKIT", tarih=test_tarihi)

    assert servis.fatura_kalan_borc("FTR-0001") == Decimal("1400")
    assert servis.odeme_bekleyen_faturalari_listele() == [kaydedilen_fatura]


def test_k3(tmp_path):
    """K3 — kalan borcu aşan ödeme: 23e; ödeme oluşmaz (O3, O4)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    sas1_faturasi_kur(servis, test_tarihi)
    servis.odeme_kaydet("TED-0001", [
        {"fatura_no": "FTR-0001", "tutar": Decimal("600")},
    ], "NAKIT", tarih=test_tarihi)

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.odeme_kaydet("TED-0001", [
            {"fatura_no": "FTR-0001", "tutar": Decimal("1400.01")},
        ], "NAKIT", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "23e"
    assert list(servis.odemeler) == ["ODM-0001"]


def test_k4(tmp_path):
    """K4 — BLOKE fatura ödenmez (23c); serbest bırakılınca ödenir (O1)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    kaydedilen_fatura = sas1_faturasi_kur(servis, test_tarihi,
                                          k10_fiyati=Decimal("103"))

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.odeme_kaydet("TED-0001", [
            {"fatura_no": "FTR-0001", "tutar": Decimal("100")},
        ], "NAKIT", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "23c"

    servis.serbest_birak("FTR-0001", "FIYAT_FARKI_ONAYLANDI", tarih=test_tarihi)
    servis.odeme_kaydet("TED-0001", [
        {"fatura_no": "FTR-0001", "tutar": Decimal("2030")},
    ], "NAKIT", tarih=test_tarihi)

    assert kaydedilen_fatura.durum == "SERBEST"
    assert servis.fatura_kalan_borc("FTR-0001") == Decimal("0")


def test_k5(tmp_path):
    """K5 — başka tedarikçinin faturası ödenmez: 23d (O2)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    sas1_faturasi_kur(servis, test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.odeme_kaydet("TED-0002", [
            {"fatura_no": "FTR-0001", "tutar": Decimal("100")},
        ], "NAKIT", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "23d"


def test_k6(tmp_path):
    """K6 — tek ödemeyle aynı tedarikçinin iki faturası kapanır (O2)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    sas1_faturasi_kur(servis, test_tarihi)
    servis.mal_kabul_kaydet("SAS-0002", [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("100")},
    ], tarih=test_tarihi)
    servis.fatura_kaydet("SAS-0002", "F-1002", [
        {"siparis_kalem_no": 10, "miktar": Decimal("100"),
         "birim_fiyat": Decimal("20")},
    ], tarih=test_tarihi)

    kaydedilen_odeme = servis.odeme_kaydet("TED-0001", [
        {"fatura_no": "FTR-0001", "tutar": Decimal("2000")},
        {"fatura_no": "FTR-0002", "tutar": Decimal("2000")},
    ], "HAVALE_EFT", tarih=test_tarihi)

    assert kaydedilen_odeme.toplam() == Decimal("4000")
    assert kaydedilen_odeme.odeme_kalemleri[1].kalem_no == 20
    assert servis.fatura_kalan_borc("FTR-0001") == Decimal("0")
    assert servis.fatura_kalan_borc("FTR-0002") == Decimal("0")


def test_l1(tmp_path):
    """L1 — ödenmiş fatura iptal edilmez (9c); ödeme iptal edilince edilir (O5)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    kaydedilen_fatura = sas1_faturasi_kur(servis, test_tarihi)
    kaydedilen_odeme = servis.odeme_kaydet("TED-0001", [
        {"fatura_no": "FTR-0001", "tutar": Decimal("600")},
    ], "NAKIT", tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.fatura_iptal_et("FTR-0001", "MUKERRER_GIRIS", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "9c"

    servis.odeme_iptal_et(kaydedilen_odeme.odeme_no, "TUTAR_YANLIS_GIRILDI",
                          tarih=test_tarihi)
    servis.fatura_iptal_et("FTR-0001", "MUKERRER_GIRIS", tarih=test_tarihi)

    assert kaydedilen_odeme.iptal_bilgisi.iptal_edildi is True
    assert kaydedilen_fatura.iptal_bilgisi.iptal_edildi is True


def test_l2(tmp_path):
    """L2 — bağlı teklifi olan talep iptal edilmez: 22a (R3)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    servis.teklif_kaydet("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.talep_iptal_et("TLP-0001", "VAZGECILDI", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "22a"


def test_l3(tmp_path):
    """L3 — bağlı siparişi olan teklif iptal edilmez: 22b (R3)."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    servis.teklif_kaydet("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)
    servis.tekliften_siparis_ac("TKL-0001", tarih=test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.teklif_iptal_et("TKL-0001", "MUKERRER_GIRIS", tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "22b"


def test_m1(tmp_path):
    """M1 — sürüm 1 dosyası açılınca sürüm 2'ye dönüştürülür (E120, E131).

    Ortak test verisi kurulur, dosya elle sürüm 1 hâline getirilir (v1a'nın
    yazdığı şekil): talep, teklif, ödeme listeleri ve sayaçları ile sipariş
    kalemlerinin dört bağ alanı silinir. Servis açılınca surum_1den_2ye
    çalışır: sürüm 2, yeni listeler boş, eski belgeler aynen, sayaçlar devam.
    """
    veri_dosyasi = tmp_path / "veri.json"
    baslangic_verisini_kur(veri_dosyasi)
    test_tarihi = "2026-11-02"
    ham_veri = json.loads(veri_dosyasi.read_text(encoding="utf-8"))
    ham_veri["veri_surumu"] = 1
    del ham_veri["talepler"]
    del ham_veri["teklifler"]
    del ham_veri["odemeler"]
    del ham_veri["sayaclar"]["TLP"]
    del ham_veri["sayaclar"]["TKL"]
    del ham_veri["sayaclar"]["ODM"]
    for siparis in ham_veri["siparisler"]:
        for siparis_kalemi in siparis["siparis_kalemleri"]:
            del siparis_kalemi["talep_no"]
            del siparis_kalemi["talep_kalem_no"]
            del siparis_kalemi["teklif_no"]
            del siparis_kalemi["teklif_kalem_no"]
    veri_dosyasi.write_text(json.dumps(ham_veri), encoding="utf-8")

    yeni_servis = SatinAlmaServisi(veri_dosyasi)
    yeni_talep = yeni_servis.talep_ac("Muhasebe", [
        {"malzeme_adi": "Defter", "miktar": Decimal("10"), "birim": "adet",
         "kategori": "SARF"},
    ], tarih=test_tarihi)
    yeni_siparis = yeni_servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("1"), "birim": "adet",
         "birim_fiyat": Decimal("100"), "kategori": "SARF"},
    ], tarih=test_tarihi)

    assert yeni_servis.veri_surumu == 2
    assert yeni_servis.teklifler == {}
    assert yeni_servis.odemeler == {}
    assert len(yeni_servis.siparisler) == 6
    assert yeni_servis.siparis_bul("SAS-0001").siparis_kalemleri[0].malzeme_adi == "A4 kağıt"
    assert yeni_servis.siparis_bul("SAS-0001").siparis_kalemleri[0].talep_no is None
    assert yeni_servis.siparis_bul("SAS-0001").siparis_kalemleri[0].teklif_kalem_no is None
    assert yeni_talep.talep_no == "TLP-0001"
    assert yeni_siparis.siparis_no == "SAS-0006"


def test_m2(tmp_path):
    """M2 — kapat-aç: talep, teklif ve ödeme geri gelir, sayaçlar devam eder (F1 kalıbı)."""
    veri_dosyasi = tmp_path / "veri.json"
    servis = baslangic_verisini_kur(veri_dosyasi)
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    servis.teklif_kaydet("TED-0001", [
        {"talep_no": "TLP-0001", "talep_kalem_no": 10,
         "miktar": Decimal("10"), "birim_fiyat": Decimal("12")},
    ], tarih=test_tarihi)
    sas1_faturasi_kur(servis, test_tarihi)
    servis.odeme_kaydet("TED-0001", [
        {"fatura_no": "FTR-0001", "tutar": Decimal("600")},
    ], "NAKIT", tarih=test_tarihi)

    yeni_servis = SatinAlmaServisi(veri_dosyasi)
    yeni_talep = yeni_servis.talep_ac("Depo", [
        {"malzeme_adi": "Kalem", "miktar": Decimal("1"), "birim": "adet",
         "kategori": "SARF"},
    ], tarih=test_tarihi)

    assert yeni_servis.talep_bul("TLP-0001").durum == "ONAYLANDI"
    assert yeni_servis.teklif_bul("TKL-0001").teklif_kalemleri[0].talep_no == "TLP-0001"
    assert yeni_servis.odeme_bul("ODM-0001").toplam() == Decimal("600")
    assert yeni_servis.fatura_kalan_borc("FTR-0001") == Decimal("1400")
    assert yeni_talep.talep_no == "TLP-0002"


# ---------------------------------------------------------------------------
# Denetim bulguları (E126): B5, B6, B8, B10
# ---------------------------------------------------------------------------

def test_denetim_b5(tmp_path):
    """B5 — sipariş miktarı talep miktarını aşamaz: 20g."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)

    with pytest.raises(IslemYapilamazError) as hata_bilgisi:
        servis.siparis_ac("TED-0001", [
            {"talep_no": "TLP-0001", "talep_kalem_no": 10,
             "miktar": Decimal("11"), "birim_fiyat": Decimal("12")},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "20g"


def test_denetim_b6(tmp_path):
    """B6 — bağlı kalemde malzeme / birim / kategori ayrıca verilmez: 20h ve 19e."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    bagli_kalem = {"talep_no": "TLP-0001", "talep_kalem_no": 10,
                   "miktar": Decimal("10"), "birim_fiyat": Decimal("12"),
                   "birim": "kg"}

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.siparis_ac("TED-0001", [bagli_kalem], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "20h"

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.teklif_kaydet("TED-0001", [bagli_kalem], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "19e"


def test_denetim_b8(tmp_path):
    """B8 — miktar ve fiyat Decimal olmalı: 2d, 4e, 5f."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.siparis_ac("TED-0001", [
            {"malzeme_adi": "A4 kağıt", "miktar": 10, "birim": "adet",
             "birim_fiyat": Decimal("100"), "kategori": "SARF"},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "2d"

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.mal_kabul_kaydet("SAS-0001", [
            {"siparis_kalem_no": 10, "gelen_miktar": "10"},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "4e"

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.fatura_kaydet("SAS-0001", "F-1001", [
            {"siparis_kalem_no": 10, "miktar": Decimal("10"),
             "birim_fiyat": 100.0},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "5f"


def test_denetim_b10(tmp_path):
    """B10 — aynı belgede aynı talep kalemi ikinci satırda: 20i ve 19f."""
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onayli_talep_kur(servis, test_tarihi)
    bagli_kalem = {"talep_no": "TLP-0001", "talep_kalem_no": 10,
                   "miktar": Decimal("5"), "birim_fiyat": Decimal("12")}

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.siparis_ac("TED-0001", [bagli_kalem, bagli_kalem],
                          tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "20i"

    with pytest.raises(GecersizGirisError) as hata_bilgisi:
        servis.teklif_kaydet("TED-0001", [bagli_kalem, bagli_kalem],
                             tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "19f"


def test_denetim_b4(tmp_path, monkeypatch):
    """B4 — kayıt hata verince bellek dosyadan geri yüklenir: 10b.

    Diske yazma sahte kaydet ile bozulur (disk dolu taklidi). Sipariş
    açılırken _kaydet hatayı yakalar, belleği dosyadan yeniden yükler ve
    hatayı iletir: bellekte hayalet sipariş ya da artmış sayaç kalmaz.
    Sahte kaldırılınca açılan sipariş yine SAS-0006 alır (numara boşa
    gitmez).
    """
    servis = baslangic_verisini_kur(tmp_path / "veri.json")
    test_tarihi = "2026-11-02"
    onceki_siparis_sayisi = len(servis.siparisler)
    onceki_sas_sayaci = servis.sayaclar["SAS"]

    def sahte_kaydet(veri, dosya_yolu):
        """Disk dolu taklidi: her çağrıda 10b atar."""
        raise DepolamaError("Kaydedilemedi: disk dolu (test)", kod="10b")

    monkeypatch.setattr("servis.kaydet", sahte_kaydet)

    with pytest.raises(DepolamaError) as hata_bilgisi:
        servis.siparis_ac("TED-0001", [
            {"malzeme_adi": "A4 kağıt", "miktar": Decimal("10"),
             "birim": "adet", "birim_fiyat": Decimal("100"),
             "kategori": "SARF"},
        ], tarih=test_tarihi)
    assert hata_bilgisi.value.kod == "10b"
    assert len(servis.siparisler) == onceki_siparis_sayisi
    assert servis.sayaclar["SAS"] == onceki_sas_sayaci

    monkeypatch.undo()
    siparis = servis.siparis_ac("TED-0001", [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("10"),
         "birim": "adet", "birim_fiyat": Decimal("100"),
         "kategori": "SARF"},
    ], tarih=test_tarihi)
    assert siparis.siparis_no == "SAS-0006"


def test_denetim_b3(tmp_path, monkeypatch):
    """B3 — güvenli yazma: os.replace hata verince eski dosya bozulmaz: 10b.

    Diskte 5 siparişli veri durur; üstüne boş veri yazılmak istenir.
    Geçici dosyayı asıl dosyanın yerine koyan os.replace sahteyle bozulur.
    kaydet hatayı yakalar, geçici dosyayı siler, DepolamaError (10b) atar:
    asıl dosya hatadan önceki içeriğiyle aynı kalır, .tmp diskte kalmaz.
    """
    dosya_yolu = tmp_path / "veri.json"
    baslangic_verisini_kur(dosya_yolu)
    onceki_icerik = dosya_yolu.read_text(encoding="utf-8")

    def sahte_replace(kaynak, hedef):
        """Disk hatası taklidi: her çağrıda OSError atar."""
        raise OSError("Yer değiştirilemedi (test)")

    monkeypatch.setattr("os.replace", sahte_replace)

    with pytest.raises(DepolamaError) as hata_bilgisi:
        kaydet(bos_veri_olustur(), dosya_yolu)
    assert hata_bilgisi.value.kod == "10b"
    assert dosya_yolu.read_text(encoding="utf-8") == onceki_icerik
    assert not (tmp_path / "veri.json.tmp").exists()
