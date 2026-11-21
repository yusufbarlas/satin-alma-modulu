from dataclasses import dataclass, field
from decimal import Decimal

from hatalar import GecersizGirisError, IslemYapilamazError
from para import net_fiyat_hesapla, tutar_yuvarla


SIPARIS_DURUM_GECISLERI = {"TASLAK": ["ONAYLANDI"], "ONAYLANDI": []}

FATURA_DURUM_GECISLERI = {
    "ESLESME_BEKLIYOR": ["ONAYLANDI", "BLOKE", "REDDEDILDI"],
    "BLOKE": ["SERBEST", "REDDEDILDI"],
    "ONAYLANDI": [],
    "SERBEST": [],
    "REDDEDILDI": [],
}


@dataclass
class Tedarikci:
    """Tedarikçi ana verisi (iş ortağı kartı).

    Belge değil, ana veridir; bu yüzden kayit_tarihi ve durum alanı yoktur.

    Attributes:
        tedarikci_kodu: Sistemin verdiği kod, ör. "TED-0001".
        tedarikci_adi: Listede görünen kısa ad, ör. "ABC Kırtasiye".
        firma_adi: Resmi unvan; isteğe bağlı, verilmezse None.
    """

    tedarikci_kodu: str
    tedarikci_adi: str
    firma_adi: str | None = None


@dataclass
class IptalBilgisi:
    """Belgenin iptal kartı; sipariş, mal kabul ve faturada birer tane (has-a).

    Belge açılırken boş kurulur; sadece iptal_et doldurur. İptal bir durum
    değil, ayrı bilgidir ve geri dönmez.

    Attributes:
        iptal_edildi: Belge iptal edildiyse True.
        iptal_gerekcesi: IPTAL_GEREKCELERI'ndeki kod, ör. "VAZGECILDI".
        iptal_notu: Serbest açıklama; DIGER seçildiyse zorunlu (servis kontrol eder).
        iptal_tarihi: İptal tarihi, ör. "2026-11-02".
    """

    iptal_edildi: bool = False
    iptal_gerekcesi: str | None = None
    iptal_notu: str | None = None
    iptal_tarihi: str | None = None

    def iptal_et(self, gerekce, notu, tarih):
        """Belgeyi iptal edilmiş olarak işaretler; değer döndürmez.

        Gerekçenin listede olup olmadığını model kontrol etmez, servis
        kontrol eder (12a, E62, E71).

        Args:
            gerekce: İptal gerekçesi kodu, ör. "VAZGECILDI".
            notu: Açıklama ya da None (`not` ayrılmış kelime olduğu için notu).
            tarih: İptal tarihi, ör. "2026-11-02"; servis verir (E53).

        Raises:
            IslemYapilamazError: Belge zaten iptal edilmişse (8b, 9b, 11b).
        """
        if self.iptal_edildi:
            raise IslemYapilamazError(
                "Belge zaten iptal edilmiş; iptal geri alınamaz"
            )
        self.iptal_edildi = True
        self.iptal_gerekcesi = gerekce
        self.iptal_notu = notu
        self.iptal_tarihi = tarih


@dataclass
class ToleransKopyasi:
    """Sipariş açılırken ayardan kopyalanan tolerans değerleri (E59, E80).

    SiparisKalemi'nin içinde durur (has-a). Ayar sonradan değişse de eski
    siparişin kuralı değişmez (anlık görüntü, snapshot). Yüzde alanları
    yüzde olarak tutulur (10 = %10); None = tanımsız sınır.

    Attributes:
        fazla_teslimat_yuzde: Fazla teslimat toleransı, yüzde.
        fazla_teslimat_tl: Fazla teslimat toleransı, TL tavanı.
        asiri_sinir_yuzde: Aşırı teslimat sınırı, yüzde.
        asiri_sinir_tl: Aşırı teslimat sınırı, TL tavanı.
        fiyat_ust_yuzde: Fiyat üst sınırı, yüzde.
        fiyat_ust_tl: Fiyat üst sınırı, TL tavanı.
        fiyat_alt_yuzde: Fiyat alt sınırı, yüzde.
        fiyat_alt_tl: Fiyat alt sınırı, TL tavanı.
        kucuk_fark_esigi: Bu tutarın altındaki fark yok sayılır (E40); hiç None olmaz.
    """

    fazla_teslimat_yuzde: Decimal | None
    fazla_teslimat_tl: Decimal | None
    asiri_sinir_yuzde: Decimal | None
    asiri_sinir_tl: Decimal | None
    fiyat_ust_yuzde: Decimal | None
    fiyat_ust_tl: Decimal | None
    fiyat_alt_yuzde: Decimal | None
    fiyat_alt_tl: Decimal | None
    kucuk_fark_esigi: Decimal


