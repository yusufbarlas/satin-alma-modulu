from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from hatalar import GecersizGirisError
from ayarlar import ISKONTO_TURLERI


def tutara_cevir(metin):
    """Türkçe biçimde yazılmış tutarı Decimal'e çevirir (E105).

    Virgül ondalık ayracıdır (en fazla bir tane); nokta sadece binlik
    ayracıdır: ilk grup 1-3 rakam, sonraki her grup tam 3 rakam. Baştaki
    ve sondaki boşluklar atılır; başta tek bir eksi işareti kabul edilir
    (eksi tutarın reddi servisin işidir). Başka karakter kabul edilmez.

    Örnek: "1.250,50" → Decimal("1250.50"), "1.000" → Decimal("1000"),
    "12.50" → GecersizGirisError.

    Args:
        metin: Kullanıcının yazdığı metin, ör. " 1.250,50 ".

    Returns:
        Tutar (Decimal).

    Raises:
        GecersizGirisError: Metin Türkçe sayı biçimine uymuyorsa.
    """
    temiz_metin = metin.strip()
    eksi_var = False
    if temiz_metin.startswith("-"):
        eksi_var = True
        temiz_metin = temiz_metin[1:]

    if temiz_metin.count(",") > 1:
        raise GecersizGirisError(f"Geçersiz tutar: {metin}", kod="25a")

    virgul_parcalari = temiz_metin.split(",")
    if virgul_parcalari[0] == "":
        raise GecersizGirisError(f"Geçersiz tutar: {metin}", kod="25a")
    if "," in temiz_metin and not virgul_parcalari[1].isdigit():
        raise GecersizGirisError(f"Geçersiz tutar: {metin}", kod="25a")

    gruplar = virgul_parcalari[0].split(".")
    if len(gruplar) == 1 and not gruplar[0].isdigit():
        raise GecersizGirisError(f"Geçersiz tutar: {metin}", kod="25a")
    if len(gruplar) > 1 and (
        not 1 <= len(gruplar[0]) <= 3 or not gruplar[0].isdigit()
    ):
        raise GecersizGirisError(f"Geçersiz tutar: {metin}", kod="25a")
    for grup in gruplar[1:]:
        if len(grup) != 3 or not grup.isdigit():
            raise GecersizGirisError(f"Geçersiz tutar: {metin}", kod="25a")

    noktasiz_metin = temiz_metin.replace(".", "")
    python_bicimi = noktasiz_metin.replace(",", ".")
    try:
        tutar = Decimal(python_bicimi)
    except InvalidOperation as hata:
        raise GecersizGirisError(
            f"Geçersiz tutar: {metin}",
            kod="25a",
        ) from hata
    if eksi_var:
        tutar = -tutar
    return tutar


def tutar_yuvarla(tutar):
    """Tutarı 2 haneye yuvarlar; 5 ve üstü yukarı (ROUND_HALF_UP)."""
    yuvarlanmis_tutar = tutar.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return yuvarlanmis_tutar


def net_fiyat_hesapla(birim_fiyat, iskonto_turu, iskonto_degeri):
    """İskontolu (net) birim fiyatı hesaplar; yuvarlamaz (E30).

    Args:
        birim_fiyat: İskonto öncesi birim fiyat (Decimal), ör. Decimal("100").
        iskonto_turu: "ORAN" (yüzde) ya da "TUTAR" (TL).
        iskonto_degeri: İskonto değeri (Decimal), ör. Decimal("20").

    Returns:
        Net birim fiyat (Decimal), ör. ORAN 20 → Decimal("80").

    Raises:
        GecersizGirisError: İskonto türü ISKONTO_TURLERI'nde yoksa.
    """
    if iskonto_turu not in ISKONTO_TURLERI:
        raise GecersizGirisError(
            f"Geçersiz iskonto türü: {iskonto_turu}",
            kod="13a",
        )
    if iskonto_turu == "ORAN":
        indirim = birim_fiyat * iskonto_degeri / 100
    else:
        indirim = iskonto_degeri
    net_fiyat = birim_fiyat - indirim
    return net_fiyat


def iskontoyu_dogrula(birim_fiyat, iskonto_turu, iskonto_degeri):
    """İskontonun kurala uyduğunu kontrol eder; net fiyat her zaman > 0 kalır (E32).

    Kural: ORAN için 0 ≤ değer < 100, TUTAR için 0 ≤ değer < birim fiyat.
    Kural bozuksa hata fırlatır; uyuyorsa değer döndürmez.

    Args:
        birim_fiyat: İskonto öncesi birim fiyat (Decimal), ör. Decimal("100").
        iskonto_turu: "ORAN" (yüzde) ya da "TUTAR" (TL).
        iskonto_degeri: İskonto değeri (Decimal), ör. Decimal("20").

    Raises:
        GecersizGirisError: Tür ISKONTO_TURLERI'nde yoksa ya da değer
            türünün aralığı dışındaysa (hata tablosu 13a).
    """
    if iskonto_turu not in ISKONTO_TURLERI:
        raise GecersizGirisError(
            f"Geçersiz iskonto türü: {iskonto_turu}",
            kod="13a",
        )
    if iskonto_turu == "ORAN" and not 0 <= iskonto_degeri < 100:
        raise GecersizGirisError(
            f"Geçersiz iskonto oranı: {iskonto_degeri} "
            "(0 ile 100 arasında olmalı, 100 hariç)",
            kod="13a",
        )
    if iskonto_turu == "TUTAR" and not 0 <= iskonto_degeri < birim_fiyat:
        raise GecersizGirisError(
            f"Geçersiz iskonto tutarı: {iskonto_degeri} "
            f"(0 ile birim fiyat {birim_fiyat} arasında olmalı, "
            "birim fiyat hariç)",
            kod="13a",
        )


if __name__ == "__main__":
    denemeler = [
        (Decimal("100"), "ORAN", Decimal("0"), "geçerli"),
        (Decimal("100"), "ORAN", Decimal("99.99"), "geçerli"),
        (Decimal("100"), "ORAN", Decimal("100"), "hata"),
        (Decimal("100"), "ORAN", Decimal("-5"), "hata"),
        (Decimal("100"), "TUTAR", Decimal("0"), "geçerli"),
        (Decimal("100"), "TUTAR", Decimal("99.99"), "geçerli"),
        (Decimal("100"), "TUTAR", Decimal("100"), "hata"),
        (Decimal("100"), "TUTAR", Decimal("120"), "hata"),
        (Decimal("100"), "YUZDE", Decimal("10"), "hata"),
        (Decimal("100"), "oran", Decimal("10"), "hata"),
    ]
    for fiyat, tur, deger, beklenen in denemeler:
        try:
            iskontoyu_dogrula(fiyat, tur, deger)
            sonuc = "geçerli"
            mesaj = ""
        except GecersizGirisError as hata:
            sonuc = "hata"
            mesaj = str(hata)
        durum = "GEÇTİ" if sonuc == beklenen else "KALDI"
        print(f"{durum}: {fiyat} {tur} {deger} → {sonuc} {mesaj}")