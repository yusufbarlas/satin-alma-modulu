class SatinAlmaError(Exception):
    """Projenin bütün hatalarının atası; doğrudan raise edilmez"""


class GecersizGirisError(SatinAlmaError):
    """Girilen değer geçersiz ya da eksik"""


class KayitBulunamadiError(SatinAlmaError):
    """Girilen numarayla kayıt yok"""


class IslemYapilamazError(SatinAlmaError):
    """Kayıt var ama durumu ya da kural bu işleme izin vermiyor"""


class DepolamaError(SatinAlmaError):
    """Veri dosyası okunamadı ya da yazılamadı"""



if __name__ == "__main__":
    try:
        raise IslemYapilamazError("Sipariş zaten onaylı")
    except SatinAlmaError as hata:
        print(f"Yakalanan hata: {hata}")
        print(hata)
        print(type(hata))


    