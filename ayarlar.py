"""Satın Alma Modülü'nün sabit değerleri ve listeleri.

Ayar değişince kod değişmez (ilke 6). Bu dosyada hesap,
fonksiyon ve dosya işi yoktur.
"""
from decimal import Decimal

KALEM_NO_ARTISI = 10
VERI_SURUMU = 2
VERI_DOSYASI = "veri.json"
TEST_VERI_DOSYASI = "test_veri.json"
KUCUK_FARK_ESIGI = Decimal("10")

ONEKLER = {
    "tedarikci": "TED",
    "siparis": "SAS",
    "mal_kabul": "MKB",
    "fatura": "FTR",
    "talep": "TLP",
    "teklif": "TKL",
    "odeme": "ODM",
}

ISKONTO_TURLERI = ("ORAN", "TUTAR")
ODEME_YONTEMLERI = ("HAVALE_EFT", "NAKIT")

TOLERANSLAR = {
    "SARF": {
        "fazla_teslimat_yuzde": Decimal("10"),
        "fazla_teslimat_tl": Decimal("1000"),
        "asiri_sinir_yuzde": Decimal("25"),
        "asiri_sinir_tl": Decimal("5000"),
        "fiyat_ust_yuzde": Decimal("5"),
        "fiyat_ust_tl": Decimal("500"),
        "fiyat_alt_yuzde": Decimal("10"),
        "fiyat_alt_tl": Decimal("1000"),
    },
    "STRATEJIK": {
        "fazla_teslimat_yuzde": Decimal("0"),
        "fazla_teslimat_tl": Decimal("0"),
        "asiri_sinir_yuzde": Decimal("5"),
        "asiri_sinir_tl": Decimal("10000"),
        "fiyat_ust_yuzde": Decimal("2"),
        "fiyat_ust_tl": Decimal("1000"),
        "fiyat_alt_yuzde": Decimal("5"),
        "fiyat_alt_tl": Decimal("2000"),
    },
}

KARAR_GEREKCELERI = {
    "SERBEST": {
        "FIYAT_FARKI_ONAYLANDI": "Fiyat farkı onaylandı",
        "TEDARIKCI_INDIRIMI": "Tedarikçi habersiz indirim yaptı",
        "YONETICI_ONAYI": "Yönetici onayı",
        "DIGER": "Diğer",
    },
    "REDDEDILDI": {
        "FIYAT_HATALI": "Faturadaki fiyat hatalı",
        "MIKTAR_HATALI": "Faturadaki miktar hatalı",
        "MAL_TESLIM_EDILMEDI": "Mal teslim edilmedi",
        "DIGER": "Diğer",
    },
    "TALEP_RED": {
        "BUTCE_YOK": "Bütçe yok",
        "IHTIYAC_YOK": "İhtiyaç yok",
        "STOKTA_VAR": "Malzeme stokta var",
        "DIGER": "Diğer",
    },
    "TEKLIF_RED": {
        "DAHA_IYI_TEKLIF_VAR": "Daha iyi bir teklif var",
        "TESLIM_SURESI_UYGUN_DEGIL": "Teslim süresi uygun değil",
        "SARTLAR_UYGUN_DEGIL": "Teklif şartları uygun değil",
        "DIGER": "Diğer",
    },
}

IPTAL_GEREKCELERI = {
    "SIPARIS": {
        "YANLIS_TEDARIKCI_SECILDI": "Yanlış tedarikçi seçildi",
        "MIKTAR_FIYAT_YANLIS_GIRILDI": "Miktar / fiyat yanlış girildi",
        "MUKERRER_GIRIS": "Mükerrer giriş",
        "VAZGECILDI": "Siparişten vazgeçildi",
        "DIGER": "Diğer",
    },
    "MAL_KABUL": {
        "YANLIS_SIPARIS_SECILDI": "Yanlış sipariş seçildi",
        "MIKTAR_YANLIS_GIRILDI": "Miktar yanlış girildi",
        "MUKERRER_GIRIS": "Mükerrer giriş",
        "DIGER": "Diğer",
    },
    "FATURA": {
        "YANLIS_SIPARIS_SECILDI": "Yanlış sipariş seçildi",
        "MIKTAR_FIYAT_YANLIS_GIRILDI": "Miktar / fiyat yanlış girildi",
        "MUKERRER_GIRIS": "Mükerrer giriş",
        "DIGER": "Diğer",
    },
    "TALEP": {
        "MIKTAR_YANLIS_GIRILDI": "Miktar yanlış girildi",
        "MUKERRER_GIRIS": "Mükerrer giriş",
        "VAZGECILDI": "Talepten vazgeçildi",
        "DIGER": "Diğer",
    },
    "TEKLIF": {
        "YANLIS_TEDARIKCI_SECILDI": "Yanlış tedarikçi seçildi",
        "MIKTAR_FIYAT_YANLIS_GIRILDI": "Miktar / fiyat yanlış girildi",
        "MUKERRER_GIRIS": "Mükerrer giriş",
        "DIGER": "Diğer",
    },
    "ODEME": {
        "YANLIS_FATURA_SECILDI": "Yanlış fatura seçildi",
        "TUTAR_YANLIS_GIRILDI": "Tutar yanlış girildi",
        "MUKERRER_GIRIS": "Mükerrer giriş",
        "BANKA_IADESI": "Banka ödemeyi iade etti",
        "DIGER": "Diğer",
    },
}

# v2: KALITE_RET eklenir.
KARANTINA_NEDENLERI = {
    "KARAR_BEKLIYOR": "Fazlalık için karar bekleniyor",
    "IADE_BEKLIYOR": "Tedarikçiye iade bekleniyor",
}

# v2: KALITE_RET eklenir.
KAPIDA_RED_NEDENLERI = {
    "ASIRI_TESLIMAT": "Aşırı sınırın üstündeki fazlalık",
    "YANLIS_URUN": "Yanlış ürün geldi",
}

# v2: "KABUL" grubu eklenir (IHTIYAC_VAR_SIPARIS_REVIZE, DIGER).
KARANTINA_KARAR_GEREKCELERI = {
    "IADE": {
        "FAZLA_KABUL_EDILMEDI": "Fazla miktar kabul edilmedi",
        "DIGER": "Diğer",
    },
}


if __name__ == "__main__":
    deneme = ONEKLER["siparis"]
    print(deneme)

    deneme1 = TOLERANSLAR["SARF"]["fiyat_ust_yuzde"]
    print(deneme1)
    print(type(deneme1))