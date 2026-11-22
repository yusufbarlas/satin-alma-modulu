"""Satın alma servisi: belgeleri bellekte tutar, iş kurallarını uygular.

Menü (ana.py) ve senaryolar sadece SatinAlmaServisi'nin metotlarını
çağırır; belgeleri kendileri değiştirmez. Her başarılı işlemden sonra
veri dosyaya kaydedilir (E61).
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from ayarlar import (
    IPTAL_GEREKCELERI,
    KALEM_NO_ARTISI,
    KARANTINA_KARAR_GEREKCELERI,
    KARAR_GEREKCELERI,
    KUCUK_FARK_ESIGI,
    ONEKLER,
    TOLERANSLAR,
)
from depolama import kaydet, yukle
from eslestirme import KovaSonucu, kovalara_ayir, kurallari_uygula
from hatalar import GecersizGirisError, IslemYapilamazError, KayitBulunamadiError
from modeller import (
    Fatura,
    FaturaKalemi,
    KarantinaKarari,
    MalKabul,
    MalKabulDagitimi,
    MalKabulKalemi,
    NedenliMiktar,
    Siparis,
    SiparisKalemi,
    Tedarikci,
    ToleransKopyasi,
)
from para import iskontoyu_dogrula, net_fiyat_hesapla


@dataclass
class MalKabulSonucu:
    """mal_kabul_kaydet'in sonucu; saklanmaz (E95).

    Attributes:
        mal_kabul: Kaydedilen MalKabul.
        kova_sonuclari: {sipariş kalem no: KovaSonucu}; menü belirleyici
            sınırı buradan gösterir.
        eslesen_faturalar: Mal kabulden sonra otomatik eşleşen bekleyen
            faturaların numaraları (R2); yoksa boş liste.
    """

    mal_kabul: MalKabul
    kova_sonuclari: dict[int, KovaSonucu]
    eslesen_faturalar: list[str] = field(default_factory=list)


@dataclass
class KarantinaSatiri:
    """Karantinadakiler listesinin bir satırı; saklanmaz (E118).

    Kalanlar nedene göre gösterilir; verilen kararlar önce
    IADE_BEKLIYOR'dan, sonra KARAR_BEKLIYOR'dan düşülmüştür (C7).

    Attributes:
        mal_kabul_no: Mal kabul numarası, ör. "MKB-0001".
        mal_kabul_kalem_no: Mal kabul kaleminin numarası, ör. 10.
        siparis_no: Mal kabulün siparişi, ör. "SAS-0001".
        kalanlar: Karar bekleyen miktarlar, NedenliMiktar listesi.
    """

    mal_kabul_no: str
    mal_kabul_kalem_no: int
    siparis_no: str
    kalanlar: list[NedenliMiktar]

    def kalan_miktar(self):
        """Bütün nedenlerin kalan toplamı.

        Returns:
            Decimal, ör. 1 IADE_BEKLIYOR + 2 KARAR_BEKLIYOR → Decimal("3").
        """
        toplam = Decimal("0")
        for kalan in self.kalanlar:
            toplam += kalan.miktar
        return toplam


class SatinAlmaServisi:
    """Satın alma sürecinin bütün işlemleri: sipariş, mal kabul, fatura.

    Belgeler numarayla anahtarlı sözlüklerde tutulur (ör. "SAS-0001" →
    Siparis). Her başarılı işlem sonunda _kaydet çağrılır; hata veren
    işlem hiçbir şeyi kaydetmez (E61).
    """

    def __init__(self, dosya_yolu):
        """Veri dosyasını açar ve belgeleri sözlüklere yerleştirir.

        Args:
            dosya_yolu: Veri dosyasının yolu (VERI_DOSYASI ya da
                TEST_VERI_DOSYASI).

        Raises:
            DepolamaError: Dosya bozuksa ya da sürümü uyumsuzsa (10a, 10c).
        """
        self.dosya_yolu = dosya_yolu
        veri = yukle(dosya_yolu)

        self.veri_surumu = veri["veri_surumu"]
        self.sayaclar = veri["sayaclar"]
        self.karantina_kararlari = veri["karantina_kararlari"]

        self.tedarikciler = {}
        for tedarikci in veri["tedarikciler"]:
            self.tedarikciler[tedarikci.tedarikci_kodu] = tedarikci

        self.siparisler = {}
        for siparis in veri["siparisler"]:
            self.siparisler[siparis.siparis_no] = siparis

        self.mal_kabuller = {}
        for mal_kabul in veri["mal_kabuller"]:
            self.mal_kabuller[mal_kabul.mal_kabul_no] = mal_kabul

        self.faturalar = {}
        for fatura in veri["faturalar"]:
            self.faturalar[fatura.fatura_no] = fatura

    def _kaydet(self):
        """Bellekteki bütün veriyi dosyaya yazar.

        Sözlükler listeye çevrilir, depolama.kaydet çağrılır. Her başarılı
        işlemin son adımıdır (E61, E91).

        Raises:
            DepolamaError: Dosya yazılamazsa (10b).
        """
        veri = {
            "veri_surumu": self.veri_surumu,
            "sayaclar": self.sayaclar,
            "tedarikciler": list(self.tedarikciler.values()),
            "siparisler": list(self.siparisler.values()),
            "mal_kabuller": list(self.mal_kabuller.values()),
            "faturalar": list(self.faturalar.values()),
            "karantina_kararlari": self.karantina_kararlari,
        }
        kaydet(veri, self.dosya_yolu)
    
    def _numara_ver(self, onek):
        """Önekin sayacını bir artırır ve sıradaki belge numarasını döndürür.

        Sayaç önce artar, sonra numara üretilir (sayaç 0 ise ilk numara
        "SAS-0001"). Dosyaya yazmaz; işlemi yapan metot sonunda _kaydet'i
        çağırır.

        Args:
            onek: "TED", "SAS", "MKB" ya da "FTR".

        Returns:
            "SAS-0002" biçiminde numara.
        """
        self.sayaclar[onek] += 1
        return f"{onek}-{self.sayaclar[onek]:04d}"


    def _kayit_bul(self, kayitlar, numara):
        """Numarası verilen belgeyi verilen sözlükte bulur.

        Dört belge türü için tek yardımcı: hangi sözlükte aranacağını
        çağıran söyler (ör. self.siparisler).

        Args:
            kayitlar: Numarayla anahtarlı belge sözlüğü.
            numara: Aranan numara, ör. "SAS-0001".

        Returns:
            Bulunan belge nesnesi.

        Raises:
            KayitBulunamadiError: Numara sözlükte yoksa.
        """
        if numara not in kayitlar:
            raise KayitBulunamadiError(f"{numara} numaralı kayıt bulunamadı")
        return kayitlar[numara]

    
    def _aktif_mal_kabuller(self, siparis_no):
        """Siparişin iptal edilmemiş mal kabullerini verir.

        Args:
            siparis_no: Sipariş numarası, ör. "SAS-0001".

        Returns:
            MalKabul listesi, kayıt sırasıyla; yoksa boş liste.
        """
        aktif_mal_kabuller = []
        for mal_kabul in self.mal_kabuller.values():
            if (mal_kabul.siparis_no == siparis_no
                    and not mal_kabul.iptal_bilgisi.iptal_edildi):
                aktif_mal_kabuller.append(mal_kabul)
        return aktif_mal_kabuller

    def _gerekceyi_dogrula(self, gerekce, notu, gecerli_gerekceler):
        """Gerekçe kodunu ve DIGER'in notunu kontrol eder.

        Karar, iptal ve karantina kararı metotlarının ortak yardımcısı
        (E113); hiçbir şeyi değiştirmez.

        Args:
            gerekce: Seçilen gerekçe kodu, ör. "MUKERRER_GIRIS".
            notu: Açıklama; gerekçe DIGER ise zorunlu.
            gecerli_gerekceler: O işlemin gerekçe sözlüğü,
                ör. IPTAL_GEREKCELERI["FATURA"].

        Raises:
            GecersizGirisError: Gerekçe listede yoksa ya da DIGER seçilip
                not boşsa (7c, 12a, 15c).
        """
        if gerekce not in gecerli_gerekceler:
            raise GecersizGirisError(
                f"Geçersiz gerekçe: {gerekce}; geçerli olanlar: "
                f"{', '.join(gecerli_gerekceler)}"
            )
        if gerekce == "DIGER" and (not notu or not notu.strip()):
            raise GecersizGirisError("DIGER seçildiğinde açıklama notu zorunlu")

    def tedarikci_ekle(self, tedarikci_adi, firma_adi=None):
        """Yeni tedarikçiyi kaydeder ve döndürür.

        Kod kullanıcıdan alınmaz, sayaçtan üretilir. Ad kontrolü numara
        alınmadan önce yapılır; hatalı girişte sayaç artmaz.

        Args:
            tedarikci_adi: Zorunlu; boş ya da sadece boşluk olamaz.
            firma_adi: İsteğe bağlı.

        Returns:
            Oluşturulan Tedarikci.

        Raises:
            GecersizGirisError: Ad boşsa.
        """
        if not tedarikci_adi or not tedarikci_adi.strip():
            raise GecersizGirisError("Tedarikçi adı boş olamaz")

        tedarikci_kodu = self._numara_ver(ONEKLER["tedarikci"])
        yeni_tedarikci = Tedarikci(
            tedarikci_kodu=tedarikci_kodu,
            tedarikci_adi=tedarikci_adi.strip(),
            firma_adi=firma_adi,
        )
        self.tedarikciler[tedarikci_kodu] = yeni_tedarikci
        self._kaydet()
        return yeni_tedarikci

    def siparis_ac(self, tedarikci_kodu, kalemler, tolerans=None, tarih=None):
        """Yeni siparişi TASLAK olarak açar, kaydeder ve döndürür.

        Kalem numarasını ve tolerans kopyasını servis verir. Sipariş
        numarası bütün kalemler hatasız kurulduktan sonra alınır; hatalı
        girişte sayaç artmaz. Birim boşlukları atılıp küçük harfle saklanır.

        Args:
            tedarikci_kodu: Kayıtlı tedarikçi kodu, ör. "TED-0001".
            kalemler: Kalem sözlüklerinin listesi. Zorunlu anahtarlar:
                malzeme_adi, miktar, birim, birim_fiyat, kategori.
                İsteğe bağlı: iskonto_turu, iskonto_degeri, miktar_tavani.
            tolerans: Verilirse bütün kalemlere bu ToleransKopyasi
                kopyalanır; None ise kategorinin ayarları kullanılır.
            tarih: "2026-11-02" biçiminde; None ise bugün.

        Returns:
            Oluşturulan Siparis.

        Raises:
            KayitBulunamadiError: Tedarikçi kayıtlı değilse.
            GecersizGirisError: Kalem yoksa (2b), malzeme adı ya da birim
                boşsa (2c), miktar ya da fiyat ≤ 0 ise (2e), kategori
                geçersizse (2f), miktar tavanı negatifse (2g), iskonto
                geçersizse (13a).
        """
        self._kayit_bul(self.tedarikciler, tedarikci_kodu)
        if not kalemler:
            raise GecersizGirisError("Siparişte en az bir kalem olmalı")
        if tarih is None:
            tarih = date.today().isoformat()

        siparis_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            if kalem["kategori"] not in TOLERANSLAR:
                raise GecersizGirisError(
                    f"Geçersiz kategori: {kalem['kategori']}"
                )
            if not kalem["malzeme_adi"] or not kalem["malzeme_adi"].strip():
                raise GecersizGirisError(f"Kalem {kalem_no}: malzeme adı boş olamaz")
            if not kalem["birim"] or not kalem["birim"].strip():
                raise GecersizGirisError(f"Kalem {kalem_no}: birim boş olamaz")
            if kalem["miktar"] <= 0 or kalem["birim_fiyat"] <= 0:
                raise GecersizGirisError(
                    "Miktar ve birim fiyat 0'dan büyük olmalı"
                )
            miktar_tavani = kalem.get("miktar_tavani", None)
            if miktar_tavani is not None and miktar_tavani < 0:
                raise GecersizGirisError("Miktar tavanı negatif olamaz")
            iskontoyu_dogrula(
                kalem["birim_fiyat"],
                kalem.get("iskonto_turu", "ORAN"),
                kalem.get("iskonto_degeri", Decimal("0")),
            )

            if tolerans is not None:
                kalem_toleransi = tolerans
            else:
                kalem_toleransi = ToleransKopyasi(
                    **TOLERANSLAR[kalem["kategori"]],
                    kucuk_fark_esigi=KUCUK_FARK_ESIGI,
                )

            siparis_kalemi = SiparisKalemi(
                kalem_no=kalem_no,
                malzeme_adi=kalem["malzeme_adi"],
                miktar=kalem["miktar"],
                birim=kalem["birim"].strip().lower(),
                birim_fiyat=kalem["birim_fiyat"],
                kategori=kalem["kategori"],
                tolerans=kalem_toleransi,
                iskonto_turu=kalem.get("iskonto_turu", "ORAN"),
                iskonto_degeri=kalem.get("iskonto_degeri", Decimal("0")),
                miktar_tavani=kalem.get("miktar_tavani", None),
            )
            siparis_kalemleri.append(siparis_kalemi)
            kalem_no += KALEM_NO_ARTISI

        siparis_no = self._numara_ver(ONEKLER["siparis"])
        yeni_siparis = Siparis(
            siparis_no=siparis_no,
            tedarikci_kodu=tedarikci_kodu,
            siparis_kalemleri=siparis_kalemleri,
            kayit_tarihi=tarih,
        )
        self.siparisler[siparis_no] = yeni_siparis
        self._kaydet()
        return yeni_siparis

    def siparis_onayla(self, siparis_no):
        """TASLAK siparişi onaylar ve kaydeder.

        Durum elle değil durum_degistir ile değişir; izinli geçiş kontrolü
        orada yapılır. İptal edilmiş sipariş onaylanmaz (E115). Hata
        çıkarsa kaydedilmez.

        Args:
            siparis_no: Onaylanacak siparişin numarası, ör. "SAS-0001".

        Raises:
            KayitBulunamadiError: Numara yoksa (3a).
            IslemYapilamazError: Sipariş iptal edilmişse ya da TASLAK
                değilse (3b).
        """
        siparis = self._kayit_bul(self.siparisler, siparis_no)
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş iptal edilmiş, onaylanamaz"
            )
        siparis.durum_degistir("ONAYLANDI")
        self._kaydet()

    def siparis_bul(self, siparis_no):
        """Siparişi numarasıyla bulur ve döndürür; hiçbir şeyi değiştirmez.

        Menü (ve v3'te API) siparişin satırlarını göstermek için kullanır;
        servisin iç sözlüğüne doğrudan dokunmaz (E100).

        Args:
            siparis_no: Sipariş numarası, ör. "SAS-0001".

        Returns:
            Bulunan Siparis.

        Raises:
            KayitBulunamadiError: Numara yoksa.
        """
        return self._kayit_bul(self.siparisler, siparis_no)

    def mal_kabul_bul(self, mal_kabul_no):
        """Mal kabulü numarasıyla bulur ve döndürür (E112).

        Args:
            mal_kabul_no: Mal kabul numarası, ör. "MKB-0001".

        Returns:
            Bulunan MalKabul.

        Raises:
            KayitBulunamadiError: Numara yoksa (8a, 15a).
        """
        return self._kayit_bul(self.mal_kabuller, mal_kabul_no)

    def fatura_bul(self, fatura_no):
        """Faturayı numarasıyla bulur ve döndürür (E112).

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".

        Returns:
            Bulunan Fatura.

        Raises:
            KayitBulunamadiError: Numara yoksa (7a, 9a, 16a).
        """
        return self._kayit_bul(self.faturalar, fatura_no)

    def tedarikcileri_listele(self):
        """Bütün tedarikçileri kayıt sırasıyla verir (E112).

        Menü sipariş açarken tedarikçi seçtirmek için kullanır.

        Returns:
            Tedarikci listesi; tedarikçi yoksa boş liste.
        """
        return list(self.tedarikciler.values())

    def mal_kabul_kaydet(self, siparis_no, kalemler, tir_kapida=True,
                         mal_kabul_notu=None, tarih=None):
        """Onaylı siparişe mal kabul kaydeder ve sonucu döndürür.

        Her kalemde yanlış ürün gelen miktardan düşülür, kalan miktar
        kovalara_ayir ile kabul / karantina / kapıda red olarak bölünür;
        yanlış ürün kapıda red listesine YANLIS_URUN olarak eklenir (E110).
        Gelen ve yanlış ürünü 0 olan kalem oluşturulmaz. Numara
        kontrollerden sonra alınır; hatalı girişte sayaç artmaz. Kayıttan
        sonra siparişin bekleyen faturaları otomatik eşleştirilir (R2).

        Args:
            siparis_no: Onaylı siparişin numarası, ör. "SAS-0001".
            kalemler: Sözlük listesi. Her sözlükte "siparis_kalem_no" (int)
                ve "gelen_miktar" (Decimal); isteğe bağlı
                "yanlis_urun_miktari" (Decimal, yoksa 0).
            tir_kapida: Aşırı fazlalık kapıda geri verilebilir mi.
            mal_kabul_notu: İsteğe bağlı not.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Returns:
            MalKabulSonucu: kaydedilen MalKabul, {sipariş kalem no:
            KovaSonucu} ve eşleşen fatura numaraları.

        Raises:
            KayitBulunamadiError: Sipariş yoksa (4a).
            IslemYapilamazError: Sipariş onaylı değilse ya da iptal
                edilmişse (4b), siparişin aktif mal kabulü zaten varsa (4c),
                kalem siparişte yoksa (4d).
            GecersizGirisError: Miktar negatifse (4f), yanlış ürün gelen
                miktardan büyükse (4h), hiç kalem oluşmadıysa (4g), aynı
                sipariş kalemi iki kez girildiyse (4i).
        """
        siparis = self._kayit_bul(self.siparisler, siparis_no)
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş iptal edilmiş, mal kabul yapılamaz"
            )
        if siparis.durum != "ONAYLANDI":
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş onaylı değil, mal kabul yapılamaz"
            )
        if self._aktif_mal_kabuller(siparis_no):
            raise IslemYapilamazError(
                f"{siparis_no}: siparişin iptal edilmemiş bir mal kabulü "
                f"zaten var"
            )
        if tarih is None:
            tarih = date.today().isoformat()

        siparis_kalemleri = {}
        for siparis_kalemi in siparis.siparis_kalemleri:
            siparis_kalemleri[siparis_kalemi.kalem_no] = siparis_kalemi

        mal_kabul_kalemleri = []
        kova_sonuclari = {}
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            gelen_miktar = kalem["gelen_miktar"]
            yanlis_urun_miktari = kalem.get("yanlis_urun_miktari", Decimal("0"))

            if gelen_miktar < 0 or yanlis_urun_miktari < 0:
                raise GecersizGirisError("Miktar negatif olamaz")
            if yanlis_urun_miktari > gelen_miktar:
                raise GecersizGirisError(
                    f"Yanlış ürün miktarı ({yanlis_urun_miktari}) gelen "
                    f"miktardan ({gelen_miktar}) büyük olamaz"
                )
            if gelen_miktar == 0 and yanlis_urun_miktari == 0:
                continue
            if kalem["siparis_kalem_no"] not in siparis_kalemleri:
                raise IslemYapilamazError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem siparişte yok"
                )
            if kalem["siparis_kalem_no"] in kova_sonuclari:
                raise GecersizGirisError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem mal kabulde iki kez girilmiş"
                )

            siparis_kalemi = siparis_kalemleri[kalem["siparis_kalem_no"]]
            net_birim_fiyat = net_fiyat_hesapla(
                birim_fiyat=siparis_kalemi.birim_fiyat,
                iskonto_turu=siparis_kalemi.iskonto_turu,
                iskonto_degeri=siparis_kalemi.iskonto_degeri,
            )
            kova = kovalara_ayir(
                siparis_miktari=siparis_kalemi.miktar,
                gelen_miktar=gelen_miktar - yanlis_urun_miktari,
                tolerans=siparis_kalemi.tolerans,
                miktar_tavani=siparis_kalemi.miktar_tavani,
                birim=siparis_kalemi.birim,
                net_birim_fiyat=net_birim_fiyat,
                tir_kapida=tir_kapida,
            )
            kapida_redler = kova.kapida_redler
            if yanlis_urun_miktari > 0:
                kapida_redler = kapida_redler + [
                    NedenliMiktar(neden="YANLIS_URUN", miktar=yanlis_urun_miktari)
                ]

            mal_kabul_kalemleri.append(MalKabulKalemi(
                kalem_no=kalem_no,
                siparis_kalem_no=kalem["siparis_kalem_no"],
                kabul_edilen_miktar=kova.kabul,
                karantinalar=kova.karantinalar,
                kapida_redler=kapida_redler,
            ))
            kova_sonuclari[kalem["siparis_kalem_no"]] = kova
            kalem_no += KALEM_NO_ARTISI

        if not mal_kabul_kalemleri:
            raise GecersizGirisError("Mal kabulde en az bir kalem olmalı")

        mal_kabul_no = self._numara_ver(ONEKLER["mal_kabul"])
        mal_kabul = MalKabul(
            mal_kabul_no=mal_kabul_no,
            siparis_no=siparis_no,
            mal_kabul_kalemleri=mal_kabul_kalemleri,
            kayit_tarihi=tarih,
            mal_kabul_notu=mal_kabul_notu,
        )
        self.mal_kabuller[mal_kabul_no] = mal_kabul
        self._kaydet()

        eslesen_faturalar = []
        for fatura in self.faturalar.values():
            if (fatura.durum == "ESLESME_BEKLIYOR"
                    and not fatura.iptal_bilgisi.iptal_edildi
                    and fatura.siparis_no == siparis_no):
                self.eslestir(fatura.fatura_no)
                eslesen_faturalar.append(fatura.fatura_no)

        return MalKabulSonucu(
            mal_kabul=mal_kabul,
            kova_sonuclari=kova_sonuclari,
            eslesen_faturalar=eslesen_faturalar,
        )

    def fatura_kaydet(self, siparis_no, tedarikci_fatura_no, kalemler,
                      tarih=None):
        """Onaylı siparişe fatura kaydeder; mal geldiyse eşleştirir.

        Miktarı 0 olan kalem oluşturulmaz. Numara kontrollerden sonra
        alınır; hatalı girişte sayaç artmaz. Siparişin aktif mal kabulü
        varsa eslestir çağrılır (o kaydeder); yoksa fatura
        ESLESME_BEKLIYOR olarak bekler, mal gelince eşleşir (R2).

        Args:
            siparis_no: Onaylı siparişin numarası, ör. "SAS-0001".
            tedarikci_fatura_no: Tedarikçinin kendi fatura numarası;
                boşlukları atılıp büyük harfe çevrilerek saklanır ve
                karşılaştırılır (14a).
            kalemler: Sözlük listesi. Her sözlükte "siparis_kalem_no" (int),
                "miktar" ve "birim_fiyat" (Decimal); isteğe bağlı
                "iskonto_turu" ve "iskonto_degeri".
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Returns:
            Oluşturulan Fatura.

        Raises:
            KayitBulunamadiError: Sipariş yoksa (5a).
            IslemYapilamazError: Sipariş onaylı değilse ya da iptal
                edilmişse (5b), siparişin aktif faturası zaten varsa (5c),
                kalem siparişte yoksa (5e), aynı tedarikçinin aynı numaralı
                aktif faturası varsa (14a).
            GecersizGirisError: Tedarikçi fatura no boşsa (5d), miktar
                negatifse ya da fiyat ≤ 0 ise (5g), iskonto geçersizse
                (13a), hiç kalem oluşmadıysa (5h), aynı sipariş kalemi
                iki kez girildiyse (5i).
        """
        siparis = self._kayit_bul(self.siparisler, siparis_no)
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş iptal edilmiş, fatura kaydedilemez"
            )
        if siparis.durum != "ONAYLANDI":
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş onaylı değil, fatura kaydedilemez"
            )
        if not tedarikci_fatura_no or not tedarikci_fatura_no.strip():
            raise GecersizGirisError("Tedarikçi fatura no boş olamaz")
        tedarikci_fatura_no = tedarikci_fatura_no.strip().upper()

        for fatura in self.faturalar.values():
            if fatura.durum == "REDDEDILDI" or fatura.iptal_bilgisi.iptal_edildi:
                continue
            faturanin_siparisi = self._kayit_bul(self.siparisler, fatura.siparis_no)
            if (faturanin_siparisi.tedarikci_kodu == siparis.tedarikci_kodu
                    and fatura.tedarikci_fatura_no.strip().upper()
                    == tedarikci_fatura_no):
                raise IslemYapilamazError(
                    f"Bu tedarikçinin {tedarikci_fatura_no} numaralı faturası "
                    f"zaten {fatura.fatura_no} olarak kayıtlı"
                )
            if fatura.siparis_no == siparis_no:
                raise IslemYapilamazError(
                    f"{siparis_no}: siparişin aktif faturası zaten var "
                    f"({fatura.fatura_no})"
                )

        if tarih is None:
            tarih = date.today().isoformat()

        siparis_kalemleri = {}
        for siparis_kalemi in siparis.siparis_kalemleri:
            siparis_kalemleri[siparis_kalemi.kalem_no] = siparis_kalemi

        fatura_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            if kalem["miktar"] < 0:
                raise GecersizGirisError("Miktar negatif olamaz")
            if kalem["miktar"] == 0:
                continue
            if kalem["birim_fiyat"] <= 0:
                raise GecersizGirisError("Birim fiyat 0'dan büyük olmalı")
            if kalem["siparis_kalem_no"] not in siparis_kalemleri:
                raise IslemYapilamazError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem siparişte yok"
                )
            for onceki_kalem in fatura_kalemleri:
                if onceki_kalem.siparis_kalem_no == kalem["siparis_kalem_no"]:
                    raise GecersizGirisError(
                        f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                        f"kalem faturada iki kez girilmiş"
                    )
            iskontoyu_dogrula(
                kalem["birim_fiyat"],
                kalem.get("iskonto_turu", "ORAN"),
                kalem.get("iskonto_degeri", Decimal("0")),
            )
            fatura_kalemleri.append(FaturaKalemi(
                kalem_no=kalem_no,
                siparis_kalem_no=kalem["siparis_kalem_no"],
                miktar=kalem["miktar"],
                birim_fiyat=kalem["birim_fiyat"],
                mal_kabul_dagitimi=[],
                iskonto_turu=kalem.get("iskonto_turu", "ORAN"),
                iskonto_degeri=kalem.get("iskonto_degeri", Decimal("0")),
            ))
            kalem_no += KALEM_NO_ARTISI

        if not fatura_kalemleri:
            raise GecersizGirisError("Faturada en az bir kalem olmalı")

        fatura_no = self._numara_ver(ONEKLER["fatura"])
        fatura = Fatura(
            fatura_no=fatura_no,
            tedarikci_fatura_no=tedarikci_fatura_no,
            siparis_no=siparis_no,
            fatura_kalemleri=fatura_kalemleri,
            kayit_tarihi=tarih,
        )
        self.faturalar[fatura_no] = fatura

        if self._aktif_mal_kabuller(siparis_no):
            self.eslestir(fatura_no)
        else:
            self._kaydet()
        return fatura
    
    
    
    def _eslestirme_sonucu_hesapla(self, fatura):
        """Faturanın eşleştirme sonucunu hesaplar; hiçbir şeyi değiştirmez.

        Faturadaki her sipariş kalemi için aktif mal kabullerde kabul
        edilen ve aktif faturalarda faturalanan toplamları kurar, sonra
        kurallari_uygula'yı çağırır. Aktif mal kabul: iptal edilmemiş;
        aktif fatura: iptal edilmemiş ve REDDEDILDI olmayan.

        Args:
            fatura: Eşleştirilecek Fatura nesnesi.

        Returns:
            EslestirmeSonucu.
        """
        siparis_bul = self._kayit_bul(self.siparisler, fatura.siparis_no)
        kabul_toplamlari = {}
        faturalanan_toplamlar = {}

        for kalem in fatura.fatura_kalemleri:
            kabul_toplamlari[kalem.siparis_kalem_no] = Decimal("0")
            faturalanan_toplamlar[kalem.siparis_kalem_no] = Decimal("0")

        for deger in self._aktif_mal_kabuller(fatura.siparis_no):
            for kalemler in deger.mal_kabul_kalemleri:
                if kalemler.siparis_kalem_no in kabul_toplamlari:
                    kabul_toplamlari[kalemler.siparis_kalem_no] += (
                        kalemler.kabul_edilen_miktar)

        for deger in self.faturalar.values():
            if (deger.siparis_no == fatura.siparis_no
                    and not deger.iptal_bilgisi.iptal_edildi
                    and deger.durum != "REDDEDILDI"):
                for kalemler in deger.fatura_kalemleri:
                    if kalemler.siparis_kalem_no in faturalanan_toplamlar:
                        faturalanan_toplamlar[kalemler.siparis_kalem_no] += (
                            kalemler.miktar)

        kurallar = kurallari_uygula(
            siparis=siparis_bul,
            fatura=fatura,
            kabul_toplamlari=kabul_toplamlari,
            faturalanan_toplamlar=faturalanan_toplamlar,
        )
        return kurallar
    
    
    def eslestir(self, fatura_no):
        """Faturayı eşleştirir; sonucu faturaya yazar ve kaydeder.

        Önce bütün kontroller, sonra yazma (E114): fatura ESLESME_BEKLIYOR
        ve iptal edilmemiş olmalı, siparişin aktif mal kabulü olmalı.
        Hesabı _eslestirme_sonucu_hesapla yapar. v1a'da siparişin tek aktif
        mal kabulü olduğu için her fatura kalemi o mal kabulden kendi
        miktarı kadar kapanır (dağıtım, E107); dağıtım durumdan önce yazılır,
        6c olursa durum değişmemiş kalır. Menüde yok; fatura_kaydet ve
        mal_kabul_kaydet çağırır (E74).

        Args:
            fatura_no: Eşleştirilecek faturanın numarası, ör. "FTR-0001".

        Returns:
            EslestirmeSonucu.

        Raises:
            KayitBulunamadiError: Fatura yoksa (6a).
            IslemYapilamazError: Fatura ESLESME_BEKLIYOR değilse ya da iptal
                edilmişse (6b), siparişin aktif mal kabulü yoksa (6d).
            GecersizGirisError: Dağıtım fatura miktarını tutmazsa (6c).
        """
        fatura = self._kayit_bul(self.faturalar, fatura_no)
        if fatura.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{fatura_no}: fatura iptal edilmiş, eşleştirilemez"
            )
        if fatura.durum != "ESLESME_BEKLIYOR":
            raise IslemYapilamazError(
                f"{fatura_no}: fatura eşleşme beklemiyor (şu an {fatura.durum})"
            )
        aktif_mal_kabuller = self._aktif_mal_kabuller(fatura.siparis_no)
        if not aktif_mal_kabuller:
            raise IslemYapilamazError(
                f"{fatura_no}: siparişin mal kabulü yok; fatura mal gelince "
                f"kendiliğinden eşleşir"
            )

        sonuc = self._eslestirme_sonucu_hesapla(fatura)
        mal_kabul = aktif_mal_kabuller[0]
        for kalem in fatura.fatura_kalemleri:
            kalem.dagitimi_yaz([
                MalKabulDagitimi(
                    mal_kabul_no=mal_kabul.mal_kabul_no,
                    miktar=kalem.miktar,
                )
            ])
        fatura.durum_degistir(sonuc.durum())
        fatura.bloke_neden_kodlari = sonuc.neden_kodlari()
        self._kaydet()
        return sonuc

    def serbest_birak(self, fatura_no, gerekce, notu=None, tarih=None):
        """BLOKE faturayı gerekçeyle serbest bırakır (BLOKE → SERBEST).

        Bloke nedenleri faturada kalır; karar gerekçesi, notu ve tarihi
        faturaya yazılır (E113). Değer döndürmez.

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".
            gerekce: KARAR_GEREKCELERI["SERBEST"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Fatura yoksa (7a).
            IslemYapilamazError: Fatura BLOKE değilse (7b).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (7c).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        fatura = self._kayit_bul(self.faturalar, fatura_no)
        if fatura.durum != "BLOKE":
            raise IslemYapilamazError(
                f"{fatura_no}: sadece BLOKE fatura serbest bırakılabilir "
                f"(şu an {fatura.durum})"
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARAR_GEREKCELERI["SERBEST"],
        )
        fatura.durum_degistir("SERBEST")
        fatura.karar_gerekcesi = gerekce
        fatura.karar_notu = notu
        fatura.karar_tarihi = tarih
        self._kaydet()

    def reddet(self, fatura_no, gerekce, notu=None, tarih=None):
        """Faturayı gerekçeyle reddeder (BLOKE / ESLESME_BEKLIYOR → REDDEDILDI).

        Reddedilen fatura aktif sayılmaz: siparişe yeni fatura girilebilir,
        mal kabul ve sipariş iptal edilebilir (E27). Karar gerekçesi, notu
        ve tarihi faturaya yazılır (E113). Değer döndürmez.

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".
            gerekce: KARAR_GEREKCELERI["REDDEDILDI"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Fatura yoksa (7a).
            IslemYapilamazError: Fatura BLOKE ya da ESLESME_BEKLIYOR
                değilse (7b).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (7c).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        fatura = self._kayit_bul(self.faturalar, fatura_no)
        if fatura.durum not in ("BLOKE", "ESLESME_BEKLIYOR"):
            raise IslemYapilamazError(
                f"{fatura_no}: sadece BLOKE ya da ESLESME_BEKLIYOR fatura "
                f"reddedilebilir (şu an {fatura.durum})"
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARAR_GEREKCELERI["REDDEDILDI"],
        )
        fatura.durum_degistir("REDDEDILDI")
        fatura.karar_gerekcesi = gerekce
        fatura.karar_notu = notu
        fatura.karar_tarihi = tarih
        self._kaydet()

    def fatura_iptal_et(self, fatura_no, gerekce, notu=None, tarih=None):
        """Faturayı gerekçeyle iptal eder; iptal geri alınmaz.

        Fatura silinmez, iptal_bilgisi kartına yazılır; durum değişmez.
        Zincirin son halkası olduğu için önce o iptal edilir (R3). İptal
        edilen fatura 5c, 14a ve R2'de sayılmaz. Değer döndürmez.

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".
            gerekce: IPTAL_GEREKCELERI["FATURA"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Fatura yoksa (9a).
            IslemYapilamazError: Fatura zaten iptal edilmişse (9b).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (12a).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        fatura = self._kayit_bul(self.faturalar, fatura_no)
        if fatura.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(f"{fatura_no}: fatura zaten iptal edilmiş")
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["FATURA"],
        )
        fatura.iptal_bilgisi.iptal_et(gerekce, notu, tarih)
        self._kaydet()

    def mal_kabul_iptal_et(self, mal_kabul_no, gerekce, notu=None, tarih=None):
        """Mal kabulü gerekçeyle iptal eder; iptal geri alınmaz.

        Zincir tersten çözülür (R3): mal kabule dayanan aktif fatura ya da
        bu mal kabule ait karantina kararı varsa iptal edilmez. İptal edilen
        mal kabul 4c'de sayılmaz; aynı siparişe yeni mal kabul girilebilir.
        Değer döndürmez.

        Args:
            mal_kabul_no: Mal kabul numarası, ör. "MKB-0001".
            gerekce: IPTAL_GEREKCELERI["MAL_KABUL"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Mal kabul yoksa (8a).
            IslemYapilamazError: Zaten iptal edilmişse (8b), dayanan aktif
                fatura varsa (8c), karantina kararı varsa (8d).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (12a).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        mal_kabul = self._kayit_bul(self.mal_kabuller, mal_kabul_no)
        if mal_kabul.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{mal_kabul_no}: mal kabul zaten iptal edilmiş"
            )
        for fatura in self.faturalar.values():
            if fatura.durum == "REDDEDILDI" or fatura.iptal_bilgisi.iptal_edildi:
                continue
            for kalem in fatura.fatura_kalemleri:
                for dagitim in kalem.mal_kabul_dagitimi:
                    if dagitim.mal_kabul_no == mal_kabul_no:
                        raise IslemYapilamazError(
                            f"{mal_kabul_no}: bu mal kabule dayanan aktif "
                            f"fatura var ({fatura.fatura_no}), önce faturayı "
                            f"iptal edin"
                        )
        for karar in self.karantina_kararlari:
            if karar.mal_kabul_no == mal_kabul_no:
                raise IslemYapilamazError(
                    f"{mal_kabul_no}: mal kabulün {karar.mal_kabul_kalem_no}. "
                    f"kalemine karantina kararı verilmiş, iptal edilemez"
                )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["MAL_KABUL"],
        )
        mal_kabul.iptal_bilgisi.iptal_et(gerekce, notu, tarih)
        self._kaydet()

    def siparis_iptal_et(self, siparis_no, gerekce, notu=None, tarih=None):
        """Siparişi gerekçeyle iptal eder; iptal geri alınmaz.

        Zincirin ilk halkası olduğu için en son iptal edilir (R3):
        iptal edilmemiş mal kabulü ya da aktif faturası varsa iptal
        edilmez. Durum değişmez; iptal edilen siparişle onay, mal kabul ve
        fatura yapılamaz (E115). Değer döndürmez.

        Args:
            siparis_no: Sipariş numarası, ör. "SAS-0001".
            gerekce: IPTAL_GEREKCELERI["SIPARIS"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Sipariş yoksa (11a).
            IslemYapilamazError: Zaten iptal edilmişse (11b), aktif mal
                kabulü ya da aktif faturası varsa (11c).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (12a).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        siparis = self._kayit_bul(self.siparisler, siparis_no)
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(f"{siparis_no}: sipariş zaten iptal edilmiş")
        if self._aktif_mal_kabuller(siparis_no):
            raise IslemYapilamazError(
                f"{siparis_no}: siparişin iptal edilmemiş mal kabulü var, "
                f"önce mal kabulü iptal edin"
            )
        for fatura in self.faturalar.values():
            if fatura.durum == "REDDEDILDI" or fatura.iptal_bilgisi.iptal_edildi:
                continue
            if fatura.siparis_no == siparis_no:
                raise IslemYapilamazError(
                    f"{siparis_no}: siparişin aktif faturası var "
                    f"({fatura.fatura_no}), önce faturayı iptal edin"
                )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["SIPARIS"],
        )
        siparis.iptal_bilgisi.iptal_et(gerekce, notu, tarih)
        self._kaydet()

    def karantina_karari_ver(self, mal_kabul_no, mal_kabul_kalem_no, karar,
                             miktar, gerekce, notu=None, tarih=None):
        """Karantinadaki mal için karar kaydeder ve kaydı döndürür.

        Mal kabul belgesi değişmez; karar ayrı KarantinaKarari olarak
        listeye eklenir. Kalan karantina saklanmaz, hesaplanır: kalemin
        karantina toplamı − bu kaleme verilmiş kararların toplamı. Karar
        kısmi olabilir. v1a'da karar sadece "IADE" (v2: "KABUL").

        Args:
            mal_kabul_no: Mal kabul numarası, ör. "MKB-0001".
            mal_kabul_kalem_no: Mal kabul kaleminin numarası, ör. 10.
            karar: KARANTINA_KARAR_GEREKCELERI anahtarı, ör. "IADE".
            miktar: Karar verilen miktar (Decimal, > 0, ≤ kalan).
            gerekce: KARANTINA_KARAR_GEREKCELERI[karar] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Returns:
            Oluşturulan KarantinaKarari.

        Raises:
            KayitBulunamadiError: Mal kabul yoksa (15a).
            IslemYapilamazError: Mal kabul iptal edilmişse, kalem yoksa ya da
                kalemde karar bekleyen karantina kalmadıysa (15b).
            GecersizGirisError: Karar türü geçersizse, miktar ≤ 0 ya da
                kalandan fazlaysa, gerekçe geçersizse ya da DIGER notsuzsa
                (15c, E116).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        mal_kabul = self._kayit_bul(self.mal_kabuller, mal_kabul_no)
        if mal_kabul.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{mal_kabul_no}: mal kabul iptal edilmiş, karar verilemez"
            )
        if karar not in KARANTINA_KARAR_GEREKCELERI:
            raise GecersizGirisError(
                f"Geçersiz karar: {karar}; geçerli olanlar: "
                f"{', '.join(KARANTINA_KARAR_GEREKCELERI)}"
            )

        bulunan_kalem = None
        for kalem in mal_kabul.mal_kabul_kalemleri:
            if kalem.kalem_no == mal_kabul_kalem_no:
                bulunan_kalem = kalem
        if bulunan_kalem is None:
            raise IslemYapilamazError(
                f"{mal_kabul_no}: {mal_kabul_kalem_no} numaralı kalem yok"
            )

        karar_toplami = Decimal("0")
        for onceki in self.karantina_kararlari:
            if (onceki.mal_kabul_no == mal_kabul_no
                    and onceki.mal_kabul_kalem_no == mal_kabul_kalem_no):
                karar_toplami += onceki.miktar
        kalan = bulunan_kalem.karantina_miktari() - karar_toplami
        if kalan == 0:
            raise IslemYapilamazError(
                f"{mal_kabul_no} kalem {mal_kabul_kalem_no}: karar bekleyen "
                f"karantina yok"
            )
        if miktar <= 0 or miktar > kalan:
            raise GecersizGirisError(
                f"Karar miktarı 0'dan büyük ve kalan karantinadan ({kalan}) "
                f"fazla olmamalı; girilen: {miktar}"
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARANTINA_KARAR_GEREKCELERI[karar],
        )

        karantina_karari = KarantinaKarari(
            mal_kabul_no=mal_kabul_no,
            mal_kabul_kalem_no=mal_kabul_kalem_no,
            karar=karar,
            miktar=miktar,
            karar_gerekcesi=gerekce,
            kayit_tarihi=tarih,
            karar_notu=notu,
        )
        self.karantina_kararlari.append(karantina_karari)
        self._kaydet()
        return karantina_karari

    def fatura_ayrintisini_hesapla(self, fatura_no):
        """Faturanın bloke ayrıntısını (Bulgu'ları) yeniden hesaplar.

        Faturada sadece neden kodları saklanır; ayrıntı her açılışta kayıtlı
        veriden hesaplanır, hiçbir şey yazılmaz (E63). Sadece eşleşmiş ve
        aktif faturada (BLOKE, ONAYLANDI, SERBEST); bekleyen faturada mal
        olmadığı için sonuç yanıltıcı olurdu (E117).

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".

        Returns:
            EslestirmeSonucu; menü bulgular() ile satırları yazar.

        Raises:
            KayitBulunamadiError: Fatura yoksa (16a).
            IslemYapilamazError: Fatura eşleşmemiş, reddedilmiş ya da iptal
                edilmişse (16b).
        """
        fatura = self._kayit_bul(self.faturalar, fatura_no)
        if (fatura.iptal_bilgisi.iptal_edildi
                or fatura.durum not in ("BLOKE", "ONAYLANDI", "SERBEST")):
            raise IslemYapilamazError(
                f"{fatura_no}: ayrıntı sadece eşleşmiş ve aktif faturada "
                f"gösterilir (şu an {fatura.durum})"
            )
        return self._eslestirme_sonucu_hesapla(fatura)

    def bekleyen_faturalari_listele(self):
        """Malı gelmemiş, eşleşme bekleyen faturalar (ilke 10, E118).

        Returns:
            ESLESME_BEKLIYOR ve iptal edilmemiş Fatura listesi; yoksa boş.
        """
        bekleyenler = []
        for fatura in self.faturalar.values():
            if (fatura.durum == "ESLESME_BEKLIYOR"
                    and not fatura.iptal_bilgisi.iptal_edildi):
                bekleyenler.append(fatura)
        return bekleyenler

    def bloke_faturalari_listele(self):
        """Serbest bırak / reddet kararı bekleyen faturalar (ilke 10, E118).

        Returns:
            BLOKE ve iptal edilmemiş Fatura listesi; yoksa boş.
        """
        blokeler = []
        for fatura in self.faturalar.values():
            if fatura.durum == "BLOKE" and not fatura.iptal_bilgisi.iptal_edildi:
                blokeler.append(fatura)
        return blokeler

    def karantinadakileri_listele(self):
        """Karar bekleyen karantinadaki mal, nedene göre (ilke 10, E118).

        Sadece iptal edilmemiş mal kabuller ve kalanı > 0 olan kalemler
        girer. Kalemin karar toplamı önce IADE_BEKLIYOR'dan, sonra diğer
        nedenlerden düşülür (C7 sıra kuralı).

        Returns:
            KarantinaSatiri listesi; yoksa boş.
        """
        satirlar = []
        for mal_kabul in self.mal_kabuller.values():
            if mal_kabul.iptal_bilgisi.iptal_edildi:
                continue
            for kalem in mal_kabul.mal_kabul_kalemleri:
                if not kalem.karantinalar:
                    continue
                karar_toplami = Decimal("0")
                for karar in self.karantina_kararlari:
                    if (karar.mal_kabul_no == mal_kabul.mal_kabul_no
                            and karar.mal_kabul_kalem_no == kalem.kalem_no):
                        karar_toplami += karar.miktar
                sirali = []
                for karantina in kalem.karantinalar:
                    if karantina.neden == "IADE_BEKLIYOR":
                        sirali.append(karantina)
                for karantina in kalem.karantinalar:
                    if karantina.neden != "IADE_BEKLIYOR":
                        sirali.append(karantina)
                kalanlar = []
                for karantina in sirali:
                    dusulen = min(karantina.miktar, karar_toplami)
                    karar_toplami -= dusulen
                    if karantina.miktar - dusulen > 0:
                        kalanlar.append(NedenliMiktar(
                            neden=karantina.neden,
                            miktar=karantina.miktar - dusulen))
                if kalanlar:
                    satirlar.append(KarantinaSatiri(
                        mal_kabul_no=mal_kabul.mal_kabul_no,
                        mal_kabul_kalem_no=kalem.kalem_no,
                        siparis_no=mal_kabul.siparis_no,
                        kalanlar=kalanlar))
        return satirlar


if __name__ == "__main__":
    # Deneme köşesi: test dosyasında küçük bir akış (gerçek veriye yazmaz).
    from ayarlar import TEST_VERI_DOSYASI
    from depolama import bos_veri_olustur

    kaydet(bos_veri_olustur(), TEST_VERI_DOSYASI)
    servis = SatinAlmaServisi(TEST_VERI_DOSYASI)
    tedarikci = servis.tedarikci_ekle("ABC Kırtasiye")
    siparis = servis.siparis_ac(tedarikci.tedarikci_kodu, [
        {"malzeme_adi": "A4 kağıt", "miktar": Decimal("10"), "birim": "adet",
         "birim_fiyat": Decimal("100"), "kategori": "SARF"},
    ], tarih="2026-11-02")
    servis.siparis_onayla(siparis.siparis_no)

    fatura = servis.fatura_kaydet(siparis.siparis_no, "F-1001", [
        {"siparis_kalem_no": 10, "miktar": Decimal("10"),
         "birim_fiyat": Decimal("120")},
    ], tarih="2026-11-02")
    print("Bekleyen:", [f.fatura_no for f in servis.bekleyen_faturalari_listele()])

    sonuc = servis.mal_kabul_kaydet(siparis.siparis_no, [
        {"siparis_kalem_no": 10, "gelen_miktar": Decimal("15")},
    ], tir_kapida=False, tarih="2026-11-02")
    print("R2 ile eşleşen:", sonuc.eslesen_faturalar)
    print("Bloke:", [(f.fatura_no, f.bloke_neden_kodlari)
                     for f in servis.bloke_faturalari_listele()])
    for bulgu in servis.fatura_ayrintisini_hesapla(fatura.fatura_no).bulgular():
        print("  Ayrıntı:", bulgu)

    mal_kabul_no = sonuc.mal_kabul.mal_kabul_no
    servis.karantina_karari_ver(mal_kabul_no, 10, "IADE", Decimal("3"),
                                "FAZLA_KABUL_EDILMEDI", tarih="2026-11-02")
    for satir in servis.karantinadakileri_listele():
        print("Karantina:", satir.mal_kabul_no, satir.mal_kabul_kalem_no,
              satir.kalanlar, "toplam", satir.kalan_miktar())

    try:
        servis.mal_kabul_iptal_et(mal_kabul_no, "MUKERRER_GIRIS")
    except IslemYapilamazError as hata:
        print("Beklenen hata (8c):", hata)


    


        
        