@dataclass
class SiparisKalemi:
    """Siparişin bir satırı: ne, ne kadar, kaça (sipariş kalemi).

    Net fiyat saklanmaz, her seferinde hesaplanır (E30).

    Attributes:
        kalem_no: Sipariş içindeki numara: 10, 20, 30 (KALEM_NO_ARTISI).
        malzeme_adi: Ürün adı, ör. "Defter".
        miktar: Sipariş miktarı (> 0), ör. Decimal("10").
        birim: "adet", "kg" ya da "metre".
        birim_fiyat: İskonto öncesi birim fiyat, ör. Decimal("12.50").
        kategori: "SARF" ya da "STRATEJIK"; tolerans buna göre seçilir.
        tolerans: Açılış anındaki tolerans kopyası (ToleransKopyasi).
        iskonto_turu: "ORAN" (yüzde) ya da "TUTAR" (adet başına TL).
        iskonto_degeri: İskonto değeri; varsayılan 0.
        miktar_tavani: Fazla teslimat toleransına adet tavanı; None = yok (E48).
    """

    kalem_no: int
    malzeme_adi: str
    miktar: Decimal
    birim: str
    birim_fiyat: Decimal
    kategori: str
    tolerans: ToleransKopyasi
    iskonto_turu: str = "ORAN"
    iskonto_degeri: Decimal = Decimal("0")
    miktar_tavani: Decimal | None = None

    def tutar(self):
        """Kalem tutarı: miktar × net birim fiyat; tek kez yuvarlanır (E35).

        Returns:
            Kalem tutarı (Decimal, 2 hane), ör. 10 × 11.25 → Decimal("112.50").
        """
        net_fiyat = net_fiyat_hesapla(
            self.birim_fiyat, self.iskonto_turu, self.iskonto_degeri
        )
        return tutar_yuvarla(net_fiyat * self.miktar)


@dataclass
class Siparis:
    """Satın alma siparişi (purchase order): tedarikçiye verilen söz.

    Durum TASLAK ile başlar, onayla ONAYLANDI olur; durumu sadece
    durum_degistir değiştirir (E86). İptal durum değil, iptal_bilgisi'dir.

    Attributes:
        siparis_no: Sistemin verdiği numara, ör. "SAS-0001".
        tedarikci_kodu: Tedarikçinin kodu, ör. "TED-0001"; sonradan değişmez (E42).
        siparis_kalemleri: SiparisKalemi listesi; en az 1 kalem.
        kayit_tarihi: Kayıt tarihi (posting date), ör. "2026-11-02" (E53).
        durum: "TASLAK" ya da "ONAYLANDI".
        iptal_bilgisi: Boş kurulan iptal kartı (IptalBilgisi).
    """

    siparis_no: str
    tedarikci_kodu: str
    siparis_kalemleri: list[SiparisKalemi]
    kayit_tarihi: str
    durum: str = "TASLAK"
    iptal_bilgisi: IptalBilgisi = field(default_factory=IptalBilgisi)

    def genel_toplam(self):
        """Bütün kalem tutarlarının toplamı.

        Returns:
            Sipariş toplamı (Decimal); her kalem kendi içinde yuvarlanmıştır.
        """
        toplam = Decimal("0")
        for kalem in self.siparis_kalemleri:
            toplam += kalem.tutar()
        return toplam

    def durum_degistir(self, yeni_durum):
        """Durumu SIPARIS_DURUM_GECISLERI'ndeki izinli geçişe göre değiştirir.

        Args:
            yeni_durum: Hedef durum, ör. "ONAYLANDI".

        Raises:
            IslemYapilamazError: Geçişe izin yoksa (ör. ONAYLANDI → TASLAK).
        """
        izinli_durumlar = SIPARIS_DURUM_GECISLERI[self.durum]
        if yeni_durum not in izinli_durumlar:
            raise IslemYapilamazError(
                f"{self.siparis_no}: {self.durum} → {yeni_durum} geçişine izin yok"
            )
        self.durum = yeni_durum

