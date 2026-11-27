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
    ODEME_YONTEMLERI,
    ONEKLER,
    TOLERANSLAR,
)
from depolama import kaydet, yukle
from eslestirme import KovaSonucu, kovalara_ayir, kurallari_uygula
from hatalar import (
    DepolamaError,
    GecersizGirisError,
    IslemYapilamazError,
    KayitBulunamadiError,
)
from modeller import (
    Fatura,
    FaturaKalemi,
    KarantinaKarari,
    MalKabul,
    MalKabulDagitimi,
    MalKabulKalemi,
    NedenliMiktar,
    Odeme,
    OdemeKalemi,
    Siparis,
    SiparisKalemi,
    Talep,
    TalepKalemi,
    Tedarikci,
    Teklif,
    TeklifKalemi,
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


# _kayit_bul'un hata mesajında kullanılan belge türü adları (E132):
# (servisteki sözlüğün adı, ekranda görünen tür).
BELGE_TURLERI = (
    ("tedarikciler", "Tedarikçi"),
    ("talepler", "Talep"),
    ("teklifler", "Teklif"),
    ("siparisler", "Sipariş"),
    ("mal_kabuller", "Mal kabul"),
    ("faturalar", "Fatura"),
    ("odemeler", "Ödeme"),
)


class SatinAlmaServisi:
    """Satın alma sürecinin bütün işlemleri: talep, teklif, sipariş, mal
    kabul, fatura, ödeme.

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
        self._yukle()

    def _yukle(self):
        """Veri dosyasını okur ve belgeleri sözlüklere yerleştirir.

        __init__ açılışta, _kaydet kayıt hata verince çağırır (B4): bellek
        dosyanın son sağlam hâline döner. Dosya yoksa boş veriyle başlar.

        Raises:
            DepolamaError: Dosya bozuksa ya da sürümü uyumsuzsa (10a, 10c).
        """
        veri = yukle(self.dosya_yolu)

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

        self.talepler = {}
        for talep in veri["talepler"]:
            self.talepler[talep.talep_no] = talep

        self.teklifler = {}
        for teklif in veri["teklifler"]:
            self.teklifler[teklif.teklif_no] = teklif

        self.odemeler = {}
        for odeme in veri["odemeler"]:
            self.odemeler[odeme.odeme_no] = odeme

    def _kaydet(self):
        """Bellekteki bütün veriyi dosyaya yazar.

        Sözlükler listeye çevrilir, depolama.kaydet çağrılır. Her başarılı
        işlemin son adımıdır (E61, E91). Yazma hata verirse bellek dosyadan
        yeniden yüklenir, sonra hata yukarı iletilir (B4): bellekte dosyada
        olmayan bir "hayalet" belge ya da artmış sayaç kalmaz. Dosyanın son
        sağlam hâlini güvenli yazma korur (B3).

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
            "talepler": list(self.talepler.values()),
            "teklifler": list(self.teklifler.values()),
            "odemeler": list(self.odemeler.values()),
        }
        try:
            kaydet(veri, self.dosya_yolu)
        except DepolamaError:
            self._yukle()
            raise
    
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


    def _kayit_bul(self, kayitlar, numara, kod):
        """Numarası verilen belgeyi verilen sözlükte bulur.

        Bütün belge türleri için tek yardımcı: hangi sözlükte aranacağını
        çağıran söyler (ör. self.siparisler). Bulunamazsa mesaj kaydın
        türünü söyler ("Fatura bulunamadı: FTR-0009"); numara boşsa
        "Fatura numarası girilmedi" der (E132). Tür, sözlüğün kendisinden
        çıkarılır; çağıranların değişmesi gerekmez.

        Args:
            kayitlar: Numarayla anahtarlı belge sözlüğü.
            numara: Aranan numara, ör. "SAS-0001".
            kod: Bulunamazsa verilecek hata kodu; çağıran metot işlemini
                bildiği için kodu o verir (E129), ör. "9a".

        Returns:
            Bulunan belge nesnesi.

        Raises:
            KayitBulunamadiError: Numara sözlükte yoksa (kod: çağıranın
                verdiği).
        """
        if numara not in kayitlar:
            belge_turu = "Kayıt"
            for alan_adi, tur_adi in BELGE_TURLERI:
                if getattr(self, alan_adi) is kayitlar:
                    belge_turu = tur_adi
            if not str(numara).strip():
                mesaj = f"{belge_turu} numarası girilmedi"
            else:
                mesaj = f"{belge_turu} bulunamadı: {numara}"
            raise KayitBulunamadiError(mesaj, kod=kod)
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

    def _gerekceyi_dogrula(self, gerekce, notu, gecerli_gerekceler, kod):
        """Gerekçe kodunu ve DIGER'in notunu kontrol eder.

        Karar, iptal ve karantina kararı metotlarının ortak yardımcısı
        (E113); hiçbir şeyi değiştirmez.

        Args:
            gerekce: Seçilen gerekçe kodu, ör. "MUKERRER_GIRIS".
            notu: Açıklama; gerekçe DIGER ise zorunlu.
            gecerli_gerekceler: O işlemin gerekçe sözlüğü,
                ör. IPTAL_GEREKCELERI["FATURA"].
            kod: Hata kodu; çağıran metot verir (E129): 7c, 12a, 15c.

        Raises:
            GecersizGirisError: Gerekçe listede yoksa ya da DIGER seçilip
                not boşsa (kod: çağıranın verdiği).
        """
        if gerekce not in gecerli_gerekceler:
            raise GecersizGirisError(
                f"Geçersiz gerekçe: {gerekce}; geçerli olanlar: "
                f"{', '.join(gecerli_gerekceler)}",
                kod=kod,
            )
        if gerekce == "DIGER" and (not notu or not notu.strip()):
            raise GecersizGirisError(
                "DIGER seçildiğinde açıklama notu zorunlu",
                kod=kod,
            )

    def _kalemleri_dogrula(self, kalemler, fiyat_alani="birim_fiyat",
                           fiyat_zorunlu=True):
        """Kalem sözlüklerinin ortak kurallarını kontrol eder.

        Sipariş, talep ve teklif kalemlerinin ortak yardımcısı; hiçbir
        şeyi değiştirmez, kaydetmez. Kalem nesnesini çağıran metot kurar.
        Tür kontrolü (2d) karşılaştırmalardan (2e) önce yapılır; yoksa
        metin bir değer TypeError verir.

        Args:
            kalemler: Kalem sözlüklerinin listesi. Zorunlu anahtarlar:
                malzeme_adi, miktar, birim, kategori. İsteğe bağlı:
                fiyat (adı fiyat_alani'nda), iskonto_turu, iskonto_degeri,
                miktar_tavani.
            fiyat_alani: Fiyatın anahtarı: siparişte ve teklifte
                "birim_fiyat", talepte "tahmini_birim_fiyat".
            fiyat_zorunlu: True ise fiyat girilmemiş kalem 2d hatası
                verir; False ise (talep) fiyatsız kalem kabul edilir.

        Raises:
            GecersizGirisError: Kalem yoksa (2b), malzeme adı ya da birim
                boşsa (2c), miktar ya da fiyat Decimal değilse (2d, B8),
                miktar ya da fiyat ≤ 0 ise (2e), kategori geçersizse (2f),
                miktar tavanı negatifse (2g), iskonto geçersizse (13a,
                para.py).
        """
        if not kalemler:
            raise GecersizGirisError("En az bir kalem olmalı", kod="2b")

        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            fiyat = kalem.get(fiyat_alani)

            if not kalem["malzeme_adi"] or not kalem["malzeme_adi"].strip():
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: malzeme adı boş olamaz",
                    kod="2c",
                )
            if not kalem["birim"] or not kalem["birim"].strip():
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: birim boş olamaz",
                    kod="2c",
                )
            if not isinstance(kalem["miktar"], Decimal):
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: miktar sayı olmalı",
                    kod="2d",
                )
            if (fiyat is not None or fiyat_zorunlu) and not isinstance(
                fiyat, Decimal
            ):
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: birim fiyat sayı olmalı",
                    kod="2d",
                )
            if kalem["miktar"] <= 0:
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: miktar 0'dan büyük olmalı",
                    kod="2e",
                )
            if fiyat is not None and fiyat <= 0:
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: birim fiyat 0'dan büyük olmalı",
                    kod="2e",
                )
            if kalem["kategori"] not in TOLERANSLAR:
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: geçersiz kategori: "
                    f"{kalem['kategori']}",
                    kod="2f",
                )
            miktar_tavani = kalem.get("miktar_tavani")
            if miktar_tavani is not None and miktar_tavani < 0:
                raise GecersizGirisError(
                    f"Kalem {kalem_no}: miktar tavanı negatif olamaz",
                    kod="2g",
                )
            if fiyat is not None:
                iskontoyu_dogrula(
                    fiyat,
                    kalem.get("iskonto_turu", "ORAN"),
                    kalem.get("iskonto_degeri", Decimal("0")),
                )
            kalem_no += KALEM_NO_ARTISI


    def _aktif_siparis_kalemi_bul(self, talep_no, talep_kalem_no):
        """Talep kalemine bağlı iptal edilmemiş siparişi bulur (K3).

        Aynı talep kalemi aynı anda tek bir aktif siparişte olabilir.
        Hata atmaz: hangi işlemden çağrıldığını bilmez, hatayı çağıran
        verir (20c, E129). Hiçbir şeyi değiştirmez.

        Args:
            talep_no: Talep numarası, ör. "TLP-0001".
            talep_kalem_no: Talep kalemi numarası, ör. 10.

        Returns:
            Bağlı kalemin bulunduğu Siparis; yoksa None.
        """
        for siparis in self.siparisler.values():
            if siparis.iptal_bilgisi.iptal_edildi:
                continue
            for siparis_kalemi in siparis.siparis_kalemleri:
                if (siparis_kalemi.talep_no == talep_no
                        and siparis_kalemi.talep_kalem_no == talep_kalem_no):
                    return siparis
        return None

    
    def _bag_dogrula(self, kalem, bulunamadi_kodu, onay_kodu, yarim_kodu,
                     kopya_kodu):
        """Kalemin talep bağını kontrol eder, bağlı talep kalemini döndürür.

        Sipariş ve teklif kalemlerinin ortak yardımcısı (E120); hiçbir
        şeyi değiştirmez. Kodları çağıran metot verir (E129): teklifte
        19a / 19b / 19d / 19e, siparişte 18a / 20d / 20f / 20h. "Kalem o
        talepte yok" iki işlemde de aynıdır (19c). Bağlı kalemde malzeme,
        birim ve kategori talepten kopyalanır, ayrıca verilmez (B6).

        Args:
            kalem: Kalem sözlüğü; bağ için talep_no ve talep_kalem_no.
            bulunamadi_kodu: Talep bulunamazsa verilecek kod.
            onay_kodu: Talep iptal edilmiş ya da onaysızsa verilecek kod.
            yarim_kodu: Bağın tek alanı verilmişse verilecek kod.
            kopya_kodu: Bağlı kalemde malzeme / birim / kategori de
                verilmişse verilecek kod.

        Returns:
            Bağlı TalepKalemi; kalem talebe bağlı değilse None.

        Raises:
            GecersizGirisError: Bağ yarımsa (yarim_kodu), bağlı kalemde
                malzeme / birim / kategori verilmişse (kopya_kodu).
            KayitBulunamadiError: Talep yoksa (bulunamadi_kodu).
            IslemYapilamazError: Talep iptal edilmiş ya da ONAYLANDI
                değilse (onay_kodu, K2); kalem o talepte yoksa (19c).
        """
        talep_no = kalem.get("talep_no")
        talep_kalem_no = kalem.get("talep_kalem_no")
        if talep_no is None and talep_kalem_no is None:
            return None
        if talep_no is None or talep_kalem_no is None:
            raise GecersizGirisError(
                "Talep bağı yarım: talep_no ve talep_kalem_no birlikte "
                "verilmeli",
                kod=yarim_kodu,
            )
        if "malzeme_adi" in kalem or "birim" in kalem or "kategori" in kalem:
            raise GecersizGirisError(
                f"{talep_no} / {talep_kalem_no}: talebe bağlı kalemde "
                f"malzeme, birim ve kategori talepten gelir, ayrıca "
                f"verilmez",
                kod=kopya_kodu,
            )

        talep = self._kayit_bul(self.talepler, talep_no, kod=bulunamadi_kodu)
        if talep.iptal_bilgisi.iptal_edildi or talep.durum != "ONAYLANDI":
            raise IslemYapilamazError(
                f"{talep_no}: sadece iptal edilmemiş ONAYLANDI talebe "
                f"bağlanılır (şu an {talep.durum})",
                kod=onay_kodu,
            )

        for talep_kalemi in talep.talep_kalemleri:
            if talep_kalemi.kalem_no == talep_kalem_no:
                return talep_kalemi
        raise IslemYapilamazError(
            f"{talep_no}: {talep_kalem_no} numaralı kalem talepte yok",
            kod="19c",
        )
        
                

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
            raise GecersizGirisError("Tedarikçi adı boş olamaz", kod="1a")

        tedarikci_kodu = self._numara_ver(ONEKLER["tedarikci"])
        yeni_tedarikci = Tedarikci(
            tedarikci_kodu=tedarikci_kodu,
            tedarikci_adi=tedarikci_adi.strip(),
            firma_adi=firma_adi,
        )
        self.tedarikciler[tedarikci_kodu] = yeni_tedarikci
        self._kaydet()
        return yeni_tedarikci

    def talep_ac(self, talep_eden, kalemler, tarih=None):
        """Yeni satın alma talebini TASLAK olarak açar, kaydeder ve döndürür.

        Kalem kuralları siparişle ortaktır (_kalemleri_dogrula); talepte
        fiyat zorunlu değildir, verildiyse > 0 olmalıdır (E121). Talep
        numarası bütün kontrollerden sonra alınır; hatalı girişte sayaç
        artmaz. Birim boşlukları atılıp küçük harfle saklanır.

        Args:
            talep_eden: Talebi yapan kişi ya da birim, ör. "Muhasebe".
            kalemler: Kalem sözlüklerinin listesi. Zorunlu anahtarlar:
                malzeme_adi, miktar, birim, kategori. İsteğe bağlı:
                tahmini_birim_fiyat.
            tarih: "2026-11-02" biçiminde; None ise bugün.

        Returns:
            Oluşturulan Talep.

        Raises:
            GecersizGirisError: talep_eden boşsa (17a); kalem kuralları
                bozulursa (2b-2g).
        """
        if not talep_eden or not talep_eden.strip():
            raise GecersizGirisError("Talep eden boş olamaz", kod="17a")
        self._kalemleri_dogrula(
            kalemler,
            fiyat_alani="tahmini_birim_fiyat",
            fiyat_zorunlu=False,
        )
        if tarih is None:
            tarih = date.today().isoformat()

        talep_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            talep_kalemleri.append(TalepKalemi(
                kalem_no=kalem_no,
                malzeme_adi=kalem["malzeme_adi"],
                miktar=kalem["miktar"],
                birim=kalem["birim"].strip().lower(),
                kategori=kalem["kategori"],
                tahmini_birim_fiyat=kalem.get("tahmini_birim_fiyat"),
            ))
            kalem_no += KALEM_NO_ARTISI

        talep_no = self._numara_ver(ONEKLER["talep"])
        yeni_talep = Talep(
            talep_no=talep_no,
            talep_eden=talep_eden.strip(),
            talep_kalemleri=talep_kalemleri,
            kayit_tarihi=tarih,
        )
        self.talepler[talep_no] = yeni_talep
        self._kaydet()
        return yeni_talep

    def talep_bul(self, talep_no):
        """Talebi numarasıyla bulur ve döndürür; hiçbir şeyi değiştirmez.

        Menü ve talebe bağlanan teklif / sipariş kontrolü kullanır (E100).

        Args:
            talep_no: Talep numarası, ör. "TLP-0001".

        Returns:
            Bulunan Talep.

        Raises:
            KayitBulunamadiError: Numara yoksa (18a).
        """
        return self._kayit_bul(self.talepler, talep_no, kod="18a")

    def talep_onayla(self, talep_no, tarih=None):
        """TASLAK talebi onaylar; onay gerekçesizdir (T2). Değer döndürmez.

        Sadece onaylı talepten teklif ve sipariş açılabilir (K2).

        Args:
            talep_no: Talep numarası, ör. "TLP-0001".
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Talep yoksa (18a).
            IslemYapilamazError: Talep iptal edilmişse ya da TASLAK
                değilse (18b).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        talep = self.talep_bul(talep_no)
        if talep.iptal_bilgisi.iptal_edildi or talep.durum != "TASLAK":
            raise IslemYapilamazError(
                f"{talep_no}: sadece iptal edilmemiş TASLAK talep onaylanır "
                f"(şu an {talep.durum})",
                kod="18b",
            )
        talep.durum_degistir("ONAYLANDI")
        talep.karar_tarihi = tarih
        self._kaydet()

    def talep_reddet(self, talep_no, gerekce, notu=None, tarih=None):
        """TASLAK talebi gerekçeyle reddeder; reddedilen talep kilitlenir (T3).

        Karar gerekçesi, notu ve tarihi talebe yazılır (E113). Değer
        döndürmez.

        Args:
            talep_no: Talep numarası, ör. "TLP-0001".
            gerekce: KARAR_GEREKCELERI["TALEP_RED"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Talep yoksa (18a).
            IslemYapilamazError: Talep iptal edilmişse ya da TASLAK
                değilse (18b).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (7c).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        talep = self.talep_bul(talep_no)
        if talep.iptal_bilgisi.iptal_edildi or talep.durum != "TASLAK":
            raise IslemYapilamazError(
                f"{talep_no}: sadece iptal edilmemiş TASLAK talep reddedilir "
                f"(şu an {talep.durum})",
                kod="18b",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARAR_GEREKCELERI["TALEP_RED"],
            kod="7c",
        )
        talep.durum_degistir("REDDEDILDI")
        talep.karar_gerekcesi = gerekce
        talep.karar_notu = notu
        talep.karar_tarihi = tarih
        self._kaydet()

    def talep_iptal_et(self, talep_no, gerekce, notu=None, tarih=None):
        """Talebi gerekçeyle iptal eder; iptal geri alınmaz.

        Zincirin ilk halkası olduğu için en son iptal edilir (R3): ona bağlı
        aktif teklif (iptal edilmemiş, reddedilmemiş) ya da iptal edilmemiş
        sipariş varsa iptal edilmez. Durum değişmez. Değer döndürmez.

        Args:
            talep_no: Talep numarası, ör. "TLP-0001".
            gerekce: IPTAL_GEREKCELERI["TALEP"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Talep yoksa (18a).
            IslemYapilamazError: Zaten iptal edilmişse (22c), bağlı aktif
                teklif ya da sipariş varsa (22a).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (12a).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        talep = self.talep_bul(talep_no)
        if talep.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{talep_no}: talep zaten iptal edilmiş",
                kod="22c",
            )
        for teklif in self.teklifler.values():
            if teklif.durum == "REDDEDILDI" or teklif.iptal_bilgisi.iptal_edildi:
                continue
            for teklif_kalemi in teklif.teklif_kalemleri:
                if teklif_kalemi.talep_no == talep_no:
                    raise IslemYapilamazError(
                        f"{talep_no}: talebe bağlı aktif teklif var "
                        f"({teklif.teklif_no}), önce teklifi iptal edin",
                        kod="22a",
                    )
        for siparis in self.siparisler.values():
            if siparis.iptal_bilgisi.iptal_edildi:
                continue
            for siparis_kalemi in siparis.siparis_kalemleri:
                if siparis_kalemi.talep_no == talep_no:
                    raise IslemYapilamazError(
                        f"{talep_no}: talebe bağlı aktif sipariş var "
                        f"({siparis.siparis_no}), önce siparişi iptal edin",
                        kod="22a",
                    )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["TALEP"],
            kod="12a",
        )
        talep.iptal_bilgisi.iptal_et(gerekce, notu, tarih)
        self._kaydet()

    def teklif_kaydet(self, tedarikci_kodu, kalemler, tedarikci_teklif_no=None,
                      tarih=None):
        """Tedarikçinin teklifini ACIK olarak kaydeder ve döndürür (E122).

        siparis_ac'ın kalıbı: kalem bir talep kalemine bağlanabilir; o
        zaman malzeme adı, birim ve kategori talepten kopyalanır (B6).
        Sıra: bağ + kopya → kalem kuralları (_kalemleri_dogrula) → aynı
        talep kalemi iki kez mi (19f) → kalemler kurulur. Aynı talep
        kalemine birden çok tedarikçinin teklifi olabilir (karşılaştırma
        için), bu yüzden K3 ve miktar sınırı yalnızca siparişte vardır.
        Teklif numarası bütün kontrollerden sonra alınır.

        Args:
            tedarikci_kodu: Teklifi veren kayıtlı tedarikçi, ör. "TED-0001".
            kalemler: Kalem sözlüklerinin listesi. Talepsiz kalemde zorunlu:
                malzeme_adi, miktar, birim, birim_fiyat, kategori. Talebe
                bağlı kalemde: talep_no, talep_kalem_no, miktar, birim_fiyat.
                İsteğe bağlı: iskonto_turu, iskonto_degeri.
            tedarikci_teklif_no: Tedarikçinin kendi teklif numarası.
            tarih: "2026-11-02" biçiminde; None ise bugün.

        Returns:
            Oluşturulan Teklif.

        Raises:
            KayitBulunamadiError: Tedarikçi ya da bağlı talep yoksa (19a).
            GecersizGirisError: Kalem kuralları bozulursa (2b-2g, 13a); bağ
                yarımsa (19d); bağlı kalemde malzeme / birim / kategori de
                verilmişse (19e); aynı talep kalemi iki kez varsa (19f).
            IslemYapilamazError: Bağlı talep onaylı değilse ya da iptal
                edilmişse (19b, K2); kalem o talepte yoksa (19c).
        """
        self._kayit_bul(self.tedarikciler, tedarikci_kodu, kod="19a")

        hazir_kalemler = []
        bagli_talep_kalemleri = []
        for kalem in kalemler:
            talep_kalemi = self._bag_dogrula(kalem, "19a", "19b", "19d", "19e")
            hazir_kalem = dict(kalem)
            if talep_kalemi is not None:
                hazir_kalem["malzeme_adi"] = talep_kalemi.malzeme_adi
                hazir_kalem["birim"] = talep_kalemi.birim
                hazir_kalem["kategori"] = talep_kalemi.kategori
            hazir_kalemler.append(hazir_kalem)
            bagli_talep_kalemleri.append(talep_kalemi)

        self._kalemleri_dogrula(hazir_kalemler)

        gorulen_baglar = []
        for hazir_kalem, talep_kalemi in zip(hazir_kalemler,
                                             bagli_talep_kalemleri):
            if talep_kalemi is None:
                continue
            bag = (hazir_kalem["talep_no"], hazir_kalem["talep_kalem_no"])
            if bag in gorulen_baglar:
                raise GecersizGirisError(
                    f"{bag[0]} / {bag[1]}: aynı talep kalemi teklifte iki "
                    f"kez girilmiş",
                    kod="19f",
                )
            gorulen_baglar.append(bag)

        if tarih is None:
            tarih = date.today().isoformat()
        if tedarikci_teklif_no is not None:
            tedarikci_teklif_no = tedarikci_teklif_no.strip() or None

        teklif_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in hazir_kalemler:
            teklif_kalemleri.append(TeklifKalemi(
                kalem_no=kalem_no,
                malzeme_adi=kalem["malzeme_adi"],
                miktar=kalem["miktar"],
                birim=kalem["birim"].strip().lower(),
                kategori=kalem["kategori"],
                birim_fiyat=kalem["birim_fiyat"],
                iskonto_turu=kalem.get("iskonto_turu", "ORAN"),
                iskonto_degeri=kalem.get("iskonto_degeri", Decimal("0")),
                talep_no=kalem.get("talep_no"),
                talep_kalem_no=kalem.get("talep_kalem_no"),
            ))
            kalem_no += KALEM_NO_ARTISI

        teklif_no = self._numara_ver(ONEKLER["teklif"])
        yeni_teklif = Teklif(
            teklif_no=teklif_no,
            tedarikci_kodu=tedarikci_kodu,
            teklif_kalemleri=teklif_kalemleri,
            kayit_tarihi=tarih,
            tedarikci_teklif_no=tedarikci_teklif_no,
        )
        self.teklifler[teklif_no] = yeni_teklif
        self._kaydet()
        return yeni_teklif

    def teklif_bul(self, teklif_no):
        """Teklifi numarasıyla bulur ve döndürür; hiçbir şeyi değiştirmez.

        Menü, teklif kararları ve tekliften sipariş kullanır (E100).

        Args:
            teklif_no: Teklif numarası, ör. "TKL-0001".

        Returns:
            Bulunan Teklif.

        Raises:
            KayitBulunamadiError: Numara yoksa (21a).
        """
        return self._kayit_bul(self.teklifler, teklif_no, kod="21a")

    def teklif_siparise_donustu_mu(self, teklif_no):
        """Teklife bağlı iptal edilmemiş sipariş var mı, söyler (E122).

        "Siparişe dönüştü" ayrı bir durum değildir; her seferinde sipariş
        kalemlerindeki teklif_no'dan hesaplanır. Siparişi iptal edilen
        teklif yeniden ACIK sayılır. Hiçbir şeyi değiştirmez.

        Args:
            teklif_no: Teklif numarası, ör. "TKL-0001".

        Returns:
            Bağlı aktif sipariş varsa True, yoksa False.

        Raises:
            KayitBulunamadiError: Teklif yoksa (21a).
        """
        self.teklif_bul(teklif_no)
        for siparis in self.siparisler.values():
            if siparis.iptal_bilgisi.iptal_edildi:
                continue
            for siparis_kalemi in siparis.siparis_kalemleri:
                if siparis_kalemi.teklif_no == teklif_no:
                    return True
        return False

    def teklif_reddet(self, teklif_no, gerekce, notu=None, tarih=None):
        """ACIK teklifi gerekçeyle reddeder; reddedilen teklif kilitlenir.

        Siparişe dönüşmüş teklif reddedilmez: önce sipariş iptal edilmeli.
        Karar gerekçesi, notu ve tarihi teklife yazılır (E113). Değer
        döndürmez.

        Args:
            teklif_no: Teklif numarası, ör. "TKL-0001".
            gerekce: KARAR_GEREKCELERI["TEKLIF_RED"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Teklif yoksa (21a).
            IslemYapilamazError: Teklif iptal edilmişse, ACIK değilse ya
                da siparişe dönüşmüşse (21b).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (7c).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        teklif = self.teklif_bul(teklif_no)
        if teklif.iptal_bilgisi.iptal_edildi or teklif.durum != "ACIK":
            raise IslemYapilamazError(
                f"{teklif_no}: sadece iptal edilmemiş ACIK teklif reddedilir "
                f"(şu an {teklif.durum})",
                kod="21b",
            )
        if self.teklif_siparise_donustu_mu(teklif_no):
            raise IslemYapilamazError(
                f"{teklif_no}: teklif siparişe dönüşmüş, önce siparişi "
                f"iptal edin",
                kod="21b",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARAR_GEREKCELERI["TEKLIF_RED"],
            kod="7c",
        )
        teklif.durum_degistir("REDDEDILDI")
        teklif.karar_gerekcesi = gerekce
        teklif.karar_notu = notu
        teklif.karar_tarihi = tarih
        self._kaydet()

    def teklif_iptal_et(self, teklif_no, gerekce, notu=None, tarih=None):
        """Teklifi gerekçeyle iptal eder; iptal geri alınmaz.

        Zincir tersten iptal edilir (R3): teklife bağlı iptal edilmemiş
        sipariş varsa iptal edilmez. Durum değişmez. Değer döndürmez.

        Args:
            teklif_no: Teklif numarası, ör. "TKL-0001".
            gerekce: IPTAL_GEREKCELERI["TEKLIF"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Teklif yoksa (21a).
            IslemYapilamazError: Zaten iptal edilmişse (22c), bağlı aktif
                sipariş varsa (22b).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (12a).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        teklif = self.teklif_bul(teklif_no)
        if teklif.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{teklif_no}: teklif zaten iptal edilmiş",
                kod="22c",
            )
        if self.teklif_siparise_donustu_mu(teklif_no):
            raise IslemYapilamazError(
                f"{teklif_no}: teklife bağlı aktif sipariş var, önce "
                f"siparişi iptal edin",
                kod="22b",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["TEKLIF"],
            kod="12a",
        )
        teklif.iptal_bilgisi.iptal_et(gerekce, notu, tarih)
        self._kaydet()

    def siparis_ac(self, tedarikci_kodu, kalemler, tolerans=None, tarih=None):
        """Yeni siparişi TASLAK olarak açar, kaydeder ve döndürür.

        Kalem numarasını ve tolerans kopyasını servis verir. Sipariş
        numarası bütün kontrollerden sonra alınır; hatalı girişte sayaç
        artmaz. Birim boşlukları atılıp küçük harfle saklanır.

        Kalem bir talep kalemine bağlanabilir (E120): o zaman malzeme adı,
        birim ve kategori talepten kopyalanır (B6). Kalem bir teklif
        kalemine de bağlanabilir (E122); bağ burada kontrol edilir, böylece
        elle verilen yanlış teklif bağı da yakalanır. Sıra: talep bağı +
        kopya → kalem kuralları (_kalemleri_dogrula) → teklif bağı (20a,
        20b, 20e) ve talep bağı kuralları (20i, 20c, 20g) → kalemler
        kurulur. Miktar kontrolü 2d'den sonra gelir; metin
        bir miktar TypeError değil 2d verir. Kullanıcının sözlükleri
        değişmez, kopyaları üzerinde çalışılır.

        Args:
            tedarikci_kodu: Kayıtlı tedarikçi kodu, ör. "TED-0001".
            kalemler: Kalem sözlüklerinin listesi. Talepsiz kalemde zorunlu:
                malzeme_adi, miktar, birim, birim_fiyat, kategori. Talebe
                bağlı kalemde: talep_no, talep_kalem_no, miktar, birim_fiyat
                (malzeme adı, birim ve kategori verilmez). İsteğe bağlı:
                iskonto_turu, iskonto_degeri, miktar_tavani. Tekliften gelen
                kalemde ayrıca teklif_no, teklif_kalem_no
                (tekliften_siparis_ac verir).
            tolerans: Verilirse bütün kalemlere bu ToleransKopyasi
                kopyalanır; None ise kategorinin ayarları kullanılır.
            tarih: "2026-11-02" biçiminde; None ise bugün.

        Returns:
            Oluşturulan Siparis.

        Raises:
            KayitBulunamadiError: Tedarikçi (2a), bağlı talep (18a) ya da
                bağlı teklif (20a) kayıtlı değilse.
            GecersizGirisError: Kalem kuralları bozulursa (2b-2g, 13a); bağ
                yarımsa (20f); bağlı kalemde malzeme / birim / kategori de
                verilmişse (20h); aynı talep kalemi siparişte iki kez
                varsa (20i).
            IslemYapilamazError: Bağlı talep onaylı değilse ya da iptal
                edilmişse (20d); kalem o talepte yoksa (19c); talep kalemi
                başka bir aktif siparişe bağlıysa (20c, K3); miktar talep
                miktarından büyükse (20g, B5); bağlı teklif ACIK değilse ya
                da iptal edilmişse (20b), başka tedarikçininse (20e).
        """
        self._kayit_bul(self.tedarikciler, tedarikci_kodu, kod="2a")

        hazir_kalemler = []
        bagli_talep_kalemleri = []
        for kalem in kalemler:
            talep_kalemi = self._bag_dogrula(kalem, "18a", "20d", "20f", "20h")
            hazir_kalem = dict(kalem)
            if talep_kalemi is not None:
                hazir_kalem["malzeme_adi"] = talep_kalemi.malzeme_adi
                hazir_kalem["birim"] = talep_kalemi.birim
                hazir_kalem["kategori"] = talep_kalemi.kategori
            hazir_kalemler.append(hazir_kalem)
            bagli_talep_kalemleri.append(talep_kalemi)

        self._kalemleri_dogrula(hazir_kalemler)

        gorulen_baglar = []
        for hazir_kalem, talep_kalemi in zip(hazir_kalemler,
                                             bagli_talep_kalemleri):
            teklif_no = hazir_kalem.get("teklif_no")
            if teklif_no is not None:
                teklif = self._kayit_bul(self.teklifler, teklif_no, kod="20a")
                if teklif.iptal_bilgisi.iptal_edildi or teklif.durum != "ACIK":
                    raise IslemYapilamazError(
                        f"{teklif_no}: sadece iptal edilmemiş ACIK tekliften "
                        f"sipariş açılır (şu an {teklif.durum})",
                        kod="20b",
                    )
                if teklif.tedarikci_kodu != tedarikci_kodu:
                    raise IslemYapilamazError(
                        f"{teklif_no}: teklif başka tedarikçinin "
                        f"({teklif.tedarikci_kodu})",
                        kod="20e",
                    )

            if talep_kalemi is None:
                continue
            bag = (hazir_kalem["talep_no"], hazir_kalem["talep_kalem_no"])
            if bag in gorulen_baglar:
                raise GecersizGirisError(
                    f"{bag[0]} / {bag[1]}: aynı talep kalemi siparişte iki "
                    f"kez girilmiş",
                    kod="20i",
                )
            bagli_siparis = self._aktif_siparis_kalemi_bul(bag[0], bag[1])
            if bagli_siparis is not None:
                raise IslemYapilamazError(
                    f"{bag[0]} / {bag[1]}: talep kalemi zaten "
                    f"{bagli_siparis.siparis_no} siparişine bağlı",
                    kod="20c",
                )
            if hazir_kalem["miktar"] > talep_kalemi.miktar:
                raise IslemYapilamazError(
                    f"{bag[0]} / {bag[1]}: sipariş miktarı "
                    f"({hazir_kalem['miktar']}) talep miktarından "
                    f"({talep_kalemi.miktar}) büyük olamaz",
                    kod="20g",
                )
            gorulen_baglar.append(bag)

        if tarih is None:
            tarih = date.today().isoformat()

        siparis_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in hazir_kalemler:
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
                talep_no=kalem.get("talep_no"),
                talep_kalem_no=kalem.get("talep_kalem_no"),
                teklif_no=kalem.get("teklif_no"),
                teklif_kalem_no=kalem.get("teklif_kalem_no"),
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

    def tekliften_siparis_ac(self, teklif_no, tolerans=None, tarih=None):
        """ACIK tekliften sipariş açar ve döndürür (E122).

        Teklifin her kalemi bir sipariş kalemi sözlüğüne çevrilir ve
        siparis_ac çağrılır; bütün kontroller (teklif bağı 20a / 20b /
        20e, talep bağı, kalem kuralları) orada yapılır. Siparişin
        tedarikçisi teklifin tedarikçisidir. Talebe bağlı teklif kaleminde
        malzeme adı, birim ve kategori verilmez, siparis_ac talepten
        kopyalar (B6); bağsız kalemde teklif kaleminden alınır.

        Args:
            teklif_no: Teklif numarası, ör. "TKL-0001".
            tolerans: siparis_ac'a aynen geçer; None ise kategori ayarları.
            tarih: "2026-11-02" biçiminde; None ise bugün.

        Returns:
            Oluşturulan Siparis.

        Raises:
            KayitBulunamadiError: Teklif yoksa (20a).
            IslemYapilamazError: Teklif zaten siparişe dönüşmüşse ya da
                ACIK değilse (20b); siparis_ac'ın diğer hataları.
        """
        teklif = self._kayit_bul(self.teklifler, teklif_no, kod="20a")
        if self.teklif_siparise_donustu_mu(teklif_no):
            raise IslemYapilamazError(
                f"{teklif_no}: teklif zaten siparişe dönüşmüş",
                kod="20b",
            )

        kalemler = []
        for teklif_kalemi in teklif.teklif_kalemleri:
            yeni_kalem = {
                "miktar": teklif_kalemi.miktar,
                "birim_fiyat": teklif_kalemi.birim_fiyat,
                "iskonto_turu": teklif_kalemi.iskonto_turu,
                "iskonto_degeri": teklif_kalemi.iskonto_degeri,
                "talep_no": teklif_kalemi.talep_no,
                "talep_kalem_no": teklif_kalemi.talep_kalem_no,
                "teklif_no": teklif_no,
                "teklif_kalem_no": teklif_kalemi.kalem_no,
            }
            if teklif_kalemi.talep_no is None:
                yeni_kalem["malzeme_adi"] = teklif_kalemi.malzeme_adi
                yeni_kalem["birim"] = teklif_kalemi.birim
                yeni_kalem["kategori"] = teklif_kalemi.kategori
            kalemler.append(yeni_kalem)

        return self.siparis_ac(
            teklif.tedarikci_kodu,
            kalemler,
            tolerans=tolerans,
            tarih=tarih,
        )

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
        siparis = self._kayit_bul(self.siparisler, siparis_no, kod="3a")
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş iptal edilmiş, onaylanamaz",
                kod="3b",
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
            KayitBulunamadiError: Numara yoksa (27a).
        """
        return self._kayit_bul(self.siparisler, siparis_no, kod="27a")

    def mal_kabul_bul(self, mal_kabul_no):
        """Mal kabulü numarasıyla bulur ve döndürür (E112).

        Args:
            mal_kabul_no: Mal kabul numarası, ör. "MKB-0001".

        Returns:
            Bulunan MalKabul.

        Raises:
            KayitBulunamadiError: Numara yoksa (27b).
        """
        return self._kayit_bul(self.mal_kabuller, mal_kabul_no, kod="27b")

    def fatura_bul(self, fatura_no):
        """Faturayı numarasıyla bulur ve döndürür (E112).

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".

        Returns:
            Bulunan Fatura.

        Raises:
            KayitBulunamadiError: Numara yoksa (27c).
        """
        return self._kayit_bul(self.faturalar, fatura_no, kod="27c")

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
            GecersizGirisError: Miktar Decimal değilse (4e), negatifse (4f), yanlış ürün gelen
                miktardan büyükse (4h), hiç kalem oluşmadıysa (4g), aynı
                sipariş kalemi iki kez girildiyse (4i).
        """
        siparis = self._kayit_bul(self.siparisler, siparis_no, kod="4a")
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş iptal edilmiş, mal kabul yapılamaz",
                kod="4b",
            )
        if siparis.durum != "ONAYLANDI":
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş onaylı değil, mal kabul yapılamaz",
                kod="4b",
            )
        if self._aktif_mal_kabuller(siparis_no):
            raise IslemYapilamazError(
                f"{siparis_no}: siparişin iptal edilmemiş bir mal kabulü "
                f"zaten var",
                kod="4c",
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

            if (not isinstance(gelen_miktar, Decimal)
                    or not isinstance(yanlis_urun_miktari, Decimal)):
                raise GecersizGirisError(
                    f"Kalem {kalem['siparis_kalem_no']}: gelen ve yanlış ürün "
                    f"miktarı sayı olmalı",
                    kod="4e",
                )

            if gelen_miktar < 0 or yanlis_urun_miktari < 0:
                raise GecersizGirisError("Miktar negatif olamaz", kod="4f")
            if yanlis_urun_miktari > gelen_miktar:
                raise GecersizGirisError(
                    f"Yanlış ürün miktarı ({yanlis_urun_miktari}) gelen "
                    f"miktardan ({gelen_miktar}) büyük olamaz",
                    kod="4h",
                )
            if gelen_miktar == 0 and yanlis_urun_miktari == 0:
                continue
            if kalem["siparis_kalem_no"] not in siparis_kalemleri:
                raise IslemYapilamazError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem siparişte yok",
                    kod="4d",
                )
            if kalem["siparis_kalem_no"] in kova_sonuclari:
                raise GecersizGirisError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem mal kabulde iki kez girilmiş",
                    kod="4i",
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
            raise GecersizGirisError(
                "Mal kabulde en az bir kalem olmalı",
                kod="4g",
            )

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
            GecersizGirisError: Tedarikçi fatura no boşsa (5d), miktar ya
                da fiyat Decimal değilse (5f), miktar negatifse ya da fiyat
                ≤ 0 ise (5g), iskonto geçersizse
                (13a), hiç kalem oluşmadıysa (5h), aynı sipariş kalemi
                iki kez girildiyse (5i).
        """
        siparis = self._kayit_bul(self.siparisler, siparis_no, kod="5a")
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş iptal edilmiş, fatura kaydedilemez",
                kod="5b",
            )
        if siparis.durum != "ONAYLANDI":
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş onaylı değil, fatura kaydedilemez",
                kod="5b",
            )
        if not tedarikci_fatura_no or not tedarikci_fatura_no.strip():
            raise GecersizGirisError(
                "Tedarikçi fatura no boş olamaz",
                kod="5d",
            )
        tedarikci_fatura_no = tedarikci_fatura_no.strip().upper()

        for fatura in self.faturalar.values():
            if fatura.durum == "REDDEDILDI" or fatura.iptal_bilgisi.iptal_edildi:
                continue
            faturanin_siparisi = self._kayit_bul(
                self.siparisler, fatura.siparis_no, kod="26c"
            )
            if (faturanin_siparisi.tedarikci_kodu == siparis.tedarikci_kodu
                    and fatura.tedarikci_fatura_no.strip().upper()
                    == tedarikci_fatura_no):
                raise IslemYapilamazError(
                    f"Bu tedarikçinin {tedarikci_fatura_no} numaralı faturası "
                    f"zaten {fatura.fatura_no} olarak kayıtlı",
                    kod="14a",
                )
            if fatura.siparis_no == siparis_no:
                raise IslemYapilamazError(
                    f"{siparis_no}: siparişin aktif faturası zaten var "
                    f"({fatura.fatura_no})",
                    kod="5c",
                )

        if tarih is None:
            tarih = date.today().isoformat()

        siparis_kalemleri = {}
        for siparis_kalemi in siparis.siparis_kalemleri:
            siparis_kalemleri[siparis_kalemi.kalem_no] = siparis_kalemi

        fatura_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            if (not isinstance(kalem["miktar"], Decimal)
                    or not isinstance(kalem["birim_fiyat"], Decimal)):
                raise GecersizGirisError(
                    f"Kalem {kalem['siparis_kalem_no']}: miktar ve birim fiyat "
                    f"sayı olmalı",
                    kod="5f",
                )
            if kalem["miktar"] < 0:
                raise GecersizGirisError("Miktar negatif olamaz", kod="5g")
            if kalem["miktar"] == 0:
                continue
            if kalem["birim_fiyat"] <= 0:
                raise GecersizGirisError(
                    "Birim fiyat 0'dan büyük olmalı",
                    kod="5g",
                )
            if kalem["siparis_kalem_no"] not in siparis_kalemleri:
                raise IslemYapilamazError(
                    f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                    f"kalem siparişte yok",
                    kod="5e",
                )
            for onceki_kalem in fatura_kalemleri:
                if onceki_kalem.siparis_kalem_no == kalem["siparis_kalem_no"]:
                    raise GecersizGirisError(
                        f"{siparis_no}: {kalem['siparis_kalem_no']} numaralı "
                        f"kalem faturada iki kez girilmiş",
                        kod="5i",
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
            raise GecersizGirisError(
                "Faturada en az bir kalem olmalı",
                kod="5h",
            )

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
        siparis_bul = self._kayit_bul(
            self.siparisler, fatura.siparis_no, kod="26c"
        )
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
        fatura = self._kayit_bul(self.faturalar, fatura_no, kod="6a")
        if fatura.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{fatura_no}: fatura iptal edilmiş, eşleştirilemez",
                kod="6b",
            )
        if fatura.durum != "ESLESME_BEKLIYOR":
            raise IslemYapilamazError(
                f"{fatura_no}: fatura eşleşme beklemiyor (şu an {fatura.durum})",
                kod="6b",
            )
        aktif_mal_kabuller = self._aktif_mal_kabuller(fatura.siparis_no)
        if not aktif_mal_kabuller:
            raise IslemYapilamazError(
                f"{fatura_no}: siparişin mal kabulü yok; fatura mal gelince "
                f"kendiliğinden eşleşir",
                kod="6d",
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
        fatura = self._kayit_bul(self.faturalar, fatura_no, kod="7a")
        if fatura.durum != "BLOKE":
            raise IslemYapilamazError(
                f"{fatura_no}: sadece BLOKE fatura serbest bırakılabilir "
                f"(şu an {fatura.durum})",
                kod="7b",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARAR_GEREKCELERI["SERBEST"],
            kod="7c",
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
        fatura = self._kayit_bul(self.faturalar, fatura_no, kod="7a")
        if fatura.durum not in ("BLOKE", "ESLESME_BEKLIYOR"):
            raise IslemYapilamazError(
                f"{fatura_no}: sadece BLOKE ya da ESLESME_BEKLIYOR fatura "
                f"reddedilebilir (şu an {fatura.durum})",
                kod="7b",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARAR_GEREKCELERI["REDDEDILDI"],
            kod="7c",
        )
        fatura.durum_degistir("REDDEDILDI")
        fatura.karar_gerekcesi = gerekce
        fatura.karar_notu = notu
        fatura.karar_tarihi = tarih
        self._kaydet()

    def fatura_iptal_et(self, fatura_no, gerekce, notu=None, tarih=None):
        """Faturayı gerekçeyle iptal eder; iptal geri alınmaz.

        Fatura silinmez, iptal_bilgisi kartına yazılır; durum değişmez.
        Zincirin son halkası olduğu için önce o iptal edilir (R3); aktif
        ödemesi olan fatura iptal edilmez, önce ödeme iptal edilir (O5). İptal
        edilen fatura 5c, 14a ve R2'de sayılmaz. Değer döndürmez.

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".
            gerekce: IPTAL_GEREKCELERI["FATURA"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Fatura yoksa (9a).
            IslemYapilamazError: Fatura zaten iptal edilmişse (9b), aktif
                ödemesi varsa (9c).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (12a).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        fatura = self._kayit_bul(self.faturalar, fatura_no, kod="9a")
        if fatura.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{fatura_no}: fatura zaten iptal edilmiş",
                kod="9b",
            )
        if self._faturaya_odenen(fatura_no) > 0:
            raise IslemYapilamazError(
                f"{fatura_no}: faturanın aktif ödemesi var, önce ödemeyi "
                f"iptal edin",
                kod="9c",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["FATURA"],
            kod="12a",
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
        mal_kabul = self._kayit_bul(self.mal_kabuller, mal_kabul_no, kod="8a")
        if mal_kabul.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{mal_kabul_no}: mal kabul zaten iptal edilmiş",
                kod="8b",
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
                            f"iptal edin",
                            kod="8c",
                        )
        for karar in self.karantina_kararlari:
            if karar.mal_kabul_no == mal_kabul_no:
                raise IslemYapilamazError(
                    f"{mal_kabul_no}: mal kabulün {karar.mal_kabul_kalem_no}. "
                    f"kalemine karantina kararı verilmiş, iptal edilemez",
                    kod="8d",
                )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["MAL_KABUL"],
            kod="12a",
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
        siparis = self._kayit_bul(self.siparisler, siparis_no, kod="11a")
        if siparis.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{siparis_no}: sipariş zaten iptal edilmiş",
                kod="11b",
            )
        if self._aktif_mal_kabuller(siparis_no):
            raise IslemYapilamazError(
                f"{siparis_no}: siparişin iptal edilmemiş mal kabulü var, "
                f"önce mal kabulü iptal edin",
                kod="11c",
            )
        for fatura in self.faturalar.values():
            if fatura.durum == "REDDEDILDI" or fatura.iptal_bilgisi.iptal_edildi:
                continue
            if fatura.siparis_no == siparis_no:
                raise IslemYapilamazError(
                    f"{siparis_no}: siparişin aktif faturası var "
                    f"({fatura.fatura_no}), önce faturayı iptal edin",
                    kod="11c",
                )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["SIPARIS"],
            kod="12a",
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
        mal_kabul = self._kayit_bul(self.mal_kabuller, mal_kabul_no, kod="15a")
        if mal_kabul.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{mal_kabul_no}: mal kabul iptal edilmiş, karar verilemez",
                kod="15b",
            )
        if karar not in KARANTINA_KARAR_GEREKCELERI:
            raise GecersizGirisError(
                f"Geçersiz karar: {karar}; geçerli olanlar: "
                f"{', '.join(KARANTINA_KARAR_GEREKCELERI)}",
                kod="15c",
            )

        bulunan_kalem = None
        for kalem in mal_kabul.mal_kabul_kalemleri:
            if kalem.kalem_no == mal_kabul_kalem_no:
                bulunan_kalem = kalem
        if bulunan_kalem is None:
            raise IslemYapilamazError(
                f"{mal_kabul_no}: {mal_kabul_kalem_no} numaralı kalem yok",
                kod="15b",
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
                f"karantina yok",
                kod="15b",
            )
        if miktar <= 0 or miktar > kalan:
            raise GecersizGirisError(
                f"Karar miktarı 0'dan büyük ve kalan karantinadan ({kalan}) "
                f"fazla olmamalı; girilen: {miktar}",
                kod="15c",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=KARANTINA_KARAR_GEREKCELERI[karar],
            kod="15c",
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

    def _faturaya_odenen(self, fatura_no):
        """Faturaya iptal edilmemiş ödemelerle ödenen toplamı hesaplar (R4).

        Kalan borç saklanmaz, her seferinde ödeme kalemlerinden hesaplanır;
        iptal edilen ödeme sayılmaz (ters kayıt). Hiçbir şeyi değiştirmez.

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".

        Returns:
            Ödenen toplam (Decimal); ödeme yoksa Decimal("0").
        """
        odenen = Decimal("0")
        for odeme in self.odemeler.values():
            if odeme.iptal_bilgisi.iptal_edildi:
                continue
            for odeme_kalemi in odeme.odeme_kalemleri:
                if odeme_kalemi.fatura_no == fatura_no:
                    odenen += odeme_kalemi.tutar
        return odenen

    def fatura_kalan_borc(self, fatura_no):
        """Faturanın kalan borcunu döndürür: genel toplam − ödenen (R4).

        Args:
            fatura_no: Fatura numarası, ör. "FTR-0001".

        Returns:
            Kalan borç (Decimal), ör. 2000 − 600 → Decimal("1400").

        Raises:
            KayitBulunamadiError: Fatura yoksa (27c).
        """
        fatura = self.fatura_bul(fatura_no)
        return fatura.genel_toplam() - self._faturaya_odenen(fatura_no)

    def odeme_kaydet(self, tedarikci_kodu, kalemler, odeme_yontemi,
                     odeme_notu=None, tarih=None):
        """Tedarikçiye yapılan ödemeyi kaydeder ve döndürür (E123).

        Tek ödeme aynı tedarikçinin birden çok faturasını kapatabilir (O2).
        Sadece iptal edilmemiş ONAYLANDI ya da SERBEST fatura ödenir (O1);
        tutar kalan borcu aşamaz, kısmi ödeme olabilir (O3). Ödeme numarası
        bütün kontrollerden sonra alınır; hatalı girişte sayaç artmaz.

        Args:
            tedarikci_kodu: Ödenen tedarikçi, ör. "TED-0001".
            kalemler: Kalem sözlüklerinin listesi: fatura_no, tutar
                (Decimal), ör. [{"fatura_no": "FTR-0001",
                "tutar": Decimal("600")}].
            odeme_yontemi: ODEME_YONTEMLERI'nden biri, ör. "HAVALE_EFT".
            odeme_notu: Açıklama; isteğe bağlı.
            tarih: "2026-11-02" biçiminde; None ise bugün.

        Returns:
            Oluşturulan Odeme.

        Raises:
            KayitBulunamadiError: Tedarikçi ya da fatura yoksa (23a).
            GecersizGirisError: Kalem yoksa ya da ödeme yöntemi geçersizse
                (23b); tutar Decimal değilse, ≤ 0 ise, kalan borcu aşıyorsa
                ya da aynı fatura iki kalemde varsa (23e, O4).
            IslemYapilamazError: Fatura iptal edilmişse ya da ONAYLANDI /
                SERBEST değilse (23c, O1); başka tedarikçininse (23d, O2).
        """
        self._kayit_bul(self.tedarikciler, tedarikci_kodu, kod="23a")
        if not kalemler:
            raise GecersizGirisError("Ödemede en az bir kalem olmalı", kod="23b")
        if odeme_yontemi not in ODEME_YONTEMLERI:
            raise GecersizGirisError(
                f"Geçersiz ödeme yöntemi: {odeme_yontemi}; geçerli olanlar: "
                f"{', '.join(ODEME_YONTEMLERI)}",
                kod="23b",
            )

        gorulen_faturalar = []
        for kalem in kalemler:
            fatura_no = kalem["fatura_no"]
            tutar = kalem["tutar"]
            if not isinstance(tutar, Decimal):
                raise GecersizGirisError(
                    f"{fatura_no}: tutar sayı olmalı",
                    kod="23e",
                )
            if tutar <= 0:
                raise GecersizGirisError(
                    f"{fatura_no}: tutar 0'dan büyük olmalı",
                    kod="23e",
                )
            if fatura_no in gorulen_faturalar:
                raise GecersizGirisError(
                    f"{fatura_no}: aynı fatura ödemede iki kez girilmiş",
                    kod="23e",
                )
            fatura = self._kayit_bul(self.faturalar, fatura_no, kod="23a")
            if (fatura.iptal_bilgisi.iptal_edildi
                    or fatura.durum not in ("ONAYLANDI", "SERBEST")):
                raise IslemYapilamazError(
                    f"{fatura_no}: sadece iptal edilmemiş ONAYLANDI ya da "
                    f"SERBEST fatura ödenir (şu an {fatura.durum})",
                    kod="23c",
                )
            fatura_tedarikcisi = self._kayit_bul(
                self.siparisler, fatura.siparis_no, kod="26c"
            ).tedarikci_kodu
            if fatura_tedarikcisi != tedarikci_kodu:
                raise IslemYapilamazError(
                    f"{fatura_no}: fatura başka tedarikçinin "
                    f"({fatura_tedarikcisi})",
                    kod="23d",
                )
            kalan_borc = self.fatura_kalan_borc(fatura_no)
            if tutar > kalan_borc:
                raise GecersizGirisError(
                    f"{fatura_no}: tutar ({tutar}) kalan borcu "
                    f"({kalan_borc}) aşıyor",
                    kod="23e",
                )
            gorulen_faturalar.append(fatura_no)

        if tarih is None:
            tarih = date.today().isoformat()

        odeme_kalemleri = []
        kalem_no = KALEM_NO_ARTISI
        for kalem in kalemler:
            odeme_kalemleri.append(OdemeKalemi(
                kalem_no=kalem_no,
                fatura_no=kalem["fatura_no"],
                tutar=kalem["tutar"],
            ))
            kalem_no += KALEM_NO_ARTISI

        odeme_no = self._numara_ver(ONEKLER["odeme"])
        yeni_odeme = Odeme(
            odeme_no=odeme_no,
            tedarikci_kodu=tedarikci_kodu,
            odeme_yontemi=odeme_yontemi,
            odeme_kalemleri=odeme_kalemleri,
            kayit_tarihi=tarih,
            odeme_notu=odeme_notu,
        )
        self.odemeler[odeme_no] = yeni_odeme
        self._kaydet()
        return yeni_odeme

    def odeme_bul(self, odeme_no):
        """Ödemeyi numarasıyla bulur ve döndürür; hiçbir şeyi değiştirmez.

        Args:
            odeme_no: Ödeme numarası, ör. "ODM-0001".

        Returns:
            Bulunan Odeme.

        Raises:
            KayitBulunamadiError: Numara yoksa (24a).
        """
        return self._kayit_bul(self.odemeler, odeme_no, kod="24a")

    def odeme_iptal_et(self, odeme_no, gerekce, notu=None, tarih=None):
        """Ödemeyi gerekçeyle iptal eder (ters kayıt, SAP reversal).

        Ödeme silinmez; iptal edilen ödeme kalan borçta sayılmaz, fatura
        yeniden ödeme bekler. Değer döndürmez.

        Args:
            odeme_no: Ödeme numarası, ör. "ODM-0001".
            gerekce: IPTAL_GEREKCELERI["ODEME"] kodu.
            notu: Açıklama; DIGER seçildiyse zorunlu.
            tarih: "YYYY-AA-GG"; verilmezse bugün.

        Raises:
            KayitBulunamadiError: Ödeme yoksa (24a).
            IslemYapilamazError: Ödeme zaten iptal edilmişse (24b).
            GecersizGirisError: Gerekçe geçersizse ya da DIGER notsuzsa (12a).
        """
        if tarih is None:
            tarih = date.today().isoformat()
        odeme = self.odeme_bul(odeme_no)
        if odeme.iptal_bilgisi.iptal_edildi:
            raise IslemYapilamazError(
                f"{odeme_no}: ödeme zaten iptal edilmiş",
                kod="24b",
            )
        self._gerekceyi_dogrula(
            gerekce=gerekce,
            notu=notu,
            gecerli_gerekceler=IPTAL_GEREKCELERI["ODEME"],
            kod="12a",
        )
        odeme.iptal_bilgisi.iptal_et(gerekce, notu, tarih)
        self._kaydet()

    def odeme_bekleyen_faturalari_listele(self):
        """Kalan borcu olan ödenebilir faturalar (ilke 10, O6).

        Sadece iptal edilmemiş ONAYLANDI ya da SERBEST faturalar girer;
        kalan borcu 0 olan (tam ödenmiş) çıkar.

        Returns:
            Fatura listesi; yoksa boş.
        """
        bekleyenler = []
        for fatura in self.faturalar.values():
            if fatura.iptal_bilgisi.iptal_edildi:
                continue
            if fatura.durum not in ("ONAYLANDI", "SERBEST"):
                continue
            if self.fatura_kalan_borc(fatura.fatura_no) > 0:
                bekleyenler.append(fatura)
        return bekleyenler

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
        fatura = self._kayit_bul(self.faturalar, fatura_no, kod="16a")
        if (fatura.iptal_bilgisi.iptal_edildi
                or fatura.durum not in ("BLOKE", "ONAYLANDI", "SERBEST")):
            raise IslemYapilamazError(
                f"{fatura_no}: ayrıntı sadece eşleşmiş ve aktif faturada "
                f"gösterilir (şu an {fatura.durum})",
                kod="16b",
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


    


        
        
