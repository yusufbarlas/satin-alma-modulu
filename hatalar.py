"""Satın Alma Modülü'nün hata sınıfları.

Bütün hatalar SatinAlmaError'dan türer; menü tek bir
except SatinAlmaError ile hepsini yakalayabilir.
"""


class SatinAlmaError(Exception):
    """Projenin bütün hatalarının atası; doğrudan raise edilmez.

    Her hata bir mesaj ve bir hata kodu taşır (E127). Kod, 2 · hatalar
    tablosundaki satırdır (ör. "3b" = sipariş onayla, zaten onaylı).
    Alt sınıflar bu __init__'i kalıtımla kullanır.

    Args:
        mesaj: Kullanıcıya gösterilen açıklama; str(hata) bunu verir.
        kod: Zorunlu hata kodu, ör. "3b"; hata.kod alanında durur.
    """

    def __init__(self, mesaj, kod):
        super().__init__(mesaj)
        self.kod = kod
        

class GecersizGirisError(SatinAlmaError):
    """Girilen değer geçersiz ya da eksik."""


class KayitBulunamadiError(SatinAlmaError):
    """Girilen numarayla kayıt yok."""


class IslemYapilamazError(SatinAlmaError):
    """Kayıt var ama durumu ya da kural bu işleme izin vermiyor."""


class DepolamaError(SatinAlmaError):
    """Veri dosyası okunamadı ya da yazılamadı."""


if __name__ == "__main__":
    try:
        raise IslemYapilamazError("Sipariş zaten onaylı", kod="3b")
    except SatinAlmaError as hata:
        print(f"Yakalanan hata: {hata}")
        print(f"Hata kodu: {hata.kod}")
        print(type(hata))

    try:
        raise GecersizGirisError("Ad boş")
    except TypeError as hata:
        print(f"Kodsuz hata kurulamaz: {hata}")