@dataclass
class NedenliMiktar:
    """Karantina ya da kapıda red için bir neden ve miktarı (E110).

    MalKabulKalemi'nin karantinalar / kapida_redler listelerinin elemanı;
    MalKabulDagitimi ile aynı kalıp.

    Attributes:
        neden: Neden kodu (KARANTINA_NEDENLERI ya da KAPIDA_RED_NEDENLERI),
            ör. "IADE_BEKLIYOR".
        miktar: O nedene düşen miktar (> 0), ör. Decimal("2").
    """

    neden: str
    miktar: Decimal


@dataclass
class MalKabulKalemi:
    """Mal kabulün bir satırı: bir sipariş kalemine gelen malın üç kovası.

    Gelen = kabul + karantina toplamı + kapıda red toplamı (hesaplanır,
    saklanmaz). Eşleştirme sadece kabul_edilen_miktar'a bakar (Karar 4).
    Karantina ve kapıda red nedenli miktar listesidir; tek kalemde
    birden çok neden olabilir (E110).

    Attributes:
        kalem_no: Mal kabulün kendi satır numarası: 10, 20, 30 (R6).
        siparis_kalem_no: Hangi sipariş kalemine ait, ör. 10.
        kabul_edilen_miktar: Depoya kabul edilen miktar (≥ 0).
        karantinalar: NedenliMiktar listesi (KARAR_BEKLIYOR /
            IADE_BEKLIYOR); yoksa [].
        kapida_redler: NedenliMiktar listesi (ASIRI_TESLIMAT /
            YANLIS_URUN); yoksa [].
    """

    kalem_no: int
    siparis_kalem_no: int
    kabul_edilen_miktar: Decimal
    karantinalar: list[NedenliMiktar] = field(default_factory=list)
    kapida_redler: list[NedenliMiktar] = field(default_factory=list)

    def karantina_miktari(self):
        """Karantinadaki toplam miktar (bütün nedenler).

        Returns:
            Decimal, ör. 2 KARAR_BEKLIYOR + 2 IADE_BEKLIYOR → Decimal("4").
        """
        toplam = Decimal("0")
        for karantina in self.karantinalar:
            toplam += karantina.miktar
        return toplam

    def kapida_red_miktari(self):
        """Kapıda reddedilen toplam miktar (bütün nedenler).

        Returns:
            Decimal, ör. 2 YANLIS_URUN + 2 ASIRI_TESLIMAT → Decimal("4").
        """
        toplam = Decimal("0")
        for red in self.kapida_redler:
            toplam += red.miktar
        return toplam

@dataclass
class MalKabul:
    mal_kabul_no: str
    siparis_no: str
    mal_kabul_kalemleri: list[MalKabulKalemi]
    kayit_tarihi: str
    mal_kabul_notu: str | None = None
    iptal_bilgisi: IptalBilgisi = field(default_factory=IptalBilgisi)


