"""Üçlü eşleştirme: sipariş, mal kabul ve fatura kalemlerini karşılaştırır.

Kurallar sapma bulursa Bulgu üretir. Bu dosya sadece hesap yapar;
ekrana yazmaz, dosyaya dokunmaz.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal,ROUND_DOWN

from para import net_fiyat_hesapla


@dataclass
class Bulgu:
    """Bir fatura kaleminde bulunan tek bir sapmanın kaydı.

    Kural sorun bulursa bir Bulgu üretir; sorun yoksa Bulgu oluşmaz.
    Bulgu saklanmaz: fatura BLOKE olunca sadece neden_kodu faturaya
    yazılır, ayrıntı gerektiğinde yeniden hesaplanır.

    Attributes:
        kalem_no: Fatura kaleminin numarası (10, 20, 30...).
        neden_kodu: Sapmanın kodu: "MIKTAR_FAZLA", "FIYAT_YUKSEK"
            veya "FIYAT_DUSUK".
        beklenen: Olması gereken değer. Miktar kuralında kabul edilen
            toplam miktar, fiyat kuralında sipariş net birim fiyatı.
        gerceklesen: Faturada gelen değer. Miktar kuralında faturalanan
            toplam miktar, fiyat kuralında fatura net birim fiyatı.
        izin_verilen_sapma: Toleransın izin verdiği en büyük fark.
            Miktar kuralında tolerans yok, Decimal("0").
        belirleyici_sinir: İzni belirleyen sınır: "YUZDE", "TL_TAVANI"
            veya "KUCUK_FARK". Miktar kuralında None.
    """

    kalem_no: int
    neden_kodu: str
    beklenen: Decimal
    gerceklesen: Decimal
    izin_verilen_sapma: Decimal
    belirleyici_sinir: str | None


@dataclass
class KalemSonucu:
    """Bir fatura kaleminin eşleştirme sonucu.

    Sorunsuz kalem de sonuçta görünür; bulgular listesi boş kalır.
    Saklanmaz, gerektiğinde yeniden hesaplanır.

    Attributes:
        kalem_no: Fatura kaleminin numarası (10, 20, 30...).
        bulgular: O kalemde bulunan Bulgu'lar; boş liste = sorun yok.
    """

    kalem_no: int
    bulgular: list[Bulgu]


@dataclass
class EslestirmeSonucu:
    """Eşleştirmenin tek sonucu: faturanın kalem kalem karnesi.

    Sadece kalem sonuçlarını saklar. Durum, neden kodları ve bulgu
    listesi her çağrıda bunlardan hesaplanır, saklanmaz.

    Attributes:
        kalem_sonuclari: Her fatura kalemi için bir KalemSonucu.
    """

    kalem_sonuclari: list[KalemSonucu]

    def bulgular(self):
        """Bütün kalemlerin bulgularını tek düz listede toplar.

        Returns:
            Kalem sırasıyla Bulgu listesi; sorun yoksa boş liste.
        """
        tum_bulgular = []
        for kalem_sonucu in self.kalem_sonuclari:
            tum_bulgular.extend(kalem_sonucu.bulgular)
        return tum_bulgular

    def neden_kodlari(self):
        """Bulgulardaki neden kodlarını tekrarsız olarak verir.

        Sıra, kodların ilk görüldüğü sıradır; böylece aynı fatura
        her seferinde aynı listeyi verir. BLOKE olunca servis bu
        listeyi faturanın bloke_neden_kodlari alanına yazar.

        Returns:
            Neden kodu listesi; sorun yoksa boş liste.
        """
        kodlar = []
        for bulgu in self.bulgular():
            if bulgu.neden_kodu not in kodlar:
                kodlar.append(bulgu.neden_kodu)
        return kodlar

    def durum(self):
        """Faturanın eşleştirme sonucunu verir.

        Tek kalemde bile Bulgu varsa bütün fatura bloke olur.

        Returns:
            Bulgu yoksa "ONAYLANDI", en az bir Bulgu varsa "BLOKE".
        """
        if not self.bulgular():
            return "ONAYLANDI"
        return "BLOKE"


class EslestirmeKurali(ABC):
    """Bütün eşleştirme kurallarının şablonu.

    Her kural kontrol_et metodunu kendi mantığıyla yazmak zorundadır.
    Bu sınıftan nesne oluşturulamaz (TypeError).
    """

    @abstractmethod
    def kontrol_et(self, siparis_kalemi, fatura_kalemi,
                   kabul_toplami, faturalanan_toplam):
        """Bir fatura kalemini kontrol eder.

        Args:
            siparis_kalemi: Faturalanan sipariş kalemi (SiparisKalemi).
            fatura_kalemi: Kontrol edilen fatura kalemi (FaturaKalemi).
            kabul_toplami: O sipariş kalemi için aktif mal kabullerde
                kabul edilen toplam miktar (Decimal).
            faturalanan_toplam: O sipariş kalemi için aktif faturalarda
                faturalanan toplam miktar (Decimal).

        Returns:
            Bulgu listesi; boş liste = sorun yok.
        """


class MiktarKurali(EslestirmeKurali):
    """Faturalanan miktarın kabul edilen miktarı aşıp aşmadığına bakar.

    Almadığın malın parası ödenmez: tolerans yok, tek birim fazla
    bile MIKTAR_FAZLA verir. Karar toplamlarla verilir.
    """

    def kontrol_et(self, siparis_kalemi, fatura_kalemi,
                   kabul_toplami, faturalanan_toplam):
        """Faturalanan toplam kabul edilen toplamı aşarsa Bulgu verir.

        siparis_kalemi kullanılmaz; imza ortak olduğu için durur.

        Returns:
            Fazla varsa tek Bulgu'lu liste, yoksa boş liste.
        """
        bulgular = []
        if faturalanan_toplam > kabul_toplami:
            bulgular.append(Bulgu(
                kalem_no=fatura_kalemi.kalem_no,
                neden_kodu="MIKTAR_FAZLA",
                beklenen=kabul_toplami,
                gerceklesen=faturalanan_toplam,
                izin_verilen_sapma=Decimal("0"),
                belirleyici_sinir=None,
            ))
        return bulgular


def en_kucuk_siniri_bul(sinirlar):
    """Tanımlı sınırlar arasından en küçüğünü ve adını bulur.

    Değeri None olan sınır tanımsızdır, atlanır. Eşitlikte sözlükte
    önce gelen kazanır. Fiyat kuralı ve üç kova hesabı ortak kullanır.

    Args:
        sinirlar: Sınır adı → Decimal ya da None sözlüğü,
            ör. {"YUZDE": Decimal("5"), "TL_TAVANI": Decimal("2.5")}.

    Returns:
        (en küçük değer, sınırın adı); hiç tanımlı sınır yoksa
        (None, None).
    """
    en_kucuk_anahtar = None
    for anahtar in sinirlar:
        if sinirlar[anahtar] is None:
            continue
        if (en_kucuk_anahtar is None
                or sinirlar[anahtar] < sinirlar[en_kucuk_anahtar]):
            en_kucuk_anahtar = anahtar
    if en_kucuk_anahtar is None:
        return None, None
    return sinirlar[en_kucuk_anahtar], en_kucuk_anahtar


class FiyatKurali(EslestirmeKurali):
    """Fatura net fiyatı ile sipariş net fiyatını karşılaştırır.

    Fatura pahalıysa FIYAT_YUKSEK, ucuzsa FIYAT_DUSUK verir. Üst ve
    alt sınır ayrı hesaplanır; tanımsız (None) sınıra bakılmaz.
    Sınır dahildir: tam sınırdaki fiyat geçer.
    """

    def kontrol_et(self, siparis_kalemi, fatura_kalemi,
                   kabul_toplami, faturalanan_toplam):
        """Fiyat izin verilen aralığın dışındaysa Bulgu verir.

        İzin = en büyüğü(en küçüğü(yüzde izni, TL izni), eşik izni).
        Değerler sipariş kaleminin tolerans kopyasından okunur; TL
        tavanı ve eşik fatura kalemi miktarına bölünür. Net fiyatlar
        yuvarlanmaz. kabul_toplami ve faturalanan_toplam kullanılmaz.

        Returns:
            Sapma varsa tek Bulgu'lu liste, yoksa boş liste.
        """
        siparis_net = net_fiyat_hesapla(siparis_kalemi.birim_fiyat,
                                        siparis_kalemi.iskonto_turu,
                                        siparis_kalemi.iskonto_degeri)
        fatura_net = net_fiyat_hesapla(fatura_kalemi.birim_fiyat,
                                       fatura_kalemi.iskonto_turu,
                                       fatura_kalemi.iskonto_degeri)
        fiyat_ust_yuzde = siparis_kalemi.tolerans.fiyat_ust_yuzde
        fiyat_ust_tl = siparis_kalemi.tolerans.fiyat_ust_tl
        fiyat_alt_yuzde = siparis_kalemi.tolerans.fiyat_alt_yuzde
        fiyat_alt_tl = siparis_kalemi.tolerans.fiyat_alt_tl
        kucuk_fark_esigi = siparis_kalemi.tolerans.kucuk_fark_esigi

        esik_izni = kucuk_fark_esigi / fatura_kalemi.miktar
        bulgular = []

        # Üst sınır: FIYAT_YUKSEK
        if fiyat_ust_yuzde is None:
            yuzde_izni = None
        else:
            yuzde_izni = fiyat_ust_yuzde / 100 * siparis_net

        if fiyat_ust_tl is None:
            tl_izni = None
        else:
            tl_izni = fiyat_ust_tl / fatura_kalemi.miktar

        izin, sinir = en_kucuk_siniri_bul(
            {"YUZDE": yuzde_izni, "TL_TAVANI": tl_izni})

        if (izin is not None) and (izin < esik_izni):
            izin = esik_izni
            sinir = "KUCUK_FARK"

        if (izin is not None) and (fatura_net > siparis_net + izin):
            bulgular.append(Bulgu(
                kalem_no=fatura_kalemi.kalem_no,
                neden_kodu="FIYAT_YUKSEK",
                beklenen=siparis_net,
                gerceklesen=fatura_net,
                izin_verilen_sapma=izin,
                belirleyici_sinir=sinir,
            ))

        # Alt sınır: FIYAT_DUSUK
        if fiyat_alt_yuzde is None:
            yuzde_izni = None
        else:
            yuzde_izni = fiyat_alt_yuzde / 100 * siparis_net

        if fiyat_alt_tl is None:
            tl_izni = None
        else:
            tl_izni = fiyat_alt_tl / fatura_kalemi.miktar

        izin, sinir = en_kucuk_siniri_bul(
            {"YUZDE": yuzde_izni, "TL_TAVANI": tl_izni})

        if (izin is not None) and (izin < esik_izni):
            izin = esik_izni
            sinir = "KUCUK_FARK"

        if (izin is not None) and (fatura_net < siparis_net - izin):
            bulgular.append(Bulgu(
                kalem_no=fatura_kalemi.kalem_no,
                neden_kodu="FIYAT_DUSUK",
                beklenen=siparis_net,
                gerceklesen=fatura_net,
                izin_verilen_sapma=izin,
                belirleyici_sinir=sinir,
            ))

        return bulgular

def kurallari_uygula(siparis, fatura, kabul_toplamlari,
                     faturalanan_toplamlar):
    """Faturanın her kalemini bütün kurallardan geçirir.

    Her fatura kalemi, bağlı olduğu sipariş kalemiyle eşlenir ve
    sırayla MiktarKurali ile FiyatKurali'ndan geçirilir. Toplamları
    servis hesaplayıp verir; bu fonksiyon belge aramaz.

    Args:
        siparis: Faturanın bağlı olduğu sipariş (Siparis).
        fatura: Kontrol edilen fatura (Fatura).
        kabul_toplamlari: Sipariş kalem no → kabul edilen toplam
            miktar sözlüğü, ör. {10: Decimal("100")}.
        faturalanan_toplamlar: Sipariş kalem no → faturalanan toplam
            miktar sözlüğü, ör. {10: Decimal("100")}.

    Returns:
        Her fatura kalemi için bir KalemSonucu içeren EslestirmeSonucu.
    """
    kalem_sonuclari = []
    for fatura_kalemi in fatura.fatura_kalemleri:
        bulgular = []
        for siparis_kalemi in siparis.siparis_kalemleri:
            if siparis_kalemi.kalem_no == fatura_kalemi.siparis_kalem_no:
                kabul_toplami = kabul_toplamlari[siparis_kalemi.kalem_no]
                faturalanan_toplam = faturalanan_toplamlar[
                    siparis_kalemi.kalem_no]
                miktar_bulgulari = MiktarKurali().kontrol_et(
                    siparis_kalemi, fatura_kalemi,
                    kabul_toplami, faturalanan_toplam)
                fiyat_bulgulari = FiyatKurali().kontrol_et(
                    siparis_kalemi, fatura_kalemi,
                    kabul_toplami, faturalanan_toplam)
                bulgular.extend(miktar_bulgulari)
                bulgular.extend(fiyat_bulgulari)
        kalem_sonucu = KalemSonucu(kalem_no=fatura_kalemi.kalem_no,
                                   bulgular=bulgular)
        kalem_sonuclari.append(kalem_sonucu)
    return EslestirmeSonucu(kalem_sonuclari=kalem_sonuclari)



@dataclass
class KovaSonucu:
    """Gelen miktarın üç kovaya ayrılmış hali.

    Belirleyici sınır saklanmaz; servis menüye ve senaryolara verir.

    Attributes:
        kabul: Depoya kabul edilen miktar.
        karantina: Karar bekleyen fazla miktar.
        kapida_red: Kapıda geri çevrilen miktar.
        belirleyici_sinir: Tolerans eşiğini belirleyen sınır:
            "YUZDE", "TL_TAVANI" veya "MIKTAR_TAVANI". Fazla
            teslimat yoksa ya da tolerans tanımsızsa None.
    """

    kabul: Decimal
    karantina: Decimal
    kapida_red: Decimal
    belirleyici_sinir: str | None


def kovalara_ayir(siparis_miktari, gelen_miktar, tolerans, miktar_tavani, birim, net_birim_fiyat, tir_kapida):
    if gelen_miktar <= siparis_miktari:
        kova_sonucu = KovaSonucu(kabul=gelen_miktar , karantina=Decimal("0") , kapida_red=Decimal("0") , belirleyici_sinir=None) 
        return kova_sonucu

    if tolerans.fazla_teslimat_yuzde is None:
        yuzde = None
    else :
        yuzde = tolerans.fazla_teslimat_yuzde / 100 * siparis_miktari

    if tolerans.fazla_teslimat_tl is None:
        tl = None
    else :
        tl = tolerans.fazla_teslimat_tl / net_birim_fiyat

    if miktar_tavani is None:
        tavan_miktari = None
    else : 
        tavan_miktari = miktar_tavani

    izin , sinir = en_kucuk_siniri_bul({"YUZDE": yuzde , "TL_TAVANI": tl , "MIKTAR_TAVANI":tavan_miktari})
    

    if birim == "adet":
        izin = izin.quantize(Decimal("1"), rounding=ROUND_DOWN)
    print(izin , sinir)

    if tolerans.asiri_sinir_yuzde is None:
        yuzde_siniri = None
    else :
         yuzde_siniri = tolerans.asiri_sinir_yuzde / 100 * siparis_miktari

    if tolerans.asiri_sinir_tl is None:
        tl_siniri = None
    else :
        tl_siniri = tolerans.asiri_sinir_tl / net_birim_fiyat

    asiri_sinir , _sinir = en_kucuk_siniri_bul({"YUZDE": yuzde_siniri , "TL_TAVANI": tl_siniri})
    if birim == "adet":
            asiri_sinir = asiri_sinir.quantize(Decimal("1"), rounding=ROUND_DOWN)
    print(asiri_sinir , _sinir)

  
    fazla_miktar_sayisi = gelen_miktar - siparis_miktari
    if fazla_miktar_sayisi < izin:
        kabul_edilen_fazla = fazla_miktar_sayisi
    else:
        kabul_edilen_fazla = izin

    kabul = siparis_miktari + kabul_edilen_fazla

    if fazla_miktar_sayisi >  asiri_sinir:
        kabul_edilen_sinir = asiri_sinir
    else :
        kabul_edilen_sinir = fazla_miktar_sayisi

    karantina_kabul = kabul_edilen_sinir - kabul_edilen_fazla

    
    fazlalik_gönder = fazla_miktar_sayisi - kabul_edilen_sinir
    
    if tir_kapida == True:
       kapida_red = fazlalik_gönder
    else:
        karantina_kabul += fazlalik_gönder
        kapida_red = 0 

    kova_sonucu = KovaSonucu(kabul=kabul , karantina=karantina_kabul , kapida_red=kapida_red , belirleyici_sinir=sinir)
    return kova_sonucu

    

    




        

    
        


    
       
if __name__ == "__main__":
    from modeller import (
        MalKabulDagitimi, FaturaKalemi, SiparisKalemi, ToleransKopyasi,Siparis,Fatura
    )

    # --- Bulgu ve KalemSonucu ---
    fiyat_bulgusu = Bulgu(
        kalem_no=10,
        neden_kodu="FIYAT_YUKSEK",
        beklenen=Decimal("100"),
        gerceklesen=Decimal("103"),
        izin_verilen_sapma=Decimal("2"),
        belirleyici_sinir="YUZDE",
    )
    miktar_bulgusu = Bulgu(
        kalem_no=20,
        neden_kodu="MIKTAR_FAZLA",
        beklenen=Decimal("50"),
        gerceklesen=Decimal("60"),
        izin_verilen_sapma=Decimal("0"),
        belirleyici_sinir=None,
    )
    fiyat_bulgusu1 = Bulgu(
        kalem_no=30,
        neden_kodu="FIYAT_YUKSEK",
        beklenen=Decimal("100"),
        gerceklesen=Decimal("103"),
        izin_verilen_sapma=Decimal("2"),
        belirleyici_sinir="YUZDE",
    )
    bulgu_sonuc = KalemSonucu(kalem_no=10, bulgular=[fiyat_bulgusu1])
    bulgu_sonuc1 = KalemSonucu(kalem_no=30, bulgular=[])

    print(fiyat_bulgusu)
    print(miktar_bulgusu)
    print(fiyat_bulgusu1)
    print(bulgu_sonuc)
    print(bulgu_sonuc1)
    print(len(bulgu_sonuc.bulgular))    # 1
    print(len(bulgu_sonuc1.bulgular))   # 0

    # --- Ortak test verisi: SARF toleransı, sipariş net fiyatı 50 ---
    tolerans = ToleransKopyasi(
        fazla_teslimat_yuzde=Decimal("10"),
        fazla_teslimat_tl=Decimal("1000"),
        asiri_sinir_yuzde=Decimal("25"),
        asiri_sinir_tl=Decimal("5000"),
        fiyat_ust_yuzde=Decimal("5"),
        fiyat_ust_tl=Decimal("500"),
        fiyat_alt_yuzde=Decimal("10"),
        fiyat_alt_tl=Decimal("1000"),
        kucuk_fark_esigi=Decimal("10"),
    )
    SK = SiparisKalemi(
        kalem_no=10,
        malzeme_adi="A4 Kagit",
        miktar=Decimal("100"),
        birim="ADET",
        birim_fiyat=Decimal("50"),
        kategori="SARF",
        tolerans=tolerans,
    )

    # --- MiktarKurali ---
    FK = FaturaKalemi(
        kalem_no=10,
        siparis_kalem_no=10,
        miktar=Decimal("100"),
        birim_fiyat=Decimal("50"),
        mal_kabul_dagitimi=[MalKabulDagitimi("MKB-001", Decimal("100"))],
    )
    KRL = MiktarKurali()
    print(KRL.kontrol_et(SK, FK, Decimal("100"), Decimal("120")))
    # MIKTAR_FAZLA

    # --- FiyatKurali ---
    FK_normal = FaturaKalemi(10, 10, Decimal("100"), Decimal("50"), [])
    FK_sinirda = FaturaKalemi(10, 10, Decimal("100"), Decimal("52.5"), [])
    FK_yuksek = FaturaKalemi(10, 10, Decimal("100"), Decimal("53"), [])
    FK_dusuk = FaturaKalemi(10, 10, Decimal("100"), Decimal("44"), [])
    fiyat_kurali = FiyatKurali()

    print(fiyat_kurali.kontrol_et(SK, FK_normal, Decimal("0"), Decimal("0")))
    # []
    print(fiyat_kurali.kontrol_et(SK, FK_sinirda, Decimal("0"), Decimal("0")))
    # []
    print(fiyat_kurali.kontrol_et(SK, FK_yuksek, Decimal("0"), Decimal("0")))
    # FIYAT_YUKSEK, izin 2.50, YUZDE
    print(fiyat_kurali.kontrol_et(SK, FK_dusuk, Decimal("0"), Decimal("0")))
    # FIYAT_DUSUK, izin 5.0, YUZDE

    siparis = Siparis(siparis_no="SAS-0001" , tedarikci_kodu="TED-0001" , siparis_kalemleri=[SK] , kayit_tarihi="2026-11-02")
    print(siparis)

    fatura = Fatura(fatura_no="FTR-0001" , tedarikci_fatura_no="A-123" , siparis_no="SAS-0001" , fatura_kalemleri=[FK] , kayit_tarihi="2026-11-02")
    print(fatura)

    kabul_toplamlari = {10: Decimal("100")}
    faturalanan_toplamlar = {10: Decimal("100")}
    print(kabul_toplamlari[10])
    print(kurallari_uygula(siparis, fatura, kabul_toplamlari, faturalanan_toplamlar))

    KS= KovaSonucu(kabul=Decimal("110") , karantina=Decimal("15") , kapida_red=Decimal("5") , belirleyici_sinir="YUZDE")
    print(KS)
   
    sonuc = kovalara_ayir(Decimal("100"), Decimal("100"), tolerans, None, "ADET", Decimal("50"), True)
    print(sonuc)

    KA = kovalara_ayir(Decimal("100"), Decimal("130"), tolerans, None, "ADET", Decimal("50"), True)
    print(KA)

    KA1 = kovalara_ayir(Decimal("4"), Decimal("5"), tolerans, None, "adet", Decimal("250"), True)
    print(KA1)

    KA2 = kovalara_ayir(Decimal("100"), Decimal("130"), tolerans, None, "adet", Decimal("50"), True)
    KA3 = kovalara_ayir(Decimal("100"), Decimal("105"), tolerans, None, "adet", Decimal("50"), True)
    print(KA2)
    print(KA3)
