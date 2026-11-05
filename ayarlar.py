from decimal import Decimal

KALEM_NO_ARTISI = 10
VERI_SURUMU = 1
VERI_DOSYASI = "veri.json"
TEST_VERI_DOSYASI = "test_veri.json"
KUCUK_FARK_ESIGI = Decimal("10")

ONEKLER = {
    "tedarikci": "TED",
    "siparis": "SAS",
    "mal_kabul": "MKB",
    "fatura": "FTR",
}

ISKONTO_TURLERI = ("ORAN", "TUTAR")


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

if __name__ == "__main__":
    deneme = ONEKLER["siparis"]
    print(deneme)

    deneme1 = TOLERANSLAR["SARF"]["fiyat_ust_yuzde"]
    print(deneme1)
    print(type(deneme1))