@dataclass
class KarantinaKarari:
    """Karantinadaki mal için verilen kararın ayrı kaydı (Karar 6-7, E86).

    Mal kabul belgesi değişmez; kalan karantina = karantina toplamı −
    kararlar (hesaplanır). v1a'da karar sadece "IADE"; "KABUL" v2'de.

    Attributes:
        mal_kabul_no: Hangi mal kabul, ör. "MKB-0001".
        mal_kabul_kalem_no: Hangi mal kabul kalemi, ör. 10.
        karar: "IADE" (v2: + "KABUL").
        miktar: Karar verilen miktar; kısmi olabilir, ör. Decimal("3").
        karar_gerekcesi: KARANTINA_KARAR_GEREKCELERI kodu,
            ör. "FAZLA_KABUL_EDILMEDI".
        kayit_tarihi: Kararın günü, ör. "2026-11-02" (E53).
        karar_notu: Açıklama; DIGER seçildiyse zorunlu (servis kontrol eder).
    """

    mal_kabul_no: str
    mal_kabul_kalem_no: int
    karar: str
    miktar: Decimal
    karar_gerekcesi: str
    kayit_tarihi: str
    karar_notu: str | None = None


@dataclass
class MalKabulDagitimi:
    """Fatura kaleminin bir mal kabulden kapattığı miktar (E41).

    "Bu fatura hangi teslimatı kapatıyor?" sorusunun cevabı; eşleştirme okumaz.

    Attributes:
        mal_kabul_no: Kapatılan mal kabul, ör. "MKB-0001".
        miktar: O mal kabulden kapatılan miktar (> 0), ör. Decimal("6").
    """

    mal_kabul_no: str
    miktar: Decimal


@dataclass
class FaturaKalemi:
    """Faturanın bir satırı: hangi sipariş kalemi, kaç adet, kaça.

    Dağıtım bekleyen faturada boştur; eşleşmede sadece dagitimi_yaz ile
    yazılır (E107).

    Attributes:
        kalem_no: Faturanın kendi satır numarası: 10, 20, 30 (R6).
        siparis_kalem_no: Faturalanan sipariş kalemi, ör. 10.
        miktar: Faturalanan miktar (> 0), ör. Decimal("10").
        birim_fiyat: Faturadaki iskonto öncesi birim fiyat.
        mal_kabul_dagitimi: MalKabulDagitimi listesi; bekleyen faturada [].
        iskonto_turu: "ORAN" (yüzde) ya da "TUTAR" (adet başına TL).
        iskonto_degeri: Tedarikçinin faturada yazdığı iskonto; varsayılan 0.
    """

    kalem_no: int
    siparis_kalem_no: int
    miktar: Decimal
    birim_fiyat: Decimal
    mal_kabul_dagitimi: list[MalKabulDagitimi]
    iskonto_turu: str = "ORAN"
    iskonto_degeri: Decimal = Decimal("0")

    def tutar(self):
        """Kalem tutarı: miktar × net birim fiyat; tek kez yuvarlanır (E35).

        Returns:
            Kalem tutarı (Decimal, 2 hane).
        """
        net_fiyat = net_fiyat_hesapla(
            self.birim_fiyat, self.iskonto_turu, self.iskonto_degeri
        )
        return tutar_yuvarla(net_fiyat * self.miktar)

    def dagitimi_yaz(self, dagitimlar):
        """Mal kabul dağıtımını kontrol edip yazar; değer döndürmez (E107).

        Hata olursa alan değişmez.

        Args:
            dagitimlar: MalKabulDagitimi listesi, ör.
                [MalKabulDagitimi("MKB-0001", Decimal("6")),
                 MalKabulDagitimi("MKB-0002", Decimal("4"))].

        Raises:
            GecersizGirisError: Liste boşsa, bir miktar 0 ya da eksiyse ya da
                miktarların toplamı fatura kalemi miktarına eşit değilse (6c).
        """
        if not dagitimlar:
            raise GecersizGirisError(
                f"Kalem {self.kalem_no}: mal kabul dağıtımı boş olamaz"
            )
        toplam = Decimal("0")
        for dagitim in dagitimlar:
            if dagitim.miktar <= 0:
                raise GecersizGirisError(
                    f"Kalem {self.kalem_no}: {dagitim.mal_kabul_no} dağıtım "
                    f"miktarı 0'dan büyük olmalı ({dagitim.miktar})"
                )
            toplam += dagitim.miktar
        if toplam != self.miktar:
            raise GecersizGirisError(
                f"Kalem {self.kalem_no}: dağıtım toplamı {toplam}, "
                f"fatura kalemi miktarı {self.miktar}; eşit olmalı"
            )
        self.mal_kabul_dagitimi = dagitimlar


