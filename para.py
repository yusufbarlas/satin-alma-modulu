from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from hatalar import GecersizGirisError
from ayarlar import ISKONTO_TURLERI


def tutara_cevir(metin):
    """Kullanıcının yazdığı metni Decimal'e çevirir; virgülü kabul eder."""
    noktali_metin = metin.replace(",", ".")
    try:
        tutar = Decimal(noktali_metin)
    except InvalidOperation as hata:
        raise GecersizGirisError(f"Geçersiz tutar: {metin}") from hata
    if not tutar.is_finite():
        raise GecersizGirisError(f"Geçersiz tutar: {metin}")
    return tutar


def tutar_yuvarla(tutar):
    """Tutarı 2 haneye yuvarlar; 5 ve üstü yukarı (ROUND_HALF_UP)."""
    yuvarlanmis_tutar = tutar.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return yuvarlanmis_tutar


def net_fiyat_hesapla(birim_fiyat, iskonto_turu, iskonto_degeri):
    """İskontolu birim fiyatı hesaplar; yuvarlamaz (E30)."""
    if iskonto_turu not in ISKONTO_TURLERI:
        raise GecersizGirisError(f"Geçersiz iskonto türü: {iskonto_turu}")
    if iskonto_turu == "ORAN":
        indirim = birim_fiyat * iskonto_degeri / 100
    else:
        indirim = iskonto_degeri
    net_fiyat = birim_fiyat - indirim
    return net_fiyat
     
          
if __name__ == "__main__":
    deneme1 = tutar_yuvarla(Decimal("2.345"))
    print(deneme1)