@dataclass
class Fatura:
    """Tedarikçi faturası (supplier invoice); eşleştirme sonucu durumunda tutulur.

    Durum ESLESME_BEKLIYOR ile başlar; durumu sadece durum_degistir
    değiştirir. İptal durum değil, iptal_bilgisi'dir.

    Attributes:
        fatura_no: Bizim iç numaramız, ör. "FTR-0001".
        tedarikci_fatura_no: Tedarikçinin kendi fatura numarası, ör. "F-1001".
        siparis_no: Faturanın bağlı olduğu sipariş, ör. "SAS-0001".
        fatura_kalemleri: FaturaKalemi listesi; en az 1 kalem.
        kayit_tarihi: Sisteme girildiği gün, ör. "2026-11-02" (E53).
        durum: ESLESME_BEKLIYOR, ONAYLANDI, BLOKE, SERBEST ya da REDDEDILDI.
        bloke_neden_kodlari: Son eşleştirmenin neden kodları; boş başlar (E36).
        karar_gerekcesi: Serbest bırak / reddet gerekçesi (KARAR_GEREKCELERI).
        karar_notu: Karar açıklaması; DIGER seçildiyse zorunlu (servis kontrol eder).
        iptal_bilgisi: Boş kurulan iptal kartı (IptalBilgisi).
        karar_tarihi: Serbest bırak / reddet günü, ör. "2026-11-02"; karar
        verilene kadar None (E113).
    """

    fatura_no: str
    tedarikci_fatura_no: str
    siparis_no: str
    fatura_kalemleri: list[FaturaKalemi]
    kayit_tarihi: str
    durum: str = "ESLESME_BEKLIYOR"
    bloke_neden_kodlari: list[str] = field(default_factory=list)
    karar_gerekcesi: str | None = None
    karar_notu: str | None = None
    iptal_bilgisi: IptalBilgisi = field(default_factory=IptalBilgisi)
    karar_tarihi: str | None = None

    def genel_toplam(self):
        """Bütün kalem tutarlarının toplamı.

        Returns:
            Fatura toplamı (Decimal).
        """
        toplam = Decimal("0")
        for kalem in self.fatura_kalemleri:
            toplam += kalem.tutar()
        return toplam

    def durum_degistir(self, yeni_durum):
        """Durumu FATURA_DURUM_GECISLERI'ndeki izinli geçişe göre değiştirir.

        Args:
            yeni_durum: Hedef durum, ör. "BLOKE".

        Raises:
            IslemYapilamazError: Geçişe izin yoksa (ör. ONAYLANDI → BLOKE).
        """
        izinli_durumlar = FATURA_DURUM_GECISLERI[self.durum]
        if yeni_durum not in izinli_durumlar:
            raise IslemYapilamazError(
                f"{self.fatura_no}: {self.durum} → {yeni_durum} geçişine izin yok"
            )
        self.durum = yeni_durum


if __name__ == "__main__":
    bos_tolerans = ToleransKopyasi(
        Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"),
        Decimal("0"),
    )

    print("--- Sipariş ---")
    kalem1 = SiparisKalemi(
        10, "Defter", Decimal("10"), "adet", Decimal("12.50"),
        "SARF", bos_tolerans, "ORAN", Decimal("10"),
    )
    kalem2 = SiparisKalemi(
        20, "Kağıt", Decimal("3"), "adet", Decimal("10.555"),
        "SARF", bos_tolerans,
    )
    siparis = Siparis("SAS-0001", "TED-0001", [kalem1, kalem2], "2026-11-02")
    print(kalem1.tutar(), kalem2.tutar(), siparis.genel_toplam())  # 112.50 31.67 144.17

    print("--- İptal ---")
    mal_kabul = MalKabul(
        "MKB-0001", "SAS-0001", [MalKabulKalemi(10, 10, Decimal("10"))], "2026-11-02"
    )
    mal_kabul.iptal_bilgisi.iptal_et("MUKERRER_GIRIS", None, "2026-11-02")
    print(mal_kabul.iptal_bilgisi.iptal_edildi)  # True
    print(siparis.iptal_bilgisi.iptal_edildi)  # False
    try:
        mal_kabul.iptal_bilgisi.iptal_et("DIGER", "tekrar", "2026-11-03")
    except IslemYapilamazError as hata:
        print(hata)  # Belge zaten iptal edilmiş; iptal geri alınamaz

    print("--- Dağıtım (dagitimi_yaz) ---")
    fatura_kalemi = FaturaKalemi(10, 10, Decimal("10"), Decimal("12.50"), [])
    denemeler = [
        ("a", [MalKabulDagitimi("MKB-0001", Decimal("10"))], "geçerli"),
        ("b", [], "hata"),
        ("c", [MalKabulDagitimi("MKB-0001", Decimal("6")),
               MalKabulDagitimi("MKB-0002", Decimal("4"))], "geçerli"),
        ("d", [MalKabulDagitimi("MKB-0001", Decimal("6")),
               MalKabulDagitimi("MKB-0002", Decimal("3"))], "hata"),
        ("e", [MalKabulDagitimi("MKB-0001", Decimal("10")),
               MalKabulDagitimi("MKB-0002", Decimal("0"))], "hata"),
    ]
    for harf, dagitimlar, beklenen in denemeler:
        try:
            fatura_kalemi.dagitimi_yaz(dagitimlar)
            sonuc = "geçerli"
            mesaj = ""
        except GecersizGirisError as hata:
            sonuc = "hata"
            mesaj = str(hata)
        durum = "GEÇTİ" if sonuc == beklenen else "KALDI"
        print(f"{durum}: {harf} → {sonuc} {mesaj}")
    print(fatura_kalemi.mal_kabul_dagitimi)  # c'deki liste (6 ve 4)

    print("--- Fatura ---")
    fatura_kalemi2 = FaturaKalemi(
        20, 20, Decimal("10"), Decimal("18.90"), [], "ORAN", Decimal("10")
    )
    fatura = Fatura(
        "FTR-0001", "F-1001", "SAS-0001", [fatura_kalemi, fatura_kalemi2], "2026-11-02"
    )
    print(fatura.genel_toplam())  # 125.00 + 170.10 = 295.10
    print(fatura.durum, fatura.bloke_neden_kodlari)  # ESLESME_BEKLIYOR []
    fatura.durum_degistir("ONAYLANDI")
    try:
        fatura.durum_degistir("BLOKE")
    except IslemYapilamazError as hata:
        print(hata)  # FTR-0001: ONAYLANDI → BLOKE geçişine izin yok


        print("--- NedenliMiktar / KarantinaKarari ---")
    print(NedenliMiktar("IADE_BEKLIYOR", Decimal("2")))
    print(KarantinaKarari(
        "MKB-0001", 10, "IADE", Decimal("3"), "FAZLA_KABUL_EDILMEDI", "2026-11-02"
    ))


    print("--- MalKabulKalemi toplamları ---")
    c4_kalemi = MalKabulKalemi(10, 10, Decimal("11"), [
        NedenliMiktar("KARAR_BEKLIYOR", Decimal("2")),
        NedenliMiktar("IADE_BEKLIYOR", Decimal("2")),
    ])
    print(c4_kalemi.karantina_miktari(), c4_kalemi.kapida_red_miktari())  # 4 0
    c9_kalemi = MalKabulKalemi(
        10, 10, Decimal("8"), kapida_redler=[NedenliMiktar("YANLIS_URUN", Decimal("2"))]
    )
    print(c9_kalemi.karantina_miktari(), c9_kalemi.kapida_red_miktari())  # 0 2
